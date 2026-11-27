"""SQLite-backed virtual portfolio with atomic, auditable accounting."""
from __future__ import annotations
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from typing import Any
from backend.app.risk.service import preview_trade, MAX_OPEN_POSITIONS, MAX_AGGREGATE_OPEN_RISK_PERCENT

D = Decimal
LOCK = threading.RLock()
DB_PATH = Path(os.getenv("PAPER_TRADING_DB", "var/paper_trading.sqlite3"))
FEE_RATE = D("0.001")
SLIPPAGE_RATE = D("0.0005")


def _connect():
    con = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK, _connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY CHECK(id=1), starting_balance TEXT NOT NULL, cash TEXT NOT NULL, quote_currency TEXT NOT NULL, risk_percent TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS positions(id TEXT PRIMARY KEY, symbol TEXT NOT NULL, direction TEXT NOT NULL, entry_price TEXT NOT NULL, quantity TEXT NOT NULL, stop_loss TEXT NOT NULL, take_profit TEXT NOT NULL, entry_fee TEXT NOT NULL, exit_fee TEXT, slippage_rate TEXT NOT NULL, opened_at TEXT NOT NULL, mark_price TEXT NOT NULL, status TEXT NOT NULL, exit_price TEXT, realised_pnl TEXT, close_reason TEXT, idempotency_key TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, position_id TEXT NOT NULL, kind TEXT NOT NULL, amount TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL);
        """)


def _now(): return datetime.now(timezone.utc).isoformat()
def _d(value): return D(str(value))
def _dict(row): return dict(row) if row else None


def _parse_positive_finite_decimal(value: Any, name: str) -> D:
    try:
        dec = _d(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid finite positive number.") from exc
    if not dec.is_finite() or dec <= 0:
        raise ValueError(f"{name} must be finite and positive.")
    return dec


def _position_slippage_rate(position: sqlite3.Row | dict) -> D:
    raw = position["slippage_rate"] if "slippage_rate" in position.keys() else None
    return _d(raw) if raw not in (None, "") else SLIPPAGE_RATE


def _position_worst_case_risk(position: sqlite3.Row | dict) -> D:
    entry_fill = _d(position["entry_price"])
    qty = _d(position["quantity"])
    stop_loss = _d(position["stop_loss"])
    slippage_rate = _position_slippage_rate(position)
    entry_fee = _d(position["entry_fee"])
    if position["direction"] == "short":
        stop_exit_fill = stop_loss * (D("1") + slippage_rate)
        price_loss = (stop_exit_fill - entry_fill) * qty
    else:
        stop_exit_fill = stop_loss * (D("1") - slippage_rate)
        price_loss = (entry_fill - stop_exit_fill) * qty
    exit_fee = stop_exit_fill * qty * FEE_RATE
    return max(D("0"), price_loss + entry_fee + exit_fee)


def get_account():
    initialize()
    with LOCK, _connect() as db:
        account = db.execute("SELECT * FROM accounts WHERE id=1").fetchone()
        if not account: return None
        positions = db.execute("SELECT * FROM positions WHERE status='OPEN' ORDER BY opened_at").fetchall()
        return _summary(account, positions)


def create_account(starting_balance: D, quote_currency: str, risk_percent: D):
    initialize()
    with LOCK, _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO accounts(id,starting_balance,cash,quote_currency,risk_percent,created_at) VALUES(1,?,?,?,?,?)", (str(starting_balance), str(starting_balance), quote_currency, str(risk_percent), _now()))
        db.commit()
        return get_account()


def _summary(account, positions):
    cash = _d(account["cash"]); starting = _d(account["starting_balance"])
    unrealised = sum((_d(p["mark_price"]) - _d(p["entry_price"])) * _d(p["quantity"]) for p in positions)
    open_value = sum(_d(p["mark_price"]) * _d(p["quantity"]) for p in positions)
    realised = D("0")
    fees = D("0")
    # Closed trade details remain in the ledger; derive realized totals once per position.
    with _connect() as db:
        rows = db.execute("SELECT realised_pnl,entry_fee,exit_fee FROM positions WHERE status='CLOSED'").fetchall()
    for row in rows:
        realised += _d(row["realised_pnl"] or 0)
        fees += _d(row["entry_fee"] or 0) + _d(row["exit_fee"] or 0)
    fees += sum((_d(p["entry_fee"]) for p in positions), D("0"))
    open_risk = sum((_position_worst_case_risk(p) for p in positions), D("0"))
    return {"account_id": 1, "starting_balance": starting, "available_cash": cash, "equity": cash + open_value, "realised_pnl": realised, "unrealised_pnl": unrealised, "total_fees": fees, "total_return_percent": ((cash + open_value - starting) / starting * 100), "quote_currency": account["quote_currency"], "risk_percent": _d(account["risk_percent"]), "open_positions": [dict(p) for p in positions], "open_position_count": len(positions), "aggregate_open_risk": open_risk}


def _open_rows(db): return db.execute("SELECT * FROM positions WHERE status='OPEN'").fetchall()


def preview_position(symbol: str, direction: str, entry: D, stop: D, target: D, risk_percent: D | None = None):
    initialize()
    with LOCK, _connect() as db:
        account = db.execute("SELECT * FROM accounts WHERE id=1").fetchone()
        if not account: return {"accepted": False, "reason_code": "ACCOUNT_NOT_FOUND", "message": "Create a paper account first."}
        positions = _open_rows(db)
        equity = _d(account["cash"]) + sum((_d(p["mark_price"]) * _d(p["quantity"]) for p in positions), D("0"))
        aggregate = sum((_position_worst_case_risk(p) for p in positions), D("0"))
        plan = preview_trade(direction=direction, entry=entry, stop_loss=stop, take_profit=target, equity=equity, available_cash=_d(account["cash"]), risk_percent=risk_percent or _d(account["risk_percent"]), open_positions=len(positions), aggregate_open_risk=aggregate, max_open_positions=MAX_OPEN_POSITIONS, max_aggregate_risk_percent=MAX_AGGREGATE_OPEN_RISK_PERCENT, fee_rate=FEE_RATE, slippage_rate=SLIPPAGE_RATE, max_notional=_d(account["cash"]))
        plan["symbol"] = symbol
        return plan


def open_position(symbol: str, entry: D, stop: D, target: D, idempotency_key: str, risk_percent: D | None = None):
    initialize()
    with LOCK, _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT * FROM positions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if previous:
            db.commit(); return dict(previous)
        account = db.execute("SELECT * FROM accounts WHERE id=1").fetchone()
        if not account:
            db.rollback(); raise ValueError("Create a paper account first.")
        positions = _open_rows(db)
        equity = _d(account["cash"]) + sum((_d(p["mark_price"]) * _d(p["quantity"]) for p in positions), D("0"))
        aggregate = sum((_position_worst_case_risk(p) for p in positions), D("0"))
        plan = preview_trade(direction="long", entry=entry, stop_loss=stop, take_profit=target, equity=equity, available_cash=_d(account["cash"]), risk_percent=risk_percent or _d(account["risk_percent"]), open_positions=len(positions), aggregate_open_risk=aggregate, max_open_positions=MAX_OPEN_POSITIONS, max_aggregate_risk_percent=MAX_AGGREGATE_OPEN_RISK_PERCENT, fee_rate=FEE_RATE, slippage_rate=SLIPPAGE_RATE, max_notional=_d(account["cash"]))
        if not plan["accepted"]:
            db.rollback(); raise ValueError(f"{plan['reason_code']}: {plan['message']}")
        fill = entry * (D("1") + SLIPPAGE_RATE)
        stop_exit_fill = stop * (D("1") - SLIPPAGE_RATE)
        # Re-size against actual adverse entry/stop slippage and both-side fees.
        budget = plan["cash_risk_budget"]
        actual_unit_risk = (fill - stop_exit_fill) + (fill * FEE_RATE) + (stop_exit_fill * FEE_RATE)
        risk_limited_qty = (budget / actual_unit_risk).quantize(D("0.00000001"), rounding=ROUND_DOWN)
        cash_limited_qty = (_d(account["cash"]) / (fill * (D("1") + FEE_RATE))).quantize(D("0.00000001"), rounding=ROUND_DOWN)
        qty = min(plan["position_quantity"], risk_limited_qty, cash_limited_qty)
        entry_fee = fill * qty * FEE_RATE
        stop_exit_fee = stop_exit_fill * qty * FEE_RATE
        estimated_loss = (fill - stop_exit_fill) * qty + entry_fee + stop_exit_fee
        while estimated_loss > budget and qty > D("0"):
            qty = max(D("0"), qty - D("0.00000001"))
            entry_fee = fill * qty * FEE_RATE
            stop_exit_fee = stop_exit_fill * qty * FEE_RATE
            estimated_loss = (fill - stop_exit_fill) * qty + entry_fee + stop_exit_fee
        total = fill * qty + entry_fee
        if qty <= 0:
            db.rollback(); raise ValueError("POSITION_TOO_SMALL: Slippage leaves insufficient quantity at supported precision.")
        if total > _d(account["cash"]):
            db.rollback(); raise ValueError("INSUFFICIENT_BUYING_POWER: Slippage-adjusted entry exceeds available cash.")
        pid = str(uuid.uuid4()); now = _now()
        db.execute("UPDATE accounts SET cash=? WHERE id=1", (str(_d(account["cash"]) - total),))
        db.execute("INSERT INTO positions(id,symbol,direction,entry_price,quantity,stop_loss,take_profit,entry_fee,slippage_rate,opened_at,mark_price,status,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (pid,symbol,"long",str(fill),str(qty),str(stop),str(target),str(entry_fee),str(SLIPPAGE_RATE),now,str(fill),"OPEN",idempotency_key))
        db.execute("INSERT INTO ledger(position_id,kind,amount,details,created_at) VALUES(?,?,?,?,?)", (pid,"OPEN",str(total),json.dumps({"fill":str(fill),"quantity":str(qty),"fee":str(entry_fee),"slippage_rate":str(SLIPPAGE_RATE)}),now))
        db.commit()
        return dict(db.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone())


def list_positions(open_only=True):
    initialize()
    with LOCK, _connect() as db:
        rows = db.execute("SELECT * FROM positions WHERE status=? ORDER BY opened_at DESC", ("OPEN" if open_only else "CLOSED",)).fetchall()
        return [dict(row) for row in rows]


def get_position(position_id: str):
    initialize()
    with LOCK, _connect() as db:
        return _dict(db.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone())


def _close_position_in_tx(db: sqlite3.Connection, position_id: str, requested_exit: D, reason: str) -> dict | None:
    row = db.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    if not row:
        return None
    if row["status"] == "CLOSED":
        return dict(row)
    # Stop/target execution uses adverse slippage; if both OHLC levels occur,
    # stop-loss is chosen first by mark_position (conservative deterministic policy).
    position_slippage = _position_slippage_rate(row)
    qty = _d(row["quantity"])
    entry = _d(row["entry_price"])
    if row["direction"] == "short":
        exit_price = requested_exit * (D("1") + position_slippage)
        exit_fee = exit_price * qty * FEE_RATE
        net = (entry - exit_price) * qty - _d(row["entry_fee"]) - exit_fee
        proceeds = entry * qty + (entry - exit_price) * qty - exit_fee
    else:
        exit_price = requested_exit * (D("1") - position_slippage)
        exit_fee = exit_price * qty * FEE_RATE
        proceeds = exit_price * qty - exit_fee
        net = (exit_price - entry) * qty - _d(row["entry_fee"]) - exit_fee
    now = _now()
    account = db.execute("SELECT cash FROM accounts WHERE id=1").fetchone()
    db.execute("UPDATE accounts SET cash=? WHERE id=1", (str(_d(account["cash"]) + proceeds),))
    db.execute(
        "UPDATE positions SET status='CLOSED',exit_price=?,exit_fee=?,realised_pnl=?,close_reason=?,mark_price=? WHERE id=?",
        (str(exit_price), str(exit_fee), str(net), reason, str(exit_price), position_id),
    )
    db.execute(
        "INSERT INTO ledger(position_id,kind,amount,details,created_at) VALUES(?,?,?,?,?)",
        (
            position_id,
            "CLOSE",
            str(proceeds),
            json.dumps({
                "requested_exit": str(requested_exit),
                "fill": str(exit_price),
                "fee": str(exit_fee),
                "slippage_rate": str(position_slippage),
                "net_pnl": str(net),
                "reason": reason,
            }),
            now,
        ),
    )
    return dict(db.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone())


def mark_position(position_id: str, mark: D, candle_low: D | None = None, candle_high: D | None = None):
    mark = _parse_positive_finite_decimal(mark, "mark_price")
    if (candle_low is None) != (candle_high is None):
        raise ValueError("Both candle_low and candle_high must be provided when either is supplied.")
    if candle_low is not None and candle_high is not None:
        low = _parse_positive_finite_decimal(candle_low, "candle_low")
        high = _parse_positive_finite_decimal(candle_high, "candle_high")
        if low > high:
            raise ValueError("Candle low cannot exceed candle high.")
        if not (low <= mark <= high):
            raise ValueError("Mark price must be between candle low and candle high, inclusive.")
    else:
        low = mark
        high = mark

    initialize()
    with LOCK, _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
        if not row or row["status"] != "OPEN":
            db.rollback()
            return _dict(row)
        db.execute("UPDATE positions SET mark_price=? WHERE id=?", (str(mark), position_id))
        if low <= _d(row["stop_loss"]):
            closed = _close_position_in_tx(db, position_id, _d(row["stop_loss"]), "stop_loss")
            db.commit()
            return closed
        if high >= _d(row["take_profit"]):
            closed = _close_position_in_tx(db, position_id, _d(row["take_profit"]), "take_profit")
            db.commit()
            return closed
        db.commit()
        return dict(db.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone())


def close_position(position_id: str, requested_exit: D, reason: str = "manual"):
    initialize()
    with LOCK, _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        closed = _close_position_in_tx(db, position_id, requested_exit, reason)
        if not closed:
            db.rollback()
            return None
        db.commit()
        return closed


def history():
    initialize()
    with LOCK, _connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM positions WHERE status='CLOSED' ORDER BY opened_at DESC")]


def ledger(position_id: str):
    initialize()
    with LOCK, _connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM ledger WHERE position_id=? ORDER BY id", (position_id,))]
