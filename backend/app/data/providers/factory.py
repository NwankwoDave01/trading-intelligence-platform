"""
Provider factory and registry.
Supports dynamic exchange selection and FastAPI dependency injection.
"""

from typing import Dict, Optional, Type

from backend.app.core.config import settings
from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.binance import BinanceMarketData
from backend.app.data.providers.kraken import KrakenMarketData
from backend.app.data.providers.exceptions import ProviderInvalidParameterError

PROVIDER_REGISTRY: Dict[str, Type[BaseMarketDataProvider]] = {
    "kraken": KrakenMarketData,
    "binance": BinanceMarketData,
}

_PROVIDER_INSTANCES: Dict[str, BaseMarketDataProvider] = {}


def get_market_data_provider(provider_name: Optional[str] = None) -> BaseMarketDataProvider:
    """
    Retrieve or instantiate a market data provider by name.
    If no name is provided, uses settings.active_provider (default: 'kraken').
    """
    key = (provider_name or settings.active_provider).strip().lower()

    if key not in PROVIDER_REGISTRY:
        supported = ", ".join(sorted(PROVIDER_REGISTRY.keys()))
        raise ProviderInvalidParameterError(
            f"Unsupported exchange provider '{key}'. Supported providers: {supported}."
        )

    if key not in _PROVIDER_INSTANCES:
        provider_class = PROVIDER_REGISTRY[key]
        _PROVIDER_INSTANCES[key] = provider_class(timeout_ms=settings.EXCHANGE_TIMEOUT_MS)

    return _PROVIDER_INSTANCES[key]


def get_active_provider() -> BaseMarketDataProvider:
    """
    FastAPI dependency for injecting the configured active market data provider.
    Can be easily overridden in tests via app.dependency_overrides[get_active_provider].
    """
    return get_market_data_provider()


def reset_provider_cache() -> None:
    """Clear cached provider instances (primarily for testing)."""
    _PROVIDER_INSTANCES.clear()
