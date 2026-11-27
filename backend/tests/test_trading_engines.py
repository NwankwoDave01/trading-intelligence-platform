from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from backend.app.analysis.signals import generate_signal
from backend.app.main import app
from backend.app.risk.service import preview_trade
from backend.app.schemas.trading import SignalResponse
from backend.app.data.providers.factory import get_active_provider


def context(trend="bullish", ema20=110, ema50=100, close=115, rsi=60, macd_line=2, macd_signal=1, hist=1, events=None):
    candles = [{"timestamp": i * 3_600_000, "close": close} for i in range(60)]
    indicators = {"latest": {"ema_20": ema20, "ema_50": ema50, "rsi_14": rsi, "macd": {"line": macd_line, "signal": macd_signal, "histogram": hist}}}
    structure = {"trend": {"classification": trend}, "confirmed_swings": [{"id":"high:1","available_at":0}], "break_events": events or [], "zones": []}
    return candles, indicators, structure


def test_signal_bullish_and_schema():
    candles, indicators, structure = context()
    result = generate_signal(symbol="BTC/USD", timeframe="1h", candles=candles, indicators=indicators, structure=structure, generated_at=9_000_000)
    assert result["signal"] == "BUY"
    assert result["score"] >= 6
    assert result["score_scale"] == [-12, 12]
    assert "-12 to +12" in result["explanation"]
    assert "-10 to +10" not in result["explanation"]
    SignalResponse(**result)


def test_signal_bearish():
    candles, indicators, structure = context("bearish", 90, 100, 85, 40, -2, -1, -1)
    assert generate_signal(symbol="BTC/USD", timeframe="1h", candles=candles, indicators=indicators, structure=structure, generated_at=9_000_000)["signal"] == "SELL"


def test_signal_waits_for_range_insufficient_and_null_indicators():
    candles, indicators, structure = context("ranging")
    assert generate_signal(symbol="X", timeframe="1h", candles=candles, indicators=indicators, structure=structure, generated_at=1)["reason_codes"] == ["STRUCTURE_RANGING"]
    assert generate_signal(symbol="X", timeframe="1h", candles=candles[:10], indicators=indicators, structure=structure, generated_at=1)["reason_codes"] == ["INSUFFICIENT_HISTORY"]
    indicators["latest"]["rsi_14"] = None
    candles, _, structure = context()
    assert generate_signal(symbol="X", timeframe="1h", candles=candles, indicators=indicators, structure=structure, generated_at=1)["reason_codes"] == ["INDICATOR_WARMUP"]
    fresh, values, state = context()
    stale_now = fresh[-1]["timestamp"] + 3 * 3_600_000 + 1
    assert generate_signal(symbol="X", timeframe="1h", candles=fresh, indicators=values, structure=state, generated_at=stale_now)["reason_codes"] == ["STALE_CANDLES"]


def test_signal_conflict_and_availability_filter():
    candles, indicators, structure = context(ema20=90, ema50=100, close=85, rsi=60, macd_line=2, macd_signal=1, hist=1)
    future = {"direction":"bearish", "available_at":10**12, "event_type":"CHoCH"}
    old = {"direction":"bearish", "available_at":0, "event_type":"CHoCH"}
    structure["break_events"] = [future, old]
    result = generate_signal(symbol="X", timeframe="1h", candles=candles, indicators=indicators, structure=structure, generated_at=1)
    assert result["signal"] == "WAIT"
    assert future not in result["structural_observations"]["recent_breaks"]


def test_risk_long_short_limits_precision_and_errors():
    base = dict(entry=D("100"), stop_loss=D("95"), take_profit=D("110"), equity=D("10000"), available_cash=D("10000"))
    long = preview_trade(direction="long", **base)
    short = preview_trade(direction="short", **{**base, "stop_loss":D("105"), "take_profit":D("90")})
    assert long["accepted"] and short["accepted"]
    assert long["position_quantity"] * long["risk_per_unit"] <= long["cash_risk_budget"]
    assert long["position_quantity"].as_tuple().exponent >= -8
    assert preview_trade(direction="long", **{**base,"stop_loss":D("101")})["reason_code"] == "INVALID_PRICE_ORDER"
    assert preview_trade(direction="long", **{**base,"take_profit":D("106")})["reason_code"] == "RISK_REWARD_BELOW_MINIMUM"
    assert preview_trade(direction="long", **{**base,"available_cash":D("1")})["reason_code"] == "INSUFFICIENT_BUYING_POWER"
    assert preview_trade(direction="long", **base, open_positions=5)["reason_code"] == "MAX_OPEN_POSITIONS"
    assert preview_trade(direction="long", **base, aggregate_open_risk=D("500"))["reason_code"] == "MAX_AGGREGATE_OPEN_RISK"
    assert preview_trade(direction="long", **base, leverage=D("2"))["reason_code"] == "UNSUPPORTED_LEVERAGE"


def test_risk_api_validation():
    client = TestClient(app)
    response = client.post("/api/v1/risk/preview", json={"direction":"long","entry":"100","stop_loss":"95","take_profit":"110","equity":"10000","available_cash":"10000"})
    assert response.status_code == 200
    assert response.json()["accepted"] is True
    invalid = client.post("/api/v1/risk/preview", json={"direction":"long","entry":"100","stop_loss":"100","take_profit":"110","equity":"10000","available_cash":"10000"})
    assert invalid.status_code == 200
    assert invalid.json()["reason_code"] == "INVALID_PRICE_ORDER"


def test_signal_api_excludes_unfinished_candle_and_checks_provider_limits():
    class Provider:
        name = "Test"
        default_symbol = "BTC/USD"
        supported_timeframes = ["1h"]
        max_candle_limit = 60
        def get_candles(self, **kwargs):
            return [{"timestamp": i * 3_600_000, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1} for i in range(60)]
    client = TestClient(app)
    app.dependency_overrides[get_active_provider] = lambda: Provider()
    try:
        response = client.get("/api/v1/analysis/signal?limit=60")
        assert response.status_code == 200
        payload = response.json()
        assert payload["signal"] == "WAIT"
        assert payload["evaluation_timestamp"] == 59 * 3_600_000
        assert client.get("/api/v1/analysis/signal?limit=61").status_code == 400
        assert client.get("/api/v1/analysis/signal?limit=49").status_code == 422
        assert client.get("/api/v1/analysis/signal?timeframe=3h").status_code == 400
    finally:
        app.dependency_overrides.clear()
