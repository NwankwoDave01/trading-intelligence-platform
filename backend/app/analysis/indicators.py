"""Technical analysis indicators implemented with NumPy.

All outputs preserve input alignment. Warm-up positions are NaN and become
JSON null at the API boundary. EMA uses an SMA seed; RSI and ATR use Wilder
smoothing; Bollinger Bands use population standard deviation (ddof=0).
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def _to_array(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def _safe_scalar(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def _safe_array(arr: np.ndarray) -> list[float | None]:
    return [float(value) if np.isfinite(value) else None for value in arr]


def _validate_period(name: str, period: int, minimum: int = 1) -> None:
    if isinstance(period, bool) or not isinstance(period, (int, np.integer)) or period < minimum:
        raise ValueError(f"{name} period must be an integer >= {minimum}, got {period}")


def sma(closes: Sequence[float], period: int) -> np.ndarray:
    """Rolling simple mean; first valid value is at index period - 1."""
    _validate_period("SMA", period)
    arr = _to_array(closes)
    out = np.full(len(arr), np.nan)
    for i in range(period - 1, len(arr)):
        out[i] = arr[i - period + 1 : i + 1].mean()
    return out


def ema(closes: Sequence[float], period: int) -> np.ndarray:
    """SMA-seeded EMA with alpha = 2 / (period + 1)."""
    _validate_period("EMA", period)
    arr = _to_array(closes)
    out = np.full(len(arr), np.nan)
    if len(arr) < period:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = out[i - 1] + alpha * (arr[i] - out[i - 1])
    return out


def rsi(closes: Sequence[float], period: int = 14) -> np.ndarray:
    """Wilder RSI, first valid at index period; flat markets return neutral 50."""
    _validate_period("RSI", period)
    arr = _to_array(closes)
    out = np.full(len(arr), np.nan)
    if len(arr) <= period:
        return out
    changes = np.diff(arr)
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())

    def value(gain: float, loss: float) -> float:
        if gain == 0.0 and loss == 0.0:
            return 50.0
        if loss == 0.0:
            return 100.0
        if gain == 0.0:
            return 0.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    out[period] = value(avg_gain, avg_loss)
    for change_index in range(period, len(changes)):
        avg_gain = ((period - 1) * avg_gain + gains[change_index]) / period
        avg_loss = ((period - 1) * avg_loss + losses[change_index]) / period
        out[change_index + 1] = value(avg_gain, avg_loss)
    return out


def macd(
    closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD(12,26,9), aligned to prices; signal is seeded on valid MACD only."""
    _validate_period("MACD fast", fast)
    _validate_period("MACD slow", slow)
    _validate_period("MACD signal", signal)
    if fast >= slow:
        raise ValueError(f"MACD fast period ({fast}) must be < slow period ({slow})")
    arr = _to_array(closes)
    fast_ema = ema(arr, fast)
    slow_ema = ema(arr, slow)
    line = fast_ema - slow_ema
    signal_line = np.full(len(arr), np.nan)
    first_valid = slow - 1
    valid_line = line[first_valid:]
    if len(valid_line) >= signal:
        signal_line[first_valid:] = ema(valid_line, signal)
    histogram = line - signal_line
    return line, signal_line, histogram


def bollinger_bands(
    closes: Sequence[float], period: int = 20, num_std: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Population-standard-deviation Bollinger Bands (default 20, 2 sigma)."""
    _validate_period("Bollinger", period, minimum=2)
    if not np.isfinite(num_std) or num_std < 0:
        raise ValueError("Bollinger standard-deviation multiplier must be finite and non-negative")
    arr = _to_array(closes)
    upper = np.full(len(arr), np.nan)
    middle = np.full(len(arr), np.nan)
    lower = np.full(len(arr), np.nan)
    for i in range(period - 1, len(arr)):
        window = arr[i - period + 1 : i + 1]
        mean = window.mean()
        deviation = window.std(ddof=0)
        middle[i] = mean
        upper[i] = mean + num_std * deviation
        lower[i] = mean - num_std * deviation
    return upper, middle, lower


def atr(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14,
) -> np.ndarray:
    """Wilder ATR, seeded by the first period true ranges at index period."""
    _validate_period("ATR", period)
    high = _to_array(highs)
    low = _to_array(lows)
    close = _to_array(closes)
    n = len(close)
    if not (len(high) == len(low) == n):
        raise ValueError("highs, lows, closes must all have the same length")
    out = np.full(n, np.nan)
    if n <= period:
        return out
    true_range = np.full(n, np.nan)
    for i in range(1, n):
        true_range[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    current = float(true_range[1 : period + 1].mean())
    out[period] = current
    for i in range(period + 1, n):
        current = ((period - 1) * current + true_range[i]) / period
        out[i] = current
    return out
