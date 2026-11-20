"""
Integration tests for FastAPI market data endpoints.
Uses FastAPI TestClient and mocked provider dependencies.
Zero external network calls required.
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.factory import get_active_provider
from backend.app.data.providers.exceptions import (
    ProviderError,
    ProviderInvalidParameterError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderUnavailableError,
)


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=BaseMarketDataProvider)
    provider.name = "Kraken"
    provider.default_symbol = "BTC/USD"
    provider.supported_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "2w"]
    provider.max_candle_limit = 720
    provider.get_metadata.return_value = {
        "exchange": "Kraken",
        "status": "ready",
        "default_symbol": "BTC/USD",
        "supported_timeframes": provider.supported_timeframes,
        "max_candle_limit": 720,
        "rate_limit_enabled": True,
    }
    return provider


@pytest.fixture
def client(mock_provider):
    app.dependency_overrides[get_active_provider] = lambda: mock_provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "running"


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_get_provider_metadata_endpoint(client, mock_provider):
    res = client.get("/api/v1/market/provider")
    assert res.status_code == 200
    data = res.json()
    assert data["exchange"] == "Kraken"
    assert data["default_symbol"] == "BTC/USD"
    assert data["max_candle_limit"] == 720


def test_get_ticker_default_symbol(client, mock_provider):
    mock_provider.get_ticker.return_value = {
        "exchange": "Kraken",
        "symbol": "BTC/USD",
        "timestamp": "2026-11-20T08:00:00Z",
        "last_price": 94000.0,
        "bid": 93990.0,
        "ask": 94010.0,
        "high_24h": 95000.0,
        "low_24h": 92000.0,
        "volume_24h": 1100.0,
        "price_change_percentage": 2.1,
    }

    res = client.get("/api/v1/market/ticker")
    assert res.status_code == 200
    mock_provider.get_ticker.assert_called_once_with("BTC/USD")
    assert res.json()["last_price"] == 94000.0


def test_get_ticker_custom_symbol(client, mock_provider):
    mock_provider.get_ticker.return_value = {
        "exchange": "Kraken",
        "symbol": "ETH/USD",
        "timestamp": "2026-11-20T08:00:00Z",
        "last_price": 3500.0,
        "bid": 3499.0,
        "ask": 3501.0,
        "high_24h": 3600.0,
        "low_24h": 3400.0,
        "volume_24h": 5000.0,
        "price_change_percentage": 0.5,
    }

    res = client.get("/api/v1/market/ticker?symbol=ETH/USD")
    assert res.status_code == 200
    mock_provider.get_ticker.assert_called_once_with("ETH/USD")
    assert res.json()["symbol"] == "ETH/USD"


def test_get_candles_default_parameters(client, mock_provider):
    mock_provider.get_candles.return_value = [
        {
            "timestamp": 1700000000000,
            "open": 93000.0,
            "high": 93500.0,
            "low": 92800.0,
            "close": 93400.0,
            "volume": 80.0,
        }
    ]

    res = client.get("/api/v1/market/candles")
    assert res.status_code == 200
    mock_provider.get_candles.assert_called_once_with(
        symbol="BTC/USD",
        timeframe="1h",
        limit=100,
    )
    data = res.json()
    assert data["exchange"] == "Kraken"
    assert data["symbol"] == "BTC/USD"
    assert data["count"] == 1
    assert len(data["candles"]) == 1


def test_get_candles_unsupported_timeframe(client, mock_provider):
    res = client.get("/api/v1/market/candles?timeframe=2h")
    assert res.status_code == 400
    assert "Unsupported timeframe '2h'" in res.json()["detail"]


def test_get_candles_exceeding_kraken_limit(client, mock_provider):
    res = client.get("/api/v1/market/candles?limit=721")
    assert res.status_code == 400
    assert "exceeds maximum allowed of 720" in res.json()["detail"]


def test_api_symbol_not_found_error(client, mock_provider):
    mock_provider.get_ticker.side_effect = ProviderSymbolNotFoundError(
        "Symbol 'NONEXISTENT' not found on Kraken."
    )

    res = client.get("/api/v1/market/ticker?symbol=NONEXISTENT")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_api_network_timeout_error(client, mock_provider):
    mock_provider.get_ticker.side_effect = ProviderNetworkError(
        "Network timeout communicating with Kraken."
    )

    res = client.get("/api/v1/market/ticker")
    assert res.status_code == 504
    assert "Network timeout" in res.json()["detail"]


def test_api_rate_limit_error(client, mock_provider):
    mock_provider.get_ticker.side_effect = ProviderRateLimitError(
        "Rate limit exceeded."
    )

    res = client.get("/api/v1/market/ticker")
    assert res.status_code == 429
    assert "Rate limit exceeded" in res.json()["detail"]


def test_api_exchange_unavailable_error(client, mock_provider):
    mock_provider.get_ticker.side_effect = ProviderUnavailableError(
        "Kraken is temporarily unavailable."
    )

    res = client.get("/api/v1/market/ticker")
    assert res.status_code == 503
    assert "temporarily unavailable" in res.json()["detail"]


def test_api_generic_exchange_error(client, mock_provider):
    mock_provider.get_ticker.side_effect = ProviderError(
        "Internal exchange failure."
    )

    res = client.get("/api/v1/market/ticker")
    assert res.status_code == 502
    assert "Unable to retrieve market data from Kraken." in res.json()["detail"]


def test_api_with_binance_provider_dependency():
    """Verify that the API routes dynamically adapt when Binance provider is injected."""
    binance_provider = MagicMock(spec=BaseMarketDataProvider)
    binance_provider.name = "Binance"
    binance_provider.default_symbol = "BTC/USDT"
    binance_provider.supported_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    binance_provider.max_candle_limit = 1000
    binance_provider.get_ticker.return_value = {
        "exchange": "Binance",
        "symbol": "BTC/USDT",
        "timestamp": "2026-11-20T08:00:00Z",
        "last_price": 93000.0,
        "bid": 92990.0,
        "ask": 93010.0,
        "high_24h": 94000.0,
        "low_24h": 91000.0,
        "volume_24h": 25000.0,
        "price_change_percentage": 1.2,
    }
    binance_provider.get_candles.return_value = [
        {"timestamp": 1700000000000, "open": 92000.0, "high": 92500.0, "low": 91500.0, "close": 92400.0, "volume": 500.0}
    ]

    app.dependency_overrides[get_active_provider] = lambda: binance_provider
    try:
        with TestClient(app) as client:
            # Ticker should default to BTC/USDT and Binance
            t_res = client.get("/api/v1/market/ticker")
            assert t_res.status_code == 200
            assert t_res.json()["exchange"] == "Binance"
            assert t_res.json()["symbol"] == "BTC/USDT"

            # Binance supports limits up to 1000
            c_res = client.get("/api/v1/market/candles?limit=1000")
            assert c_res.status_code == 200
            assert c_res.json()["exchange"] == "Binance"
            assert c_res.json()["count"] == 1
    finally:
        app.dependency_overrides.clear()

