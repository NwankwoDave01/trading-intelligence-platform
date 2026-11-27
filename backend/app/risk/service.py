"""Decimal-safe trade risk previews; this module does not own portfolio accounting."""
from decimal import Decimal, ROUND_DOWN
from typing import Literal

D = Decimal
QUANTITY_STEP = D("0.00000001")
DEFAULT_RISK_PERCENT = D("1")
MIN_RISK_REWARD = D("1.5")
MAX_OPEN_POSITIONS = 5
MAX_AGGREGATE_OPEN_RISK_PERCENT = D("5")


def preview_trade(*, direction: Literal["long", "short"], entry: Decimal, stop_loss: Decimal, take_profit: Decimal, equity: Decimal, available_cash: Decimal, risk_percent: Decimal = DEFAULT_RISK_PERCENT, min_risk_reward: Decimal = MIN_RISK_REWARD, open_positions: int = 0, aggregate_open_risk: Decimal = D("0"), max_open_positions: int = MAX_OPEN_POSITIONS, max_aggregate_risk_percent: Decimal = MAX_AGGREGATE_OPEN_RISK_PERCENT, fee_rate: Decimal = D("0"), slippage_rate: Decimal = D("0"), max_notional: Decimal | None = None, leverage: Decimal = D("1")) -> dict:
    values = (entry, stop_loss, take_profit, equity, available_cash, risk_percent, min_risk_reward, fee_rate, slippage_rate, leverage)
    if any(not value.is_finite() for value in values) or any(value <= 0 for value in (entry, stop_loss, take_profit, equity, risk_percent, min_risk_reward, leverage)) or available_cash < 0 or fee_rate < 0 or slippage_rate < 0 or slippage_rate >= 1 or aggregate_open_risk < 0:
        return _reject("INVALID_INPUT", "Prices, equity, risk, and ratios must be finite and positive; cash, fees, and slippage cannot be negative.")
    if leverage != 1:
        return _reject("UNSUPPORTED_LEVERAGE", "Leveraged simulation is not supported.")
    if direction not in ("long", "short"):
        return _reject("INVALID_DIRECTION", "Direction must be long or short.")
    if (direction == "long" and not stop_loss < entry < take_profit) or (direction == "short" and not take_profit < entry < stop_loss):
        return _reject("INVALID_PRICE_ORDER", "Stop-loss and take-profit must be on the correct side of entry.")
    if open_positions >= max_open_positions:
        return _reject("MAX_OPEN_POSITIONS", "Configured maximum open positions has been reached.")
    distance = abs(entry - stop_loss)
    reward_per_unit = abs(take_profit - entry)
    rr = reward_per_unit / distance
    if rr < min_risk_reward:
        return _reject("RISK_REWARD_BELOW_MINIMUM", "Proposed risk/reward ratio is below the configured minimum.", risk_reward_ratio=rr)
    budget = equity * risk_percent / D("100")
    if (aggregate_open_risk + budget) > equity * max_aggregate_risk_percent / D("100"):
        return _reject("MAX_AGGREGATE_OPEN_RISK", "Trade would exceed the aggregate open-risk limit.", cash_risk_budget=budget)
    if direction == "long":
        entry_fill = entry * (D("1") + slippage_rate)
        stop_exit_fill = stop_loss * (D("1") - slippage_rate)
        price_risk_per_unit = entry_fill - stop_exit_fill
    else:
        entry_fill = entry * (D("1") - slippage_rate)
        stop_exit_fill = stop_loss * (D("1") + slippage_rate)
        price_risk_per_unit = stop_exit_fill - entry_fill
    entry_fee_per_unit = entry_fill * fee_rate
    exit_fee_per_unit = stop_exit_fill * fee_rate
    unit_risk_with_costs = price_risk_per_unit + entry_fee_per_unit + exit_fee_per_unit
    qty = (budget / unit_risk_with_costs).quantize(QUANTITY_STEP, rounding=ROUND_DOWN)
    notional = qty * entry_fill
    entry_fee = notional * fee_rate
    exit_fee = qty * stop_exit_fill * fee_rate
    fees = entry_fee + exit_fee
    risk = qty * price_risk_per_unit + fees
    while risk > budget and qty > D("0"):
        qty = max(D("0"), qty - QUANTITY_STEP)
        notional = qty * entry_fill
        entry_fee = notional * fee_rate
        exit_fee = qty * stop_exit_fill * fee_rate
        fees = entry_fee + exit_fee
        risk = qty * price_risk_per_unit + fees
    if qty <= 0:
        return _reject("POSITION_TOO_SMALL", "Risk budget is too small for the supported quantity precision.")
    if notional + entry_fee > available_cash:
        return _reject("INSUFFICIENT_BUYING_POWER", "Available cash is below the proposed unleveraged notional plus entry fee.", notional=notional, estimated_entry_fee=entry_fee)
    if max_notional is not None and notional > max_notional:
        return _reject("MAX_EXPOSURE_EXCEEDED", "Trade would exceed the configured maximum notional exposure.", notional=notional)
    return {"accepted": True, "reason_code": "ACCEPTED", "message": "Trade satisfies configured risk limits.", "direction": direction, "entry": entry, "stop_loss": stop_loss, "take_profit": take_profit, "risk_per_unit": unit_risk_with_costs, "cash_risk_budget": budget, "position_quantity": qty, "notional_exposure": notional, "expected_reward": qty * reward_per_unit, "risk_reward_ratio": rr, "estimated_entry_fee": entry_fee, "estimated_exit_fee": exit_fee, "estimated_total_fees": fees, "available_buying_power": available_cash - notional - entry_fee, "estimated_max_loss_including_fees": risk}


def _reject(code: str, message: str, **extra) -> dict:
    return {"accepted": False, "reason_code": code, "message": message, **extra}
