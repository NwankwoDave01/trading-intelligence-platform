"""
Technical analysis service.

Receives a list of normalised OHLCV candle dicts (as returned by the market
data providers) and produces a fully-structured IndicatorResult.

This module is intentionally decoupled from FastAPI and from exchange
providers: it has no network dependencies and is independently testable.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.app.analysis.indicators import (
    _safe_array,
    _safe_scalar,
    atr,
    bollinger_bands,
    ema,
    macd,
    rsi,
    sma,
)

# Minimum number of candles we need before we will attempt indicator
# calculation at all.  Below this we raise ValueError so the API layer can
# return a sensible 422.
MIN_CANDLES = 2


def _extract_ohlcv(
    candles: list[dict[str, Any]],
) -> tuple[list[int], list[float], list[float], list[float], list[float]]:
    """
    Pull timestamps and OHLCV columns out of provider candle dicts.

    Raises ValueError for empty input or structurally invalid candles.
    """
    if not candles:
        raise ValueError("Candle list is empty; cannot calculate indicators.")

    timestamps: list[int] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []

    for idx, c in enumerate(candles):
        try:
            ts = c["timestamp"]
            o = float(c["open"])
            h = float(c["high"])
            lo = float(c["low"])
            cl = float(c["close"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Candle at index {idx} is malformed or missing required fields: {exc}"
            ) from exc

        # Reject non-finite price values
        if not all(np.isfinite([o, h, lo, cl])):
            raise ValueError(
                f"Candle at index {idx} contains non-finite price value(s)."
            )

        timestamps.append(ts)
        opens.append(o)
        highs.append(h)
        lows.append(lo)
        closes.append(cl)

    return timestamps, opens, highs, lows, closes


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
    """
    Calculate all technical indicators for a list of OHLCV candles.

    Parameters
    ----------
    candles:
        List of dicts with keys ``timestamp``, ``open``, ``high``, ``low``,
        ``close``, ``volume`` (as returned by market data providers).

    Returns
    -------
    dict with keys:
        ``candle_count``   – number of input candles
        ``latest``         – dict of the most-recent finite indicator values
        ``series``         – timestamp-aligned list of per-candle indicator dicts
    """
    if len(candles) < MIN_CANDLES:
        raise ValueError(
            f"At least {MIN_CANDLES} candles are required; received {len(candles)}."
        )

    timestamps, opens, highs, lows, closes = _extract_ohlcv(candles)

    # --- Moving averages ---
    sma20 = sma(closes, sma_periods[0])
    sma50 = sma(closes, sma_periods[1])
    ema20 = ema(closes, ema_periods[0])
    ema50 = ema(closes, ema_periods[1])

    # --- Momentum ---
    rsi14 = rsi(closes, rsi_period)
    macd_line, signal_line, macd_hist = macd(closes, macd_fast, macd_slow, macd_signal)

    # --- Volatility ---
    bb_upper, bb_middle, bb_lower = bollinger_bands(closes, bb_period, bb_std)
    atr14 = atr(highs, lows, closes, atr_period)

    # Convert to safe lists
    sma20_list = _safe_array(sma20)
    sma50_list = _safe_array(sma50)
    ema20_list = _safe_array(ema20)
    ema50_list = _safe_array(ema50)
    rsi14_list = _safe_array(rsi14)
    macd_line_list = _safe_array(macd_line)
    signal_line_list = _safe_array(signal_line)
    macd_hist_list = _safe_array(macd_hist)
    bb_upper_list = _safe_array(bb_upper)
    bb_middle_list = _safe_array(bb_middle)
    bb_lower_list = _safe_array(bb_lower)
    atr14_list = _safe_array(atr14)

    n = len(candles)

    # --- Build timestamp-aligned series ---
    series = []
    for i in range(n):
        series.append({
            "timestamp": timestamps[i],
            "close": closes[i],
            "sma_20": sma20_list[i],
            "sma_50": sma50_list[i],
            "ema_20": ema20_list[i],
            "ema_50": ema50_list[i],
            "rsi_14": rsi14_list[i],
            "macd": {
                "line": macd_line_list[i],
                "signal": signal_line_list[i],
                "histogram": macd_hist_list[i],
            },
            "bollinger_bands": {
                "upper": bb_upper_list[i],
                "middle": bb_middle_list[i],
                "lower": bb_lower_list[i],
            },
            "atr_14": atr14_list[i],
        })

    # --- Latest values (most recent non-NaN) ---
    latest = {
        "sma_20": sma20_list[-1],
        "sma_50": sma50_list[-1],
        "ema_20": ema20_list[-1],
        "ema_50": ema50_list[-1],
        "rsi_14": rsi14_list[-1],
        "macd": {
            "line": macd_line_list[-1],
            "signal": signal_line_list[-1],
            "histogram": macd_hist_list[-1],
        },
        "bollinger_bands": {
            "upper": bb_upper_list[-1],
            "middle": bb_middle_list[-1],
            "lower": bb_lower_list[-1],
        },
        "atr_14": atr14_list[-1],
    }

    return {
        "candle_count": n,
        "latest": latest,
        "series": series,
    }
