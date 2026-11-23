"""
Pydantic response schemas for the Technical Analysis API.

Keeping schemas separate from route logic allows independent documentation
and reuse across future API versions.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class MACDValues(BaseModel):
    line: Optional[float] = Field(None, description="MACD line (EMA fast − EMA slow)")
    signal: Optional[float] = Field(None, description="Signal line (EMA of MACD line)")
    histogram: Optional[float] = Field(None, description="MACD histogram (line − signal)")


class BollingerBandValues(BaseModel):
    upper: Optional[float] = Field(None, description="Upper band (middle + 2σ)")
    middle: Optional[float] = Field(None, description="Middle band (SMA 20)")
    lower: Optional[float] = Field(None, description="Lower band (middle − 2σ)")


class LatestIndicators(BaseModel):
    sma_20: Optional[float] = Field(None, description="Simple Moving Average, 20 periods")
    sma_50: Optional[float] = Field(None, description="Simple Moving Average, 50 periods")
    ema_20: Optional[float] = Field(None, description="Exponential Moving Average, 20 periods")
    ema_50: Optional[float] = Field(None, description="Exponential Moving Average, 50 periods")
    rsi_14: Optional[float] = Field(None, description="Relative Strength Index, 14 periods (Wilder smoothing)")
    macd: MACDValues = Field(default_factory=MACDValues, description="MACD indicator values")
    bollinger_bands: BollingerBandValues = Field(
        default_factory=BollingerBandValues, description="Bollinger Bands (period 20, 2σ sample std)"
    )
    atr_14: Optional[float] = Field(None, description="Average True Range, 14 periods (Wilder smoothing)")


class CandleIndicatorRow(BaseModel):
    timestamp: int = Field(..., description="Candle open timestamp in milliseconds (Unix epoch)")
    close: float = Field(..., description="Candle close price")
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: MACDValues = Field(default_factory=MACDValues)
    bollinger_bands: BollingerBandValues = Field(default_factory=BollingerBandValues)
    atr_14: Optional[float] = None


class IndicatorResponse(BaseModel):
    exchange: str = Field(..., description="Exchange name (e.g. Binance, Kraken)")
    symbol: str = Field(..., description="Trading pair (e.g. BTC/USDT)")
    timeframe: str = Field(..., description="Candle interval (e.g. 1h)")
    candle_count: int = Field(..., description="Number of candles used for calculation")
    latest: LatestIndicators = Field(..., description="Most-recent indicator values for dashboard display")
    series: list[CandleIndicatorRow] = Field(
        ...,
        description=(
            "Timestamp-aligned indicator history. Warm-up positions where "
            "insufficient data exists are represented as null."
        ),
    )
