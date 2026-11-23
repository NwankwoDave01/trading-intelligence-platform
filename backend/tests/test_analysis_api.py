"""
Integration tests for GET /api/v1/analysis/indicators.

Uses FastAPI TestClient with mocked provider dependency.
No network access or real exchange connections are made.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.factory import get_active_provider
from backend.app.data.providers.exceptions import (
    ProviderError,
    ProviderNetworkError,
)


# ---------------------------------------------------------------------------
# Shared synthetic candle fixture
# ---------------------------------------------------------------------------

def _make_candles(n: int, start: float = 100.0, step: float = 0.5) -> list[dict]:
    candles = []
    close = start
    ts = 1_700_000_000_000
    for i in range(n):
        candles.append({
            "timestamp": ts + i * 3_600_000,
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 50.0,
        })
        close += step
    return candles


CANDLES_200 = _make_candles(200)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=BaseMarketDataProvider)
    provider.name = "Binance"
    provider.default_symbol = "BTC/USDT"
    provider.supported_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    provider.max_candle_limit = 1000
    provider.get_candles.return_value = CANDLES_200
    return provider


@pytest.fixture
def client(mock_provider):
    app.dependency_overrides[get_active_provider] = lambda: mock_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

class TestIndicatorEndpointStructure:
    def test_status_200(self, client):
        res = client.get("/api/v1/analysis/indicators")
        assert res.status_code == 200

    def test_top_level_keys(self, client):
        data = client.get("/api/v1/analysis/indicators").json()
        assert "exchange" in data
        assert "symbol" in data
        assert "timeframe" in data
        assert "candle_count" in data
        assert "latest" in data
        assert "series" in data

    def test_exchange_name(self, client):
        data = client.get("/api/v1/analysis/indicators").json()
        assert data["exchange"] == "Binance"

    def test_symbol_defaults_to_provider_default(self, client):
        data = client.get("/api/v1/analysis/indicators").json()
        assert data["symbol"] == "BTC/USDT"

    def test_candle_count_matches_series_length(self, client):
        data = client.get("/api/v1/analysis/indicators").json()
        assert data["candle_count"] == len(data["series"])

    def test_latest_has_all_indicator_keys(self, client):
        latest = client.get("/api/v1/analysis/indicators").json()["latest"]
        assert "sma_20" in latest
        assert "sma_50" in latest
        assert "ema_20" in latest
        assert "ema_50" in latest
        assert "rsi_14" in latest
        assert "macd" in latest
        assert "bollinger_bands" in latest
        assert "atr_14" in latest

    def test_macd_has_line_signal_histogram(self, client):
        macd = client.get("/api/v1/analysis/indicators").json()["latest"]["macd"]
        assert "line" in macd
        assert "signal" in macd
        assert "histogram" in macd

    def test_bollinger_has_upper_middle_lower(self, client):
        bb = client.get("/api/v1/analysis/indicators").json()["latest"]["bollinger_bands"]
        assert "upper" in bb
        assert "middle" in bb
        assert "lower" in bb

    def test_series_rows_have_timestamp_and_close(self, client):
        series = client.get("/api/v1/analysis/indicators").json()["series"]
        for row in series[:5]:
            assert "timestamp" in row
            assert "close" in row

    def test_warm_up_values_are_null_in_json(self, client):
        series = client.get("/api/v1/analysis/indicators").json()["series"]
        # First 19 SMA-20 must be null
        for row in series[:19]:
            assert row["sma_20"] is None

    def test_sma_values_finite_after_warmup(self, client):
        series = client.get("/api/v1/analysis/indicators").json()["series"]
        for row in series[20:]:
            assert row["sma_20"] is not None

    def test_latest_sma_20_is_finite(self, client):
        latest = client.get("/api/v1/analysis/indicators").json()["latest"]
        assert latest["sma_20"] is not None
        assert math.isfinite(latest["sma_20"])

    def test_macd_histogram_coherence(self, client):
        series = client.get("/api/v1/analysis/indicators").json()["series"]
        for row in series:
            m = row["macd"]
            if m["line"] is not None and m["signal"] is not None:
                assert m["histogram"] == pytest.approx(m["line"] - m["signal"], abs=1e-4)


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------

class TestIndicatorEndpointValidation:
    def test_invalid_timeframe_returns_400(self, client):
        res = client.get("/api/v1/analysis/indicators?timeframe=2h")
        assert res.status_code == 400
        assert "Unsupported timeframe" in res.json()["detail"]

    def test_limit_below_minimum_returns_422(self, client):
        res = client.get("/api/v1/analysis/indicators?limit=10")
        assert res.status_code == 422

    def test_limit_above_maximum_returns_422(self, client):
        res = client.get("/api/v1/analysis/indicators?limit=1001")
        assert res.status_code == 422

    def test_custom_symbol_passed_to_provider(self, client, mock_provider):
        client.get("/api/v1/analysis/indicators?symbol=ETH/USDT")
        mock_provider.get_candles.assert_called_once()
        call_kwargs = mock_provider.get_candles.call_args
        assert call_kwargs.kwargs["symbol"] == "ETH/USDT"

    def test_custom_timeframe_passed_to_provider(self, client, mock_provider):
        client.get("/api/v1/analysis/indicators?timeframe=4h")
        call_kwargs = mock_provider.get_candles.call_args
        assert call_kwargs.kwargs["timeframe"] == "4h"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

class TestIndicatorEndpointErrors:
    def test_provider_network_error_returns_504(self, client, mock_provider):
        mock_provider.get_candles.side_effect = ProviderNetworkError(
            "Timeout reaching Binance."
        )
        res = client.get("/api/v1/analysis/indicators")
        assert res.status_code == 504

    def test_generic_provider_error_returns_502(self, client, mock_provider):
        mock_provider.get_candles.side_effect = ProviderError(
            "Exchange failure."
        )
        res = client.get("/api/v1/analysis/indicators")
        assert res.status_code == 502

    def test_empty_candle_response_returns_422(self, client, mock_provider):
        mock_provider.get_candles.return_value = []
        res = client.get("/api/v1/analysis/indicators")
        assert res.status_code == 422

    def test_single_candle_response_returns_422(self, client, mock_provider):
        mock_provider.get_candles.return_value = _make_candles(1)
        res = client.get("/api/v1/analysis/indicators")
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Dependency injection: switching to Kraken provider
# ---------------------------------------------------------------------------

class TestIndicatorEndpointWithKrakenProvider:
    def test_kraken_provider_injection(self):
        kraken_candles = _make_candles(200, start=94000.0, step=0.3)
        kraken_provider = MagicMock(spec=BaseMarketDataProvider)
        kraken_provider.name = "Kraken"
        kraken_provider.default_symbol = "BTC/USD"
        kraken_provider.supported_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "2w"]
        kraken_provider.max_candle_limit = 720
        kraken_provider.get_candles.return_value = kraken_candles

        app.dependency_overrides[get_active_provider] = lambda: kraken_provider
        try:
            with TestClient(app) as c:
                res = c.get("/api/v1/analysis/indicators")
            assert res.status_code == 200
            data = res.json()
            assert data["exchange"] == "Kraken"
            assert data["symbol"] == "BTC/USD"
        finally:
            app.dependency_overrides.clear()
