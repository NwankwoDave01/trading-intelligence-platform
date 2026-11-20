"""
Tests for KrakenMarketData provider using mocked exchange responses.
Requires zero external network access.
"""

from unittest.mock import MagicMock
import ccxt
import pytest

from backend.app.data.providers.kraken import KrakenMarketData
from backend.app.data.providers.exceptions import (
    ProviderError,
    ProviderInvalidParameterError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderUnavailableError,
)


@pytest.fixture
def mock_exchange():
    exchange = MagicMock(spec=ccxt.kraken)
    exchange.id = "kraken"
    return exchange


@pytest.fixture
def kraken_provider(mock_exchange):
    return KrakenMarketData(exchange=mock_exchange)


def test_kraken_metadata(kraken_provider):
    metadata = kraken_provider.get_metadata()
    assert metadata["exchange"] == "Kraken"
    assert metadata["status"] == "ready"
    assert metadata["default_symbol"] == "BTC/USD"
    assert "1h" in metadata["supported_timeframes"]
    assert metadata["max_candle_limit"] == 720
    assert metadata["rate_limit_enabled"] is True


def test_kraken_get_ticker_default_symbol(kraken_provider, mock_exchange):
    mock_exchange.fetch_ticker.return_value = {
        "datetime": "2026-11-20T08:00:00.000Z",
        "last": 92500.5,
        "bid": 92490.0,
        "ask": 92510.0,
        "high": 93000.0,
        "low": 91000.0,
        "baseVolume": 1540.25,
        "percentage": 2.45,
    }

    ticker = kraken_provider.get_ticker()

    mock_exchange.fetch_ticker.assert_called_once_with("BTC/USD")
    assert ticker == {
        "exchange": "Kraken",
        "symbol": "BTC/USD",
        "timestamp": "2026-11-20T08:00:00.000Z",
        "last_price": 92500.5,
        "bid": 92490.0,
        "ask": 92510.0,
        "high_24h": 93000.0,
        "low_24h": 91000.0,
        "volume_24h": 1540.25,
        "price_change_percentage": 2.45,
    }


def test_kraken_get_ticker_custom_symbol(kraken_provider, mock_exchange):
    mock_exchange.fetch_ticker.return_value = {
        "datetime": "2026-11-20T08:00:00.000Z",
        "last": 3400.0,
        "bid": 3399.0,
        "ask": 3401.0,
        "high": 3500.0,
        "low": 3300.0,
        "baseVolume": 8500.0,
        "percentage": -1.2,
    }

    ticker = kraken_provider.get_ticker("ETH/USD")

    mock_exchange.fetch_ticker.assert_called_once_with("ETH/USD")
    assert ticker["symbol"] == "ETH/USD"
    assert ticker["last_price"] == 3400.0


def test_kraken_get_candles_default_parameters(kraken_provider, mock_exchange):
    mock_exchange.fetch_ohlcv.return_value = [
        [1700000000000, 91000.0, 92000.0, 90500.0, 91800.0, 120.5],
        [1700003600000, 91800.0, 92600.0, 91700.0, 92500.0, 145.2],
    ]

    candles = kraken_provider.get_candles()

    mock_exchange.fetch_ohlcv.assert_called_once_with(
        "BTC/USD",
        timeframe="1h",
        limit=100,
    )
    assert len(candles) == 2
    assert candles[0] == {
        "timestamp": 1700000000000,
        "open": 91000.0,
        "high": 92000.0,
        "low": 90500.0,
        "close": 91800.0,
        "volume": 120.5,
    }


def test_kraken_invalid_symbol(kraken_provider):
    with pytest.raises(ProviderInvalidParameterError) as exc_info:
        kraken_provider.get_ticker("INVALID_NO_SLASH")
    assert "Invalid symbol format" in str(exc_info.value)


def test_kraken_unsupported_timeframe(kraken_provider):
    with pytest.raises(ProviderInvalidParameterError) as exc_info:
        kraken_provider.get_candles(timeframe="2h")
    assert "Unsupported timeframe '2h'" in str(exc_info.value)


def test_kraken_limit_bounds(kraken_provider):
    # Exceeding 720 should raise ProviderInvalidParameterError
    with pytest.raises(ProviderInvalidParameterError) as exc_info:
        kraken_provider.get_candles(limit=721)
    assert "out of bounds for Kraken" in str(exc_info.value)
    assert "720" in str(exc_info.value)

    # Limit 0 or negative
    with pytest.raises(ProviderInvalidParameterError):
        kraken_provider.get_candles(limit=0)


def test_kraken_symbol_not_found_translation(kraken_provider, mock_exchange):
    mock_exchange.fetch_ticker.side_effect = ccxt.BadSymbol("kraken does not have market symbol FOO/BAR")

    with pytest.raises(ProviderSymbolNotFoundError) as exc_info:
        kraken_provider.get_ticker("FOO/BAR")
    assert "FOO/BAR" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_kraken_network_error_translation(kraken_provider, mock_exchange):
    mock_exchange.fetch_ticker.side_effect = ccxt.NetworkError("Connection refused")

    with pytest.raises(ProviderNetworkError) as exc_info:
        kraken_provider.get_ticker()
    assert "Network timeout or connectivity failure" in str(exc_info.value)


def test_kraken_rate_limit_translation(kraken_provider, mock_exchange):
    mock_exchange.fetch_ticker.side_effect = ccxt.RateLimitExceeded("Too many calls")

    with pytest.raises(ProviderRateLimitError) as exc_info:
        kraken_provider.get_ticker()
    assert "Rate limit exceeded" in str(exc_info.value)


def test_kraken_unavailable_translation(kraken_provider, mock_exchange):
    mock_exchange.fetch_ticker.side_effect = ccxt.ExchangeNotAvailable("Maintenance")

    with pytest.raises(ProviderUnavailableError) as exc_info:
        kraken_provider.get_ticker()
    assert "temporarily unavailable" in str(exc_info.value)
