"""Deterministic, explainable signal scoring over existing analysis outputs."""
from __future__ import annotations

from typing import Any

from backend.app.analysis.market_structure.service import timeframe_to_milliseconds

# Explicit directional contributions; totals are capped at +/- 12. A directional
# signal requires aligned structure and at least three independent confirmations.
WEIGHTS = {"trend": 3, "ema_alignment": 2, "price_vs_ema20": 1, "macd": 2, "rsi": 1, "recent_break": 2, "zone_context": 1}
BUY_THRESHOLD = 6
SELL_THRESHOLD = -6
MIN_HISTORY = 50
EVENT_RECENCY_BARS = 12


def generate_signal(*, symbol: str, timeframe: str, candles: list[dict[str, Any]], indicators: dict[str, Any], structure: dict[str, Any], generated_at: int) -> dict[str, Any]:
    if len(candles) < MIN_HISTORY:
        return _wait(symbol, timeframe, candles, indicators, structure, generated_at, ["INSUFFICIENT_HISTORY"], 0)
    duration_ms = timeframe_to_milliseconds(timeframe)
    latest_available = int(candles[-1]["timestamp"]) + duration_ms
    if generated_at >= latest_available and generated_at - latest_available > 2 * duration_ms:
        return _wait(symbol, timeframe, candles, indicators, structure, generated_at, ["STALE_CANDLES"], 0)
    close = float(candles[-1]["close"])
    latest = indicators["latest"]
    trend = structure["trend"]["classification"]
    values = [latest.get("ema_20"), latest.get("ema_50"), latest.get("rsi_14"), latest.get("macd", {}).get("line"), latest.get("macd", {}).get("signal"), latest.get("macd", {}).get("histogram")]
    if any(value is None for value in values):
        return _wait(symbol, timeframe, candles, indicators, structure, generated_at, ["INDICATOR_WARMUP"], 0)
    components: dict[str, int] = {}
    reasons: list[str] = []
    if trend in ("bullish", "bearish"):
        components["trend"] = WEIGHTS["trend"] * (1 if trend == "bullish" else -1)
        reasons.append("STRUCTURE_BULLISH" if trend == "bullish" else "STRUCTURE_BEARISH")
    else:
        return _wait(symbol, timeframe, candles, indicators, structure, generated_at, ["STRUCTURE_" + trend.upper()], 0)
    direction = 1 if trend == "bullish" else -1
    if (latest["ema_20"] > latest["ema_50"]) == (direction > 0):
        components["ema_alignment"] = direction * WEIGHTS["ema_alignment"]; reasons.append("EMA_ALIGNED")
    else:
        components["ema_alignment"] = -direction * WEIGHTS["ema_alignment"]; reasons.append("EMA_CONFLICT")
    if (close > latest["ema_20"]) == (direction > 0):
        components["price_vs_ema20"] = direction * WEIGHTS["price_vs_ema20"]; reasons.append("PRICE_ALIGNED_WITH_EMA20")
    else:
        components["price_vs_ema20"] = -direction * WEIGHTS["price_vs_ema20"]; reasons.append("PRICE_CONFLICTS_WITH_EMA20")
    macd = latest["macd"]
    macd_up = macd["line"] > macd["signal"] and macd["histogram"] > 0
    macd_down = macd["line"] < macd["signal"] and macd["histogram"] < 0
    components["macd"] = direction * WEIGHTS["macd"] if (macd_up if direction > 0 else macd_down) else -direction * WEIGHTS["macd"]
    reasons.append("MACD_CONFIRMS" if components["macd"] > 0 else "MACD_CONFLICT")
    rsi = latest["rsi_14"]
    rsi_supports = (direction > 0 and 50 <= rsi < 70) or (direction < 0 and 30 < rsi <= 50)
    rsi_extreme = (direction > 0 and rsi >= 70) or (direction < 0 and rsi <= 30)
    components["rsi"] = direction * WEIGHTS["rsi"] if rsi_supports else (0 if rsi_extreme else -direction * WEIGHTS["rsi"])
    reasons.append("RSI_SUPPORTS_MOMENTUM" if rsi_supports else "RSI_OVEREXTENDED" if rsi_extreme else "RSI_CONFLICT")
    latest_available = int(candles[-1]["timestamp"]) + timeframe_to_milliseconds(timeframe)
    recent_events = [e for e in structure["break_events"] if e["available_at"] <= latest_available and latest_available - e["available_at"] <= EVENT_RECENCY_BARS * timeframe_to_milliseconds(timeframe)]
    aligned = [e for e in recent_events if e["direction"] == trend]
    conflicting = [e for e in recent_events if e["direction"] != trend]
    components["recent_break"] = direction * WEIGHTS["recent_break"] if aligned else (-direction * WEIGHTS["recent_break"] if conflicting else 0)
    if aligned: reasons.append("RECENT_STRUCTURE_BREAK")
    elif conflicting: reasons.append("RECENT_OPPOSING_STRUCTURE_BREAK")
    else: reasons.append("NO_RECENT_STRUCTURE_BREAK")
    opposing_zone = "resistance" if direction > 0 else "support"
    favorable_zone = "support" if direction > 0 else "resistance"
    zone_context = 0
    for zone in structure["zones"]:
        distance = max(0.0, zone["lower_bound"] - close, close - zone["upper_bound"])
        if distance / close <= 0.01:
            if zone["zone_type"] == opposing_zone: zone_context = -direction * WEIGHTS["zone_context"]
            elif zone["zone_type"] == favorable_zone and zone_context == 0: zone_context = direction * WEIGHTS["zone_context"]
    components["zone_context"] = zone_context
    reasons.append("NEAR_OPPOSING_ZONE" if zone_context * direction < 0 else "NEAR_FAVORABLE_ZONE" if zone_context else "NO_NEARBY_ZONE")
    score = sum(components.values())
    confirmations = sum(1 for name, value in components.items() if name != "trend" and value * direction > 0)
    conflicts = any(value * direction < 0 for value in components.values())
    signal = "BUY" if direction > 0 and score >= BUY_THRESHOLD and confirmations >= 3 and not conflicts else "SELL" if direction < 0 and score <= SELL_THRESHOLD and confirmations >= 3 and not conflicts else "WAIT"
    if signal == "WAIT": reasons.append("MIXED_EVIDENCE_OR_BELOW_THRESHOLD")
    observations = {"close": close, "ema_20": latest["ema_20"], "ema_50": latest["ema_50"], "rsi_14": rsi, "macd": macd, "support_resistance_zones": structure["zones"]}
    return {"symbol": symbol, "timeframe": timeframe, "signal": signal, "direction": "BULLISH" if signal == "BUY" else "BEARISH" if signal == "SELL" else "NEUTRAL", "score": score, "score_scale": [-12, 12], "strength": "strong" if abs(score) >= 8 and signal != "WAIT" else "moderate" if signal != "WAIT" else "none", "evaluation_timestamp": latest_available, "generated_at": generated_at, "trend": trend, "indicator_observations": observations, "structural_observations": {"recent_breaks": recent_events, "confirmed_swings": [s for s in structure["confirmed_swings"] if s["available_at"] <= latest_available]}, "reason_codes": reasons, "explanation": f"{signal}: structure is {trend}; weighted alignment score {score} on a -12 to +12 scale. This score is not a probability."}


def _wait(symbol, timeframe, candles, indicators, structure, generated_at, reasons, score):
    evaluation = int(candles[-1]["timestamp"]) if candles else generated_at
    return {"symbol": symbol, "timeframe": timeframe, "signal": "WAIT", "direction": "NEUTRAL", "score": score, "score_scale": [-12, 12], "strength": "none", "evaluation_timestamp": evaluation, "generated_at": generated_at, "trend": structure.get("trend", {}).get("classification", "undetermined"), "indicator_observations": indicators.get("latest", {}), "structural_observations": {"recent_breaks": [], "confirmed_swings": []}, "reason_codes": reasons, "explanation": "WAIT: required market context or indicator history is unavailable; no directional inference was made."}
