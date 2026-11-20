"""
Market data API routes for ticker and historical OHLCV candles.
Decoupled from specific exchanges via BaseMarketDataProvider dependency injection.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import ccxt

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

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/market",
    tags=["Market Data"]
)


def _handle_provider_exception(exc: Exception, exchange_name: str) -> None:
    """
    Safely map internal provider exceptions to standard HTTP status codes.
    Prevents leaking raw traces, internal hosts, or credentials to clients.
    """
    if isinstance(exc, ProviderInvalidParameterError):
        raise HTTPException(status_code=400, detail=exc.message)
    elif isinstance(exc, ProviderSymbolNotFoundError):
        raise HTTPException(status_code=404, detail=exc.message)
    elif isinstance(exc, ProviderRateLimitError):
        raise HTTPException(status_code=429, detail=exc.message)
    elif isinstance(exc, ProviderNetworkError):
        raise HTTPException(status_code=504, detail=exc.message)
    elif isinstance(exc, ProviderUnavailableError):
        raise HTTPException(status_code=503, detail=exc.message)
    elif isinstance(exc, (ProviderError, ccxt.BaseError)):
        logger.warning("Exchange error from %s: %s", exchange_name, str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"Unable to retrieve market data from {exchange_name}."
        )
    else:
        logger.error("Unexpected error in market endpoint: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal error occurred."
        )


@router.get("/provider")
def get_provider_metadata(
    provider: BaseMarketDataProvider = Depends(get_active_provider),
):
    """
    Retrieve metadata, capabilities, and configuration of the active exchange provider.
    Does NOT invoke external exchange network endpoints.
    """
    return provider.get_metadata()


@router.get("/ticker")
def get_market_ticker(
    symbol: Optional[str] = Query(
        default=None,
        description="Trading pair symbol (e.g. BTC/USD for Kraken, BTC/USDT for Binance). Defaults to the active exchange's default pair.",
    ),
    provider: BaseMarketDataProvider = Depends(get_active_provider),
):
    """
    Retrieve 24-hour ticker statistics for the specified or default trading pair.
    """
    target_symbol = symbol or provider.default_symbol
    try:
        return provider.get_ticker(target_symbol)
    except Exception as exc:
        _handle_provider_exception(exc, provider.name)


@router.get("/candles")
def get_market_candles(
    symbol: Optional[str] = Query(
        default=None,
        description="Trading pair symbol. Defaults to the active exchange's default pair.",
    ),
    timeframe: str = Query(
        default="1h",
        description="Candlestick interval (e.g. 1m, 5m, 15m, 30m, 1h, 4h, 1d).",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Number of candles to retrieve (Kraken public OHLC API returns a maximum of 720 candles).",
    ),
    provider: BaseMarketDataProvider = Depends(get_active_provider),
):
    """
    Retrieve historical OHLCV candlestick data from the active exchange.
    Respects provider-specific limits (e.g. Kraken maximum 720 candles).
    """
    target_symbol = symbol or provider.default_symbol

    # Validate timeframe against active provider's supported intervals
    if timeframe not in provider.supported_timeframes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported timeframe '{timeframe}' for {provider.name}. "
                f"Supported timeframes: {', '.join(provider.supported_timeframes)}."
            ),
        )

    # Validate limit against active provider's historical limit
    if limit > provider.max_candle_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested limit {limit} exceeds maximum allowed of "
                f"{provider.max_candle_limit} for {provider.name}."
            ),
        )

    try:
        candles = provider.get_candles(
            symbol=target_symbol,
            timeframe=timeframe,
            limit=limit,
        )

        return {
            "exchange": provider.name,
            "symbol": target_symbol,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles,
        }
    except Exception as exc:
        _handle_provider_exception(exc, provider.name)
