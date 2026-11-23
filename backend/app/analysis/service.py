"""Validate normalized OHLCV candles and calculate aligned indicators."""

from __future__ import annotations

from numbers import Integral
from typing import Any

import numpy as np

from backend.app.analysis.indicators import (
    _safe_array, atr, bollinger_bands, ema, macd, rsi, sma,
)

MIN_CANDLES = 2


def _extract_ohlcv(
    candles: list[dict[str, Any]],
) -> tuple[list[int], list[float], list[float], list[float], list[float], list[float]]:
    """Validate candle structure, chronological timestamps, and OHLCV values."""
    if not candles:
        raise ValueError("Candle list is empty; cannot calculate indicators.")

    timestamps: list[int] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    volumes: list[float] = []
    seen_timestamps: set[int] = set()

    for index, candle in enumerate(candles):
        if not isinstance(candle, dict):
            raise ValueError(f"Candle at index {index} must be an object.")
        try:
            timestamp = candle["timestamp"]
            if isinstance(timestamp, bool) or not isinstance(timestamp, Integral):
                raise ValueError("timestamp must be an integer")
            timestamp = int(timestamp)
            values = [float(candle[key]) for key in ("open", "high", "low", "close", "volume")]
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Candle at index {index} is malformed or missing required fields: {exc}") from exc

        open_price, high, low, close, volume = values
        if not all(np.isfinite(values)):
            raise ValueError(f"Candle at index {index} contains non-finite OHLCV value(s).")
        if timestamp < 0:
            raise ValueError(f"Candle at index {index} has a negative timestamp.")
        if timestamp in seen_timestamps:
            raise ValueError(f"Candle timestamp {timestamp} is duplicated.")
        if timestamps and timestamp <= timestamps[-1]:
            raise ValueError("Candle timestamps must be in strictly chronological order.")
        if high < low:
            raise ValueError(f"Candle at index {index} has high below low.")
        if not low <= open_price <= high or not low <= close <= high:
            raise ValueError(f"Candle at index {index} has open or close outside the high/low range.")
        if volume < 0:
            raise ValueError(f"Candle at index {index} has negative volume.")

        timestamps.append(timestamp)
        seen_timestamps.add(timestamp)
        opens.append(open_price)
        highs.append(high)
        lows.append(low)
        closes.append(close)
        volumes.append(volume)

    return timestamps, opens, highs, lows, closes, volumes


def _validate_calculation_parameters(
    sma_periods: tuple[int, int], ema_periods: tuple[int, int], rsi_period: int,
    macd_fast: int, macd_slow: int, macd_signal: int, bb_period: int,
    bb_std: float, atr_period: int,
) -> None:
    for label, pair in (("SMA", sma_periods), ("EMA", ema_periods)):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f"{label} periods must contain exactly two positive integers.")
        for period in pair:
            if isinstance(period, bool) or not isinstance(period, Integral) or period < 1:
                raise ValueError(f"{label} periods must contain exactly two positive integers.")
    for label, period in (("RSI", rsi_period), ("MACD fast", macd_fast), ("MACD slow", macd_slow),
                          ("MACD signal", macd_signal), ("Bollinger", bb_period), ("ATR", atr_period)):
        minimum = 2 if label == "Bollinger" else 1
        if isinstance(period, bool) or not isinstance(period, Integral) or period < minimum:
            raise ValueError(f"{label} period must be an integer >= {minimum}.")
    if macd_fast >= macd_slow:
        raise ValueError("MACD fast period must be less than slow period.")
    if isinstance(bb_std, bool) or not np.isfinite(bb_std) or bb_std < 0:
        raise ValueError("Bollinger standard-deviation multiplier must be finite and non-negative.")


def calculate_indicators(
    candles: list[dict[str, Any]],
    sma_periods: tuple[int, int] = (20, 50),
    ema_periods: tuple[int, int] = (20, 50),
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bb_period: int = 20,
    bb_std: float = 2.0,
    atr_period: int = 14,
) -> dict[str, Any]:
    """Calculate SMA, EMA, Wilder RSI/MACD, Bollinger Bands, and Wilder ATR."""
    timestamps, _opens, highs, lows, closes, _volumes = _extract_ohlcv(candles)
    if len(candles) < MIN_CANDLES:
        raise ValueError(f"At least {MIN_CANDLES} candles are required; received {len(candles)}.")
    _validate_calculation_parameters(
        sma_periods, ema_periods, rsi_period, macd_fast, macd_slow,
        macd_signal, bb_period, bb_std, atr_period,
    )

    arrays = {
        "sma_20": sma(closes, sma_periods[0]),
        "sma_50": sma(closes, sma_periods[1]),
        "ema_20": ema(closes, ema_periods[0]),
        "ema_50": ema(closes, ema_periods[1]),
        "rsi_14": rsi(closes, rsi_period),
    }
    macd_line, signal_line, macd_hist = macd(closes, macd_fast, macd_slow, macd_signal)
    bb_upper, bb_middle, bb_lower = bollinger_bands(closes, bb_period, bb_std)
    atr_values = atr(highs, lows, closes, atr_period)
    arrays = {key: _safe_array(value) for key, value in arrays.items()}
    macd_values = [_safe_array(value) for value in (macd_line, signal_line, macd_hist)]
    bands = [_safe_array(value) for value in (bb_upper, bb_middle, bb_lower)]
    atr_list = _safe_array(atr_values)

    series = []
    for index, close in enumerate(closes):
        series.append({
            "timestamp": timestamps[index], "close": close,
            **{key: values[index] for key, values in arrays.items()},
            "macd": {"line": macd_values[0][index], "signal": macd_values[1][index], "histogram": macd_values[2][index]},
            "bollinger_bands": {"upper": bands[0][index], "middle": bands[1][index], "lower": bands[2][index]},
            "atr_14": atr_list[index],
        })
    latest = {key: values[-1] for key, values in arrays.items()}
    latest.update({
        "macd": {"line": macd_values[0][-1], "signal": macd_values[1][-1], "histogram": macd_values[2][-1]},
        "bollinger_bands": {"upper": bands[0][-1], "middle": bands[1][-1], "lower": bands[2][-1]},
        "atr_14": atr_list[-1],
    })
    return {"candle_count": len(candles), "latest": latest, "series": series}
