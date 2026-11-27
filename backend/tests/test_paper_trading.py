from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.paper import service
from backend.app.api.v1 import trading as trading_api
from backend.app.data.providers.factory import get_active_provider


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "DB_PATH", tmp_path / "paper.sqlite3")
    service.initialize()


def test_account_open_idempotency_close_and_reconciliation(isolated_db):
    account = service.create_account(D("10000"), "USD", D("1"))
    assert account["equity"] == D("10000")
    position = service.open_position("BTC/USD", D("100"), D("95"), D("110"), "request-key-0001")
    duplicate = service.open_position("BTC/USD", D("100"), D("95"), D("110"), "request-key-0001")
    assert duplicate["id"] == position["id"]
    assert len(service.list_positions()) == 1
    marked = service.mark_position(position["id"], D("105"))
    assert marked["status"] == "OPEN"
    assert service.get_account()["unrealised_pnl"] > 0
    closed = service.close_position(position["id"], D("105"), "manual")
    assert closed["status"] == "CLOSED"
    close_again = service.close_position(position["id"], D("105"), "manual")
    assert close_again["realised_pnl"] == closed["realised_pnl"]
    account = service.get_account()
    assert account["open_position_count"] == 0
    assert account["realised_pnl"] == D(closed["realised_pnl"])
    assert account["total_fees"] == D(closed["entry_fee"]) + D(closed["exit_fee"])
    assert len(service.history()) == 1
    assert len(service.ledger(position["id"])) == 2


def test_stop_trigger_and_conservative_dual_touch(isolated_db):
    service.create_account(D("10000"), "USD", D("1"))
    position = service.open_position("BTC/USD", D("100"), D("95"), D("107.5"), "request-key-0002")
    closed = service.mark_position(position["id"], D("100"), candle_low=D("94"), candle_high=D("106"))
    assert closed["status"] == "CLOSED"
    assert closed["close_reason"] == "stop_loss"
    assert D(closed["exit_price"]) < D("95")


def test_paper_api_account_and_open_position(isolated_db):
    client = TestClient(app)
    response = client.post("/api/v1/paper/account", json={"starting_balance":"5000", "quote_currency":"USD"})
    assert response.status_code == 200
    opened = client.post("/api/v1/paper/positions", json={"symbol":"BTC/USD","entry":"100","stop_loss":"95","take_profit":"110","idempotency_key":"api-request-0001"})
    assert opened.status_code == 201
    assert client.get("/api/v1/paper/positions").json()[0]["id"] == opened.json()["id"]
    assert client.get("/api/v1/paper/account").json()["open_position_count"] == 1
    assert client.post(f"/api/v1/paper/positions/{opened.json()['id']}/close", json={"exit_price":"105"}).status_code == 200
    assert client.get("/api/v1/paper/history").json()[0]["status"] == "CLOSED"


def test_signal_to_paper_portfolio_workflow(isolated_db, monkeypatch):
    class Provider:
        name = "Test"
        default_symbol = "BTC/USD"
        supported_timeframes = ["1h"]
        max_candle_limit = 60
        def get_candles(self, **kwargs):
            return [{"timestamp": i * 3_600_000, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1} for i in range(60)]
    monkeypatch.setattr(trading_api, "generate_signal", lambda **kwargs: {"symbol":"BTC/USD","timeframe":"1h","signal":"BUY","direction":"BULLISH","score":8,"score_scale":[-12,12],"strength":"strong","evaluation_timestamp":1,"generated_at":2,"trend":"bullish","indicator_observations":{},"structural_observations":{},"reason_codes":["STRUCTURE_BULLISH"],"explanation":"Rule-aligned BUY."})
    app.dependency_overrides[get_active_provider] = lambda: Provider()
    try:
        client = TestClient(app)
        assert client.get("/api/v1/analysis/signal?limit=60").json()["signal"] == "BUY"
        client.post("/api/v1/paper/account", json={"starting_balance":"10000"}).raise_for_status()
        risk = client.post("/api/v1/paper/risk-preview", json={"symbol":"BTC/USD","direction":"long","entry":"100","stop_loss":"95","take_profit":"110","idempotency_key":"workflow-preview-0001"}).json()
        assert risk["accepted"] is True
        opened = client.post("/api/v1/paper/positions", json={"symbol":"BTC/USD","entry":"100","stop_loss":"95","take_profit":"110","idempotency_key":"workflow-open-0001"}).json()
        marked = client.post(f"/api/v1/paper/positions/{opened['id']}/mark", json={"mark_price":"105"}).json()
        assert marked["status"] == "OPEN"
        client.post(f"/api/v1/paper/positions/{opened['id']}/close", json={"exit_price":"105"}).raise_for_status()
        assert client.get("/api/v1/paper/history").json()[0]["status"] == "CLOSED"
        assert client.get("/api/v1/paper/performance").json()["open_position_count"] == 0
    finally:
        app.dependency_overrides.clear()


def test_stop_loss_risk_includes_entry_exit_slippage_and_both_fees(isolated_db):
    service.create_account(D("10000"), "USD", D("1"))
    preview = service.preview_position("BTC/USD", "long", D("100"), D("95"), D("110"))
    assert preview["accepted"] is True

    expected_entry_fill = D("100") * (D("1") + service.SLIPPAGE_RATE)
    expected_stop_exit_fill = D("95") * (D("1") - service.SLIPPAGE_RATE)
    expected_unit_risk = (
        expected_entry_fill
        - expected_stop_exit_fill
        + expected_entry_fill * service.FEE_RATE
        + expected_stop_exit_fill * service.FEE_RATE
    )
    assert preview["risk_per_unit"] == expected_unit_risk

    position = service.open_position("BTC/USD", D("100"), D("95"), D("110"), "risk-sizing-0001")
    qty = D(position["quantity"])
    assert qty == preview["position_quantity"]
    assert qty.as_tuple().exponent >= -8

    closed = service.close_position(position["id"], D("95"), "stop_loss")
    actual_loss = -D(closed["realised_pnl"])
    assert actual_loss > D("0")
    assert actual_loss <= D("100")
    assert actual_loss == preview["estimated_max_loss_including_fees"]


def test_aggregate_open_risk_includes_costs_and_blocks_cap_bypass(isolated_db):
    service.create_account(D("10000"), "USD", D("2"))
    pos1 = service.open_position("BTC/USD", D("100"), D("95"), D("115"), "agg-risk-0001", risk_percent=D("2"))
    pos2 = service.open_position("ETH/USD", D("100"), D("95"), D("115"), "agg-risk-0002", risk_percent=D("2"))

    account = service.get_account()
    raw_price_risk = (
        (D(pos1["entry_price"]) - D(pos1["stop_loss"])) * D(pos1["quantity"])
        + (D(pos2["entry_price"]) - D(pos2["stop_loss"])) * D(pos2["quantity"])
    )
    assert account["aggregate_open_risk"] > raw_price_risk

    # Without execution costs, raw_price_risk (~381.67) + 1.01% (~101) <= 500 cap;
    # with execution costs, aggregate_open_risk (~400) + 1.01% (~101) > 500 cap.
    assert raw_price_risk + D("101") <= D("500")
    assert account["aggregate_open_risk"] + D("101") > D("500")
    preview_over = service.preview_position("SOL/USD", "long", D("100"), D("95"), D("115"), risk_percent=D("1.01"))
    assert preview_over["accepted"] is False
    assert preview_over["reason_code"] == "MAX_AGGREGATE_OPEN_RISK"
    with pytest.raises(ValueError, match="MAX_AGGREGATE_OPEN_RISK"):
        service.open_position("SOL/USD", D("100"), D("95"), D("115"), "agg-risk-0003", risk_percent=D("1.01"))


def test_buying_power_check_uses_slippage_adjusted_entry_fill_and_fee(isolated_db):
    # Entry=100, stop=90, target=120, risk=100% -> budget would try to use full cash.
    # With starting_balance=1000 and risk_percent=100, qty is limited by cash vs entry fill + entry fee.
    # Verify that preview_trade rejects when cash covers requested entry + fee but not fill + fee.
    from backend.app.risk.service import preview_trade
    # If qty=10, requested entry*10*(1+0.001) = 1001, fill*10*(1+0.001) = 1001.5005
    plan = preview_trade(
        direction="long",
        entry=D("100"),
        stop_loss=D("90"),
        take_profit=D("120"),
        equity=D("10000"),
        available_cash=D("1001.20"),
        risk_percent=D("1.05"),
        fee_rate=D("0.001"),
        slippage_rate=D("0.0005"),
    )
    # Budget=105, unit_risk = 100.05 - 89.955 + 0.10005 + 0.089955 = 10.285005 -> qty ~10.209037
    # Notional + entry_fee > 1001.20 -> must reject with INSUFFICIENT_BUYING_POWER
    assert plan["accepted"] is False
    assert plan["reason_code"] == "INSUFFICIENT_BUYING_POWER"


def test_mark_position_validates_prices_and_candle_bounds_without_mutation(isolated_db):
    service.create_account(D("10000"), "USD", D("1"))
    position = service.open_position("BTC/USD", D("100"), D("95"), D("110"), "mark-val-0001")
    initial_mark = position["mark_price"]

    # Mark outside candle [low, high]
    with pytest.raises(ValueError, match="between candle low and candle high"):
        service.mark_position(position["id"], D("107"), candle_low=D("99"), candle_high=D("106"))
    assert service.get_position(position["id"])["mark_price"] == initial_mark

    # Only one of low / high supplied
    with pytest.raises(ValueError, match="Both candle_low and candle_high"):
        service.mark_position(position["id"], D("101"), candle_low=D("99"))
    with pytest.raises(ValueError, match="Both candle_low and candle_high"):
        service.mark_position(position["id"], D("101"), candle_high=D("105"))
    assert service.get_position(position["id"])["mark_price"] == initial_mark

    # low > high
    with pytest.raises(ValueError, match="cannot exceed"):
        service.mark_position(position["id"], D("101"), candle_low=D("105"), candle_high=D("99"))
    assert service.get_position(position["id"])["mark_price"] == initial_mark

    # Non-finite or non-positive prices
    for bad in (D("0"), D("-5"), D("NaN"), D("Infinity")):
        with pytest.raises(ValueError, match="finite and positive"):
            service.mark_position(position["id"], bad)
        with pytest.raises(ValueError, match="finite and positive"):
            service.mark_position(position["id"], D("101"), candle_low=bad, candle_high=D("105"))
    assert service.get_position(position["id"])["mark_price"] == initial_mark

    # API layer validation
    client = TestClient(app)
    assert client.post(f"/api/v1/paper/positions/{position['id']}/mark?low=99", json={"mark_price": "101"}).status_code == 422
    assert client.post(f"/api/v1/paper/positions/{position['id']}/mark?low=99&high=103", json={"mark_price": "104"}).status_code == 422
    assert client.post(f"/api/v1/paper/positions/{position['id']}/mark", json={"mark_price": "0"}).status_code == 422
    assert client.post(f"/api/v1/paper/positions/{position['id']}/mark", json={"mark_price": "-10"}).status_code == 422
    assert service.get_position(position["id"])["mark_price"] == initial_mark


def test_take_profit_execution_remains_intact(isolated_db):
    service.create_account(D("10000"), "USD", D("1"))
    position = service.open_position("BTC/USD", D("100"), D("95"), D("110"), "tp-exec-0001")
    closed = service.mark_position(position["id"], D("110"), candle_low=D("102"), candle_high=D("111"))
    assert closed["status"] == "CLOSED"
    assert closed["close_reason"] == "take_profit"
    assert D(closed["exit_price"]) == D("110") * (D("1") - service.SLIPPAGE_RATE)
    assert D(closed["realised_pnl"]) > D("0")


def test_close_position_uses_stored_slippage_rate_not_global_default(isolated_db, monkeypatch):
    import json

    service.create_account(D("10000"), "USD", D("1"))
    position = service.open_position("BTC/USD", D("100"), D("95"), D("110"), "stored-slip-0001")
    stored_slippage = D(position["slippage_rate"])
    assert stored_slippage == D("0.0005")

    qty = D(position["quantity"])
    entry_fill = D(position["entry_price"])
    entry_fee = D(position["entry_fee"])
    cash_after_open = service.get_account()["available_cash"]

    # Mutate global SLIPPAGE_RATE after opening; closing must still use stored_slippage.
    monkeypatch.setattr(service, "SLIPPAGE_RATE", D("0.02"))

    # Also verify aggregate open risk still uses stored_slippage, not mutated global.
    expected_stop_exit = D("95") * (D("1") - stored_slippage)
    expected_open_risk = (entry_fill - expected_stop_exit) * qty + entry_fee + expected_stop_exit * qty * service.FEE_RATE
    assert service.get_account()["aggregate_open_risk"] == expected_open_risk

    requested_exit = D("108")
    closed = service.close_position(position["id"], requested_exit, "manual")

    expected_exit_price = requested_exit * (D("1") - stored_slippage)
    expected_exit_fee = expected_exit_price * qty * service.FEE_RATE
    expected_proceeds = expected_exit_price * qty - expected_exit_fee
    expected_realised_pnl = (expected_exit_price - entry_fill) * qty - entry_fee - expected_exit_fee

    assert closed["status"] == "CLOSED"
    assert D(closed["exit_price"]) == expected_exit_price
    assert D(closed["exit_fee"]) == expected_exit_fee
    assert D(closed["realised_pnl"]) == expected_realised_pnl

    account_after_close = service.get_account()
    assert account_after_close["available_cash"] == cash_after_open + expected_proceeds
    assert account_after_close["realised_pnl"] == expected_realised_pnl

    entries = service.ledger(position["id"])
    assert len(entries) == 2
    close_details = json.loads(entries[1]["details"])
    assert D(entries[1]["amount"]) == expected_proceeds
    assert D(close_details["fill"]) == expected_exit_price
    assert D(close_details["fee"]) == expected_exit_fee
    assert D(close_details["slippage_rate"]) == stored_slippage
    assert D(close_details["net_pnl"]) == expected_realised_pnl


def test_close_position_fallback_when_slippage_rate_empty_or_missing(isolated_db):
    service.create_account(D("10000"), "USD", D("1"))
    position = service.open_position("BTC/USD", D("100"), D("95"), D("110"), "legacy-slip-0001")

    # Simulate a legacy row where slippage_rate is empty string.
    with service._connect() as db:
        db.execute("UPDATE positions SET slippage_rate='' WHERE id=?", (position["id"],))
        db.commit()

    closed = service.close_position(position["id"], D("105"), "manual")
    expected_exit_price = D("105") * (D("1") - service.SLIPPAGE_RATE)
    assert D(closed["exit_price"]) == expected_exit_price

    # Also verify _position_slippage_rate handles a dict missing the key altogether.
    legacy_dict = {k: v for k, v in position.items() if k != "slippage_rate"}
    assert service._position_slippage_rate(legacy_dict) == service.SLIPPAGE_RATE
