"""Close-confirmed structural breaks with one event per source pivot."""

from __future__ import annotations

from typing import Any

from backend.app.analysis.market_structure.trend import classify_trend


def detect_breaks(
    candles: list[dict[str, Any]],
    swings: list[dict[str, Any]],
    break_buffer: float,
    timeframe_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    potential: list[dict[str, Any]] = []
    broken: set[tuple[str, str]] = set()
    previous_close: float | None = None

    for index, candle in enumerate(candles):
        known = [swing for swing in swings if swing["confirmation_index"] < index]
        trend = classify_trend(known)
        if trend in ("bullish", "bearish"):
            for swing_type, direction in (
                ("high", "bullish"),
                ("low", "bearish"),
            ):
                candidates = [s for s in known if s["swing_type"] == swing_type]
                if not candidates:
                    continue
                source = candidates[-1]
                level = source["price"]
                threshold = level + break_buffer if direction == "bullish" else level - break_buffer
                close = float(candle["close"])
                wick = float(candle["high"] if direction == "bullish" else candle["low"])
                if direction == "bullish":
                    close_crossed = previous_close is not None and previous_close <= threshold < close
                else:
                    close_crossed = previous_close is not None and previous_close >= threshold > close
                key = (source["id"], direction)
                kind = "BOS" if direction == trend else "CHoCH"
                if direction == "bullish":
                    wick_crossed = previous_close is not None and previous_close <= threshold and wick > threshold
                else:
                    wick_crossed = previous_close is not None and previous_close >= threshold and wick < threshold
                if close_crossed and key not in broken:
                    events.append({
                        "id": f"{kind.lower()}:{source['id']}:{index}",
                        "event_type": kind,
                        "direction": direction,
                        "broken_level": level,
                        "source_swing_id": source["id"],
                        "source_swing_timestamp": source["timestamp"],
                        "confirmation_candle_timestamp": int(candle["timestamp"]),
                        "confirmation_close": close,
                        "available_at": int(candle["timestamp"]) + timeframe_ms,
                    })
                    broken.add(key)
                elif index == len(candles) - 1 and previous_close is not None and wick_crossed:
                    if not close_crossed and key not in broken:
                        potential.append({
                            "id": f"potential:{source['id']}:{index}",
                            "event_type": kind,
                            "direction": direction,
                            "broken_level": level,
                            "source_swing_id": source["id"],
                            "source_swing_timestamp": source["timestamp"],
                            "observation_candle_timestamp": int(candle["timestamp"]),
                            "observation_close": close,
                            "wick_extreme": wick,
                            "available_at": int(candle["timestamp"]) + timeframe_ms,
                            "status": "unconfirmed",
                        })
        previous_close = float(candle["close"])
    return events, potential
