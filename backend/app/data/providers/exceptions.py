"""
Provider-specific domain exceptions for market data exchanges.
Decouples exchange-specific errors (e.g., CCXT errors) from API presentation layers.
"""

class ProviderError(Exception):
    """Base exception for all market data provider errors."""
    def __init__(self, message: str, exchange: str | None = None):
        super().__init__(message)
        self.message = message
        self.exchange = exchange


class ProviderNetworkError(ProviderError):
    """Raised when a network timeout, connection drop, or unreachable host occurs."""
    pass


class ProviderSymbolNotFoundError(ProviderError):
    """Raised when a requested trading symbol is not found or unsupported."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when an exchange rate limit has been exceeded."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when the exchange API is temporarily down or in maintenance."""
    pass


class ProviderInvalidParameterError(ProviderError):
    """Raised when a query parameter (e.g. timeframe or candle limit) is invalid."""
    pass
