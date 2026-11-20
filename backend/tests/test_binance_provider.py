"""
Tests for BinanceMarketData provider and backward compatibility.
Requires zero external network access.
"""

from unittest.mock import MagicMock
import ccxt
import pytest

from backend.app.data.providers.binance import BinanceMarketData, market_data
from backend.app.data.providers.exceptions import ProviderError, ProviderInvalidParameterError


@pytest.fixture
def mock_exchange():
    exchange = MagicMock(spec=ccxt.binance)
    exchange.id = "binance"
    return exchange


@pytest.fixture
def binance_provider(mock_exchange):
    return BinanceMarketData(exchange=mock_exchange)


def test_binance_metadata(binance_provider):
    metadata = binance_provider.get_metadata()
    assert metadata["exchange"] == "Binance"
    assert metadata["status"] == "ready"
    assert metadata["default_symbol"] == "BTC/USDT"
    assert metadata["max_candle_limit"] == 1000


def test_binance_get_ticker(binance_provider, mock_exchange):
    mock_exchange.fetch_ticker.return_value = {
        "datetime": "2026-11-20T08:00:00.000Z",
        "last": 92600.0,
        "bid": 92595.0,
        "ask": 92605.0,
        "high": 93100.0,
        "low": 91200.0,
        "baseVolume": 45000.0,
        "percentage": 1.8,
    }

    ticker = binance_provider.get_ticker()
    mock_exchange.fetch_ticker.assert_called_once_with("BTC/USDT")
    assert ticker["exchange"] == "Binance"
    assert ticker["symbol"] == "BTC/USDT"
    assert ticker["last_price"] == 92600.0


def test_binance_get_candles(binance_provider, mock_exchange):
    mock_exchange.fetch_ohlcv.return_value = [
        [1700000000000, 92000.0, 92500.0, 91500.0, 92400.0, 310.0],
    ]

    candles = binance_provider.get_candles(limit=50)
    mock_exchange.fetch_ohlcv.assert_called_once_with(
        "BTC/USDT",
        timeframe="1h",
        limit=50,
    )
    assert len(candles) == 1
    assert candles[0]["open"] == 92000.0


def test_binance_backward_compatibility():
    """Verify that existing code importing `market_data` singleton still works."""
    assert isinstance(market_data, BinanceMarketData)
    assert market_data.name == "Binance"
    assert market_data.default_symbol == "BTC/USDT"
