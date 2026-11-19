
from fastapi import APIRouter, HTTPException, Query
import ccxt

from backend.app.data.providers.binance import market_data

router = APIRouter(
    prefix="/market",
    tags=["Market Data"]
)

@router.get("/ticker")
def get_market_ticker(
    symbol: str = Query(
        default="BTC/USDT",
        description="Trading pair, e.g. BTC/USDT"
    )
):
    try:
        return market_data.get_ticker(symbol)

    except ccxt.BaseError:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve market ticker from Binance."
        )

@router.get("/candles")
def get_market_candles(
    symbol: str = Query(default="BTC/USDT"),
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    supported_timeframes = [
        "1m", "5m", "15m", "30m",
        "1h", "4h", "1d"
    ]

    if timeframe not in supported_timeframes:
        raise HTTPException(
            status_code=400,
            detail="Unsupported timeframe."
        )

    try:
        candles = market_data.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        return {
            "exchange": "Binance",
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles,
        }

    except ccxt.BaseError:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve historical market data from Binance."
        )