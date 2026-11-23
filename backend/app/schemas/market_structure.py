"""Typed responses for the market structure analysis API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


SwingClassification = Literal["HH", "HL", "LH", "LL"]
TrendClassification = Literal["bullish", "bearish", "ranging", "undetermined"]
BreakType = Literal["BOS", "CHoCH"]
BreakDirection = Literal["bullish", "bearish"]


class SwingPoint(BaseModel):
    id: str
    swing_type: Literal["high", "low"]
    timestamp: int = Field(description="Pivot candle open time in milliseconds")
    price: float
    confirmation_candle_timestamp: int = Field(description="Open timestamp of the rightmost candle needed to confirm the pivot")
    available_at: int = Field(description="Estimated close time of the confirmation candle; first available to strategies")
    confirmation_delay_bars: int
    classification: Optional[SwingClassification] = None
    reference_swing_id: Optional[str] = None


class TrendState(BaseModel):
    classification: TrendClassification
    as_of: int = Field(description="Timestamp through which confirmed swing structure was evaluated")


class BreakEvent(BaseModel):
    id: str
    event_type: BreakType
    direction: BreakDirection
    broken_level: float
    source_swing_id: str
    source_swing_timestamp: int
    confirmation_candle_timestamp: int
    confirmation_close: float
    available_at: int


class PotentialBreak(BaseModel):
    id: str
    event_type: BreakType
    direction: BreakDirection
    broken_level: float
    source_swing_id: str
    source_swing_timestamp: int
    observation_candle_timestamp: int
    observation_close: float
    wick_extreme: float
    available_at: int
    status: Literal["unconfirmed"]


class StructureZone(BaseModel):
    zone_type: Literal["support", "resistance"]
    lower_bound: float
    upper_bound: float
    midpoint: float
    tolerance: float
    contributing_swings: int
    source_swing_ids: list[str]
    source_timestamps: list[int]
    confirmation_timestamps: list[int]
    first_available_at: int
    last_available_at: int


class MarketStructureConfiguration(BaseModel):
    left_bars: int
    right_bars: int
    break_buffer: float
    level_tolerance: float
    break_confirmation: Literal["candle_close"]
    tie_handling: str


class MarketStructureResponse(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    candle_count: int
    as_of: int
    trend: TrendState
    confirmed_swings: list[SwingPoint]
    break_events: list[BreakEvent]
    potential_breaks: list[PotentialBreak]
    zones: list[StructureZone]
    configuration: MarketStructureConfiguration
