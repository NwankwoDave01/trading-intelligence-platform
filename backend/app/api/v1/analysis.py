"""
Technical Analysis API route.

GET /api/v1/analysis/indicators

Retrieves OHLCV candles from the active market data provider, delegates
indicator calculation to the analysis service, and returns a fully-structured
JSON response.  All exchange connectivity is handled by the existing provider
abstraction — this module contains no exchange-specific logic.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
import ccxt

from backend.app.analysis.service import calculate_indicators, MIN_CANDLES
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
from backend.app.schemas.analysis import IndicatorResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analysis",
    tags=["Technical Analysis"],
)

# Candle limit bounds for the analysis endpoint
_ANALYSIS_MIN_LIMIT = 50
_ANALYSIS_MAX_LIMIT = 1000


def _handle_provider_exception(exc: Exception, exchange_name: str) -> None:
    """Re-use the same safe HTTP-mapping logic as the market routes."""
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
            detail=f"Unable to retrieve market data from {exchange_name}.",
        )
    else:
        logger.error("Unexpected error in analysis endpoint: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected internal error occurred.")


@router.get(
    "/indicators",
    response_model=IndicatorResponse,
    summary="Calculate technical indicators",
    description=(
        "Retrieves OHLCV candles from the active exchange provider and returns "
        "timestamp-aligned technical indicator series plus the latest indicator "
        "values.  Warm-up positions where insufficient history exists are "
        "represented as **null** in the JSON response."
    ),
)
def get_indicators(
    symbol: Optional[str] = Query(
        default=None,
        description="Trading pair (e.g. BTC/USDT for Binance, BTC/USD for Kraken). "
                    "Defaults to the active provider's default pair.",
    ),
    timeframe: str = Query(
        default="1h",
        description="Candle interval (e.g. 1m, 5m, 15m, 30m, 1h, 4h, 1d).",
    ),
    limit: int = Query(
        default=200,
        ge=_ANALYSIS_MIN_LIMIT,
        le=_ANALYSIS_MAX_LIMIT,
        description=(
            f"Number of historical candles to retrieve ({_ANALYSIS_MIN_LIMIT}–"
            f"{_ANALYSIS_MAX_LIMIT}).  "
            "Kraken's public OHLC API caps single requests at 720 candles."
        ),
    ),
    provider: BaseMarketDataProvider = Depends(get_active_provider),
) -> IndicatorResponse:
    """
    Calculate all technical indicators for the requested market and timeframe.

    Returned indicators:
    - **SMA** 20 and 50 periods
    - **EMA** 20 and 50 periods
    - **RSI** 14 periods (Wilder smoothing)
    - **MACD** (12/26/9) — line, signal, histogram
    - **Bollinger Bands** (20, 2σ population std, ddof=0) — upper, middle, lower
    - **ATR** 14 periods (Wilder smoothing)
    """
    target_symbol = symbol or provider.default_symbol

    # Validate timeframe against provider-supported intervals
    if timeframe not in provider.supported_timeframes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported timeframe '{timeframe}' for {provider.name}. "
                f"Supported: {', '.join(provider.supported_timeframes)}."
            ),
        )

    if limit > provider.max_candle_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested limit {limit} exceeds maximum allowed of "
                f"{provider.max_candle_limit} for {provider.name}."
            ),
        )

    # --- Fetch candles ---
    try:
        candles = provider.get_candles(
            symbol=target_symbol,
            timeframe=timeframe,
            limit=limit,
        )
    except Exception as exc:
        _handle_provider_exception(exc, provider.name)

    if len(candles) < MIN_CANDLES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Insufficient candle data: received {len(candles)} candle(s), "
                f"need at least {MIN_CANDLES}."
            ),
        )

    # --- Calculate indicators ---
    try:
        result = calculate_indicators(candles)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return IndicatorResponse(
        exchange=provider.name,
        symbol=target_symbol,
        timeframe=timeframe,
        candle_count=result["candle_count"],
        latest=result["latest"],
        series=result["series"],
    )
