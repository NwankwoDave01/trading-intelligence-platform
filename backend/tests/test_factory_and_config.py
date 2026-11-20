"""
Tests for provider factory, configuration, and exchange registry.
"""

import pytest

from backend.app.core.config import Settings
from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.binance import BinanceMarketData
from backend.app.data.providers.factory import (
    get_market_data_provider,
    reset_provider_cache,
)
from backend.app.data.providers.kraken import KrakenMarketData
from backend.app.data.providers.exceptions import ProviderInvalidParameterError


def setup_function():
    reset_provider_cache()


def test_default_provider_is_kraken():
    provider = get_market_data_provider()
    assert isinstance(provider, KrakenMarketData)
    assert provider.name == "Kraken"
    assert provider.default_symbol == "BTC/USD"


def test_get_binance_provider_explicit():
    provider = get_market_data_provider("binance")
    assert isinstance(provider, BinanceMarketData)
    assert provider.name == "Binance"
    assert provider.default_symbol == "BTC/USDT"


def test_case_insensitive_provider_selection():
    provider_upper = get_market_data_provider("KRAKEN")
    assert isinstance(provider_upper, KrakenMarketData)

    provider_mixed = get_market_data_provider("BinAnce")
    assert isinstance(provider_mixed, BinanceMarketData)


def test_unsupported_provider_raises_error():
    with pytest.raises(ProviderInvalidParameterError) as exc_info:
        get_market_data_provider("coinbase_pro")
    assert "Unsupported exchange provider 'coinbase_pro'" in str(exc_info.value)
    assert "Supported providers: binance, kraken" in str(exc_info.value)


def test_settings_active_provider_precedence():
    s1 = Settings(DEFAULT_PROVIDER="kraken")
    assert s1.active_provider == "kraken"

    s2 = Settings(DEFAULT_PROVIDER="kraken", MARKET_DATA_PROVIDER="binance")
    assert s2.active_provider == "binance"
