"""Confirmed pivot detection and swing classification."""

from __future__ import annotations

from typing import Any


def detect_swings(
    candles: list[dict[str, Any]],
    left_bars: int,
    right_bars: int,
    timeframe_ms: int,
) -> list[dict[str, Any]]:
    """Detect strict pivots; ties are not pivots, and confirmation waits right bars."""
    if isinstance(left_bars, bool) or not isinstance(left_bars, int) or left_bars < 1:
        raise ValueError("left_bars must be a positive integer.")
    if isinstance(right_bars, bool) or not isinstance(right_bars, int) or right_bars < 1:
        raise ValueError("right_bars must be a positive integer.")

    swings: list[dict[str, Any]] = []
    previous: dict[str, dict[str, Any] | None] = {"high": None, "low": None}
    for pivot_index in range(left_bars, len(candles) - right_bars):
        left = candles[pivot_index - left_bars:pivot_index]
        right = candles[pivot_index + 1:pivot_index + right_bars + 1]
        high = float(candles[pivot_index]["high"])
        low = float(candles[pivot_index]["low"])
        candidates = (
            ("high", high, all(high > float(c["high"]) for c in (*left, *right))),
            ("low", low, all(low < float(c["low"]) for c in (*left, *right))),
        )
        for swing_type, price, is_pivot in candidates:
            if not is_pivot:
                continue
            confirmation_index = pivot_index + right_bars
            prior = previous[swing_type]
            classification = None
            if prior is not None:
                if swing_type == "high":
                    classification = "HH" if price > prior["price"] else "LH" if price < prior["price"] else None
                else:
                    classification = "HL" if price > prior["price"] else "LL" if price < prior["price"] else None
            swing = {
                "id": f"{swing_type}:{pivot_index}",
                "swing_type": swing_type,
                "timestamp": int(candles[pivot_index]["timestamp"]),
                "price": price,
                "pivot_index": pivot_index,
                "confirmation_candle_timestamp": int(candles[confirmation_index]["timestamp"]),
                "confirmation_index": confirmation_index,
                "available_at": int(candles[confirmation_index]["timestamp"]) + timeframe_ms,
                "confirmation_delay_bars": right_bars,
                "classification": classification,
                "reference_swing_id": prior["id"] if prior is not None else None,
            }
            swings.append(swing)
            previous[swing_type] = swing
    return sorted(swings, key=lambda point: (point["confirmation_index"], point["pivot_index"], point["swing_type"]))
