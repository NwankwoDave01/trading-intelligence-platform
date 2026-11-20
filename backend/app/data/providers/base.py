"""
Base market data provider interface and abstract adapter.
Defines normalized contracts for exchange integration.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import ccxt

from backend.app.data.providers.exceptions import (
    ProviderError,
    ProviderInvalidParameterError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderUnavailableError,
)


class BaseMarketDataProvider(ABC):
    """
    Abstract adapter for cryptocurrency exchange market data providers.
    All exchange providers must implement this interface to ensure a
    consistent normalized contract across ticker and candle data.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable exchange name (e.g. 'Kraken', 'Binance')."""
        pass

    @property
    @abstractmethod
    def default_symbol(self) -> str:
        """Default trading pair symbol (e.g. 'BTC/USD' for Kraken, 'BTC/USDT' for Binance)."""
        pass

    @property
    @abstractmethod
    def supported_timeframes(self) -> List[str]:
        """List of supported OHLCV candlestick timeframes."""
        pass

    @property
    @abstractmethod
    def max_candle_limit(self) -> int:
        """Maximum number of candles allowed per OHLCV request."""
        pass

    @abstractmethod
    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch 24-hour ticker data for the specified symbol.
        Returns a normalized ticker dictionary.
        """
        pass

    @abstractmethod
    def get_candles(
        self,
        symbol: Optional[str] = None,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical OHLCV candlestick data.
        Returns a list of normalized candle dictionaries.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return provider configuration and capabilities metadata.
        Does NOT perform external network calls.
        """
        return {
            "exchange": self.name,
            "status": "ready",
            "default_symbol": self.default_symbol,
            "supported_timeframes": self.supported_timeframes,
            "max_candle_limit": self.max_candle_limit,
            "rate_limit_enabled": True,
        }

    def validate_symbol(self, symbol: Optional[str]) -> str:
        """
        Validate and resolve symbol, falling back to default_symbol if None or empty.
        """
        if not symbol or not symbol.strip():
            return self.default_symbol
        cleaned = symbol.strip().upper()
        if "/" not in cleaned or len(cleaned) < 3:
            raise ProviderInvalidParameterError(
                f"Invalid symbol format '{symbol}'. Expected standard pair format (e.g. 'BTC/USD').",
                exchange=self.name,
            )
        return cleaned

    def validate_timeframe(self, timeframe: str) -> str:
        """
        Validate that the requested timeframe is supported by this exchange.
        """
        if timeframe not in self.supported_timeframes:
            raise ProviderInvalidParameterError(
                f"Unsupported timeframe '{timeframe}' for {self.name}. "
                f"Supported timeframes: {', '.join(self.supported_timeframes)}.",
                exchange=self.name,
            )
        return timeframe

    def validate_limit(self, limit: int) -> int:
        """
        Validate that the requested candle limit is within the exchange bounds.
        """
        if limit < 1 or limit > self.max_candle_limit:
            raise ProviderInvalidParameterError(
                f"Candle limit {limit} out of bounds for {self.name}. "
                f"Must be between 1 and {self.max_candle_limit}.",
                exchange=self.name,
            )
        return limit

    def translate_ccxt_error(self, e: Exception, symbol: Optional[str] = None) -> ProviderError:
        """
        Translate low-level CCXT or network exceptions into sanitized domain exceptions.
        Guarantees no raw traces, API keys, or internal network details are leaked.
        Order matters: specific CCXT error subclasses (RateLimit, ExchangeNotAvailable)
        must be checked before their base classes (NetworkError, ExchangeError).
        """
        if isinstance(e, ccxt.BadSymbol):
            return ProviderSymbolNotFoundError(
                f"Symbol '{symbol or 'unknown'}' not found or unsupported on {self.name}.",
                exchange=self.name,
            )
        if isinstance(e, (ccxt.RateLimitExceeded, ccxt.DDoSProtection)):
            return ProviderRateLimitError(
                f"Rate limit exceeded while contacting {self.name}. Please retry later.",
                exchange=self.name,
            )
        if isinstance(e, (ccxt.ExchangeNotAvailable, ccxt.OnMaintenance)):
            return ProviderUnavailableError(
                f"{self.name} is temporarily unavailable or undergoing maintenance.",
                exchange=self.name,
            )
        if isinstance(e, (ccxt.RequestTimeout, ccxt.NetworkError)):
            return ProviderNetworkError(
                f"Network timeout or connectivity failure while communicating with {self.name}.",
                exchange=self.name,
            )
        if isinstance(e, ccxt.BaseError):
            return ProviderError(
                f"Unable to retrieve market data from {self.name}.",
                exchange=self.name,
            )
        return ProviderError(
            f"An unexpected error occurred while querying {self.name}.",
            exchange=self.name,
        )
