"""Offline API tests for the market structure endpoint."""

import time
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from backend.app.main import app
from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.factory import get_active_provider


def candles(count=80):
    rows = []
    for index in range(count):
        close = 100 + (index % 8) - 4
        rows.append({
            "timestamp": 1_700_000_000_000 + index * 3_600_000,
            "open": close,
            "high": close + 1 + (index % 5 == 0),
            "low": close - 1 - (index % 7 == 0),
            "close": close,
            "volume": 10.0,
        })
    return rows


def provider_with_limit(max_limit=1000):
    provider = MagicMock(spec=BaseMarketDataProvider)
    provider.name = "Binance"
    provider.default_symbol = "BTC/USDT"
    provider.supported_timeframes = ["1h"]
    provider.max_candle_limit = max_limit
    provider.get_candles.return_value = candles()
    return provider


def test_market_structure_api_response_and_provider_injection():
    provider = provider_with_limit()
    app.dependency_overrides[get_active_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analysis/market-structure")
        assert response.status_code == 200
        body = response.json()
        assert body["exchange"] == "Binance"
        assert body["symbol"] == "BTC/USDT"
        assert body["candle_count"] == 80
        assert body["trend"]["classification"] in {"bullish", "bearish", "ranging", "undetermined"}
        assert body["configuration"]["right_bars"] == 3
        provider.get_candles.assert_called_once_with(symbol="BTC/USDT", timeframe="1h", limit=200)
    finally:
        app.dependency_overrides.clear()


def test_binance_maximum_limit_is_passed_without_truncation():
    provider = provider_with_limit(1000)
    app.dependency_overrides[get_active_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analysis/market-structure?limit=1000")
        assert response.status_code == 200
        provider.get_candles.assert_called_once_with(symbol="BTC/USDT", timeframe="1h", limit=1000)
    finally:
        app.dependency_overrides.clear()


def test_provider_limit_is_rejected_without_truncation():
    provider = provider_with_limit(720)
    app.dependency_overrides[get_active_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analysis/market-structure?limit=721")
        assert response.status_code == 400
        assert "exceeds maximum allowed of 720" in response.json()["detail"]
        provider.get_candles.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_invalid_provider_ohlcv_returns_422():
    provider = provider_with_limit()
    rows = candles()
    rows[10]["high"] = float("nan")
    provider.get_candles.return_value = rows
    app.dependency_overrides[get_active_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analysis/market-structure")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_unfinished_final_provider_candle_is_excluded():
    provider = provider_with_limit()
    rows = candles()
    rows[-1]["timestamp"] = time.time_ns() // 1_000_000 - 60_000
    provider.get_candles.return_value = rows
    app.dependency_overrides[get_active_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analysis/market-structure")
        assert response.status_code == 200
        assert response.json()["candle_count"] == len(rows) - 1
    finally:
        app.dependency_overrides.clear()


def test_query_bounds_and_parameter_validation():
    provider = provider_with_limit()
    app.dependency_overrides[get_active_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            too_small = client.get("/api/v1/analysis/market-structure?limit=1")
            invalid_config = client.get("/api/v1/analysis/market-structure?left_bars=0")
        assert too_small.status_code == 422
        assert invalid_config.status_code == 422
    finally:
        app.dependency_overrides.clear()
