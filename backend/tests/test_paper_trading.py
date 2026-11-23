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
