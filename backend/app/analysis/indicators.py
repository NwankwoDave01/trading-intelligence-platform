"""
Technical analysis indicators engine.

Implements SMA, EMA, RSI, MACD, Bollinger Bands, and ATR using pure NumPy.
All functions operate on 1-D arrays of close/high/low/volume prices aligned
to their source candles.  Warm-up values that cannot be computed are returned
as np.nan and later serialised as JSON null.

Design choices
--------------
- Wilder's smoothing (RMA) is used for RSI and ATR, matching the standard
  TradingView / MetaTrader definitions.
- EMA uses the standard multiplier  k = 2 / (N + 1).
- Bollinger Bands use *sample* standard deviation (ddof=1) which matches the
  original Bollinger specification and is the common convention in charting
  software.  This is documented here and kept consistent with the test suite.
- All indicators return arrays the same length as the input, padded with NaN
  for the warm-up period so callers can zip the output directly with timestamps.
"""

from __future__ import annotations

from typing import Sequence
import numpy as np


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_array(values: Sequence[float]) -> np.ndarray:
    """Convert any sequence to a float64 NumPy array."""
    return np.asarray(values, dtype=np.float64)


def _safe_scalar(value: float) -> float | None:
    """Return None for NaN / Inf; otherwise return the Python float."""
    if not np.isfinite(value):
        return None
    return float(value)


def _safe_array(arr: np.ndarray) -> list[float | None]:
    """Convert a NumPy array to a JSON-safe list (NaN → None)."""
    result: list[float | None] = []
    for v in arr:
        result.append(None if not np.isfinite(v) else float(v))
    return result


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------

def sma(closes: Sequence[float], period: int) -> np.ndarray:
    """
    Simple Moving Average.

    Returns an array the same length as *closes*; the first (period - 1)
    values are NaN because there is insufficient history.
    """
    if period < 1:
        raise ValueError(f"SMA period must be >= 1, got {period}")
    arr = _to_array(closes)
    out = np.full(len(arr), np.nan)
    if len(arr) < period:
        return out
    for i in range(period - 1, len(arr)):
        out[i] = arr[i - period + 1 : i + 1].mean()
    return out


def ema(closes: Sequence[float], period: int) -> np.ndarray:
    """
    Exponential Moving Average using multiplier k = 2 / (period + 1).

    The first valid value (index period-1) is seeded with the SMA of the
    first *period* closes; subsequent values use the standard EMA recurrence.
    """
    if period < 1:
        raise ValueError(f"EMA period must be >= 1, got {period}")
    arr = _to_array(closes)
    out = np.full(len(arr), np.nan)
    if len(arr) < period:
        return out
    k = 2.0 / (period + 1)
    # Seed with SMA of the first `period` values
    out[period - 1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = arr[i] * k + out[i - 1] * (1 - k)
    return out


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------

def rsi(closes: Sequence[float], period: int = 14) -> np.ndarray:
    """
    Relative Strength Index using Wilder's smoothing (RMA).

    Wilder's smoothing: alpha = 1 / period (not the standard EMA 2/(N+1)).
    The first valid RSI is at index (period * 2 - 1) because we need *period*
    price changes to seed the first average gain/loss, then one more step to
    emit the first RSI value.

    Returns NaN for all warm-up positions.
    """
    if period < 1:
        raise ValueError(f"RSI period must be >= 1, got {period}")
    arr = _to_array(closes)
    out = np.full(len(arr), np.nan)
    if len(arr) < period + 1:
        return out

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Seed first average gain/loss with simple mean of first `period` changes
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()

    # Wilder smoothing factor
    alpha = 1.0 / period

    for i in range(period, len(deltas)):
        avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
        avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
        if avg_loss == 0:
            out[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return out


def macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    MACD indicator.

    Returns (macd_line, signal_line, histogram) as three arrays of the same
    length as *closes*, with NaN for warm-up positions.

    MACD line = EMA(fast) − EMA(slow).
    Signal    = EMA(MACD line, signal_period).
    Histogram = MACD line − signal.
    """
    if fast >= slow:
        raise ValueError(f"MACD fast period ({fast}) must be < slow period ({slow})")
    arr = _to_array(closes)
    ema_fast = ema(arr, fast)
    ema_slow = ema(arr, slow)
    macd_line = ema_fast - ema_slow
    # Signal is EMA of the MACD line; we must pass only non-NaN values but
    # keep alignment.  We feed the full macd_line; ema() seeds from index
    # (slow-1) + (signal-1).
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------

def bollinger_bands(
    closes: Sequence[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Bollinger Bands.

    Middle band = SMA(period).
    Upper band  = middle + num_std × std.
    Lower band  = middle − num_std × std.

    Standard deviation uses ddof=1 (sample std) which matches the original
    John Bollinger specification and common charting software defaults.

    Returns (upper, middle, lower) arrays the same length as *closes*.
    """
    if period < 2:
        raise ValueError(f"Bollinger period must be >= 2, got {period}")
    arr = _to_array(closes)
    n = len(arr)
    upper = np.full(n, np.nan)
    middle = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    if n < period:
        return upper, middle, lower
    for i in range(period - 1, n):
        window = arr[i - period + 1 : i + 1]
        m = window.mean()
        s = window.std(ddof=1)
        middle[i] = m
        upper[i] = m + num_std * s
        lower[i] = m - num_std * s
    return upper, middle, lower


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> np.ndarray:
    """
    Average True Range using Wilder's smoothing (RMA).

    True Range = max(high − low, |high − prev_close|, |low − prev_close|)
    ATR is the Wilder-smoothed average of TR.

    The first valid ATR (index *period*) is seeded with the simple mean of
    the first *period* TR values; subsequent values use Wilder smoothing
    alpha = 1 / period.

    Returns NaN for warm-up positions (indices 0 … period-1).
    """
    if period < 1:
        raise ValueError(f"ATR period must be >= 1, got {period}")
    h = _to_array(highs)
    l = _to_array(lows)
    c = _to_array(closes)
    n = len(c)
    if not (len(h) == len(l) == n):
        raise ValueError("highs, lows, closes must all have the same length")
    out = np.full(n, np.nan)
    if n < period + 1:
        return out

    # True range (starts at index 1 because we need prev_close)
    tr = np.full(n, np.nan)
    for i in range(1, n):
        hl = h[i] - l[i]
        hc = abs(h[i] - c[i - 1])
        lc = abs(l[i] - c[i - 1])
        tr[i] = max(hl, hc, lc)

    # Seed with simple mean of first `period` TR values (indices 1 … period)
    alpha = 1.0 / period
    atr_val = tr[1 : period + 1].mean()
    out[period] = atr_val
    for i in range(period + 1, n):
        atr_val = alpha * tr[i] + (1 - alpha) * atr_val
        out[i] = atr_val
    return out
