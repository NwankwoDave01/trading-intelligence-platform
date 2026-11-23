"""Deterministic trend classification from confirmed swing structure."""

from __future__ import annotations

from typing import Any


def classify_trend(swings: list[dict[str, Any]]) -> str:
    """Bull/bear requires the latest comparable high and low to agree."""
    highs = [point for point in swings if point["swing_type"] == "high" and point["classification"]]
    lows = [point for point in swings if point["swing_type"] == "low" and point["classification"]]
    if not highs or not lows:
        return "undetermined"
    latest_high = highs[-1]["classification"]
    latest_low = lows[-1]["classification"]
    if latest_high == "HH" and latest_low == "HL":
        return "bullish"
    if latest_high == "LH" and latest_low == "LL":
        return "bearish"
    return "ranging"
