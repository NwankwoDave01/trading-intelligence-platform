"""Pure market structure calculations over normalized OHLCV candles."""

from __future__ import annotations

import math
import re
from numbers import Real
from typing import Any

from backend.app.analysis.service import _extract_ohlcv
from backend.app.analysis.market_structure.breaks import detect_breaks
from backend.app.analysis.market_structure.levels import cluster_levels
from backend.app.analysis.market_structure.swings import detect_swings
from backend.app.analysis.market_structure.trend import classify_trend

_TIMEFRAME_UNITS_MS = {"s": 1_000, "m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}


def timeframe_to_milliseconds(timeframe: str) -> int:
    match = re.fullmatch(r"([1-9]\d*)([smhdw])", timeframe)
    if not match:
        raise ValueError(f"Unsupported fixed-duration timeframe '{timeframe}'.")
    return int(match.group(1)) * _TIMEFRAME_UNITS_MS[match.group(2)]


def calculate_market_structure(
    candles: list[dict[str, Any]],
    timeframe: str = "1h",
    left_bars: int = 3,
    right_bars: int = 3,
    break_buffer: float = 0.0,
    level_tolerance: float = 0.0,
) -> dict[str, Any]:
    """Analyze structure using only pivots confirmed before each structural break."""
    _extract_ohlcv(candles)
    if isinstance(break_buffer, bool) or not isinstance(break_buffer, Real) or not math.isfinite(break_buffer) or break_buffer < 0:
        raise ValueError("break_buffer must be a finite non-negative number.")
    if isinstance(level_tolerance, bool) or not isinstance(level_tolerance, Real) or not math.isfinite(level_tolerance) or level_tolerance < 0:
        raise ValueError("level_tolerance must be a finite non-negative number.")
    timeframe_ms = timeframe_to_milliseconds(timeframe)
    swings = detect_swings(candles, left_bars, right_bars, timeframe_ms)
    events, potential = detect_breaks(candles, swings, float(break_buffer), timeframe_ms)
    latest_timestamp = int(candles[-1]["timestamp"]) + timeframe_ms
    return {
        "candle_count": len(candles),
        "as_of": latest_timestamp,
        "trend": {"classification": classify_trend(swings), "as_of": latest_timestamp},
        "confirmed_swings": swings,
        "break_events": events,
        "potential_breaks": potential,
        "zones": cluster_levels(swings, float(level_tolerance)),
        "configuration": {
            "left_bars": left_bars,
            "right_bars": right_bars,
            "break_buffer": float(break_buffer),
            "level_tolerance": float(level_tolerance),
            "break_confirmation": "candle_close",
            "tie_handling": "equal neighboring highs/lows disqualify a pivot",
        },
    }
