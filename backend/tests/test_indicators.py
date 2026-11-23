"""
Unit tests for the technical indicators module.

All tests use deterministic synthetic data with hand-verified expected values.
No network access or exchange connectivity is required.

Calculation notes
-----------------
- SMA: straightforward rolling mean.
- EMA: seeded with SMA at index (period-1), then k = 2/(N+1) recurrence.
- RSI: Wilder smoothing; first valid at index period.
- MACD: EMA(12) - EMA(26); signal is a 9-period SMA-seeded EMA of valid MACD.
- Bollinger: SMA ± 2 × population std (ddof=0).
- ATR: Wilder smoothing; first valid at index period.
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from backend.app.analysis.indicators import (
    atr,
    bollinger_bands,
    ema,
    macd,
    rsi,
    sma,
    _safe_array,
    _safe_scalar,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_linear(start: float, step: float, n: int) -> list[float]:
    """Return [start, start+step, start+2*step, ...] of length n."""
    return [start + i * step for i in range(n)]


def make_flat(value: float, n: int) -> list[float]:
    return [value] * n


# ---------------------------------------------------------------------------
# _safe_scalar / _safe_array helpers
# ---------------------------------------------------------------------------

class TestSafeHelpers:
    def test_safe_scalar_finite(self):
        assert _safe_scalar(3.14) == pytest.approx(3.14)

    def test_safe_scalar_nan(self):
        assert _safe_scalar(float("nan")) is None

    def test_safe_scalar_inf(self):
        assert _safe_scalar(float("inf")) is None

    def test_safe_array_mixed(self):
        arr = np.array([1.0, float("nan"), 3.0, float("inf")])
        result = _safe_array(arr)
        assert result == [1.0, None, 3.0, None]


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------

class TestSMA:
    def test_basic_window(self):
        # SMA(3) of [1,2,3,4,5] → NaN,NaN,2,3,4
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = sma(closes, 3)
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_period_1_equals_input(self):
        closes = [10.0, 20.0, 30.0]
        result = sma(closes, 1)
        assert result.tolist() == pytest.approx([10.0, 20.0, 30.0])

    def test_all_nan_when_too_short(self):
        result = sma([1.0, 2.0], 5)
        assert all(math.isnan(v) for v in result)

    def test_period_equals_length(self):
        closes = [2.0, 4.0, 6.0]
        result = sma(closes, 3)
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        assert result[2] == pytest.approx(4.0)

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            sma([1.0, 2.0], 0)

    def test_sma_20_known_value(self):
        """SMA(20) of a linearly increasing sequence: mean of last 20 values."""
        closes = make_linear(1.0, 1.0, 30)  # 1,2,...,30
        result = sma(closes, 20)
        # At index 19: mean of closes[0:20] = mean(1..20) = 10.5
        assert result[19] == pytest.approx(10.5)
        # At index 29: mean of closes[10:30] = mean(11..30) = 20.5
        assert result[29] == pytest.approx(20.5)

    def test_sma_50_requires_50_candles(self):
        closes = make_linear(1.0, 1.0, 60)
        result = sma(closes, 50)
        assert all(math.isnan(result[i]) for i in range(49))
        assert result[49] == pytest.approx(25.5)  # mean(1..50)


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------

class TestEMA:
    def test_ema_period_1_equals_input(self):
        closes = [10.0, 20.0, 30.0]
        result = ema(closes, 1)
        assert result.tolist() == pytest.approx([10.0, 20.0, 30.0])

    def test_ema_seed_equals_sma(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = ema(closes, 3)
        # Seed at index 2 = mean(1,2,3) = 2.0
        assert result[2] == pytest.approx(2.0)

    def test_ema_warm_up_is_nan(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = ema(closes, 3)
        assert math.isnan(result[0])
        assert math.isnan(result[1])

    def test_ema_recurrence(self):
        # SMA seed of [10,11] at index 1, then alpha=2/3 recurrence.
        closes = [10.0, 11.0, 12.0]
        result = ema(closes, 2)
        assert math.isnan(result[0])
        assert result[1] == pytest.approx(10.5)
        assert result[2] == pytest.approx(10.5 + 2 / 3 * (12.0 - 10.5))

    def test_ema_all_nan_when_too_short(self):
        result = ema([1.0, 2.0], 5)
        assert all(math.isnan(v) for v in result)

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            ema([1.0, 2.0], 0)

    def test_ema_flat_series_stays_flat(self):
        closes = make_flat(100.0, 30)
        result = ema(closes, 10)
        for v in result[9:]:
            assert v == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

class TestRSI:
    def test_flat_series_rsi_is_neutral(self):
        closes = make_flat(100.0, 30)
        result = rsi(closes, 14)
        assert math.isnan(result[13])
        assert result[14] == pytest.approx(50.0)
        assert all(value == pytest.approx(50.0) for value in result[14:])

    def test_wilder_seed_and_recurrence_match_hand_calculation(self):
        closes = [10.0, 11.0, 10.0, 12.0, 11.0]
        result = rsi(closes, 3)
        # Changes [1,-1,2] seed avg gain=1, avg loss=1/3.
        assert math.isnan(result[2])
        assert result[3] == pytest.approx(75.0)
        # Next change is -1: avg gain=2/3, avg loss=5/9.
        expected = 100.0 - 100.0 / (1.0 + (2.0 / 3.0) / (5.0 / 9.0))
        assert result[4] == pytest.approx(expected)

    def test_all_rising_rsi_approaches_100(self):
        closes = make_linear(100.0, 1.0, 50)
        result = rsi(closes, 14)
        # With pure gains, avg_loss → 0, RSI → 100
        finite = [v for v in result if not math.isnan(v)]
        assert len(finite) > 0
        assert all(v > 90.0 for v in finite)

    def test_all_falling_rsi_approaches_0(self):
        closes = make_linear(200.0, -1.0, 50)
        result = rsi(closes, 14)
        finite = [v for v in result if not math.isnan(v)]
        assert len(finite) > 0
        assert all(v < 10.0 for v in finite)

    def test_rsi_warm_up_positions_are_nan(self):
        closes = make_linear(100.0, 1.0, 40)
        result = rsi(closes, 14)
        # First valid RSI at index period (index 14 in 0-based, since
        # we emit at i+1 after iterating deltas from index period-1)
        for i in range(14):
            assert math.isnan(result[i])

    def test_insufficient_data(self):
        closes = [100.0] * 5
        result = rsi(closes, 14)
        assert all(math.isnan(v) for v in result)

    def test_rsi_bounds(self):
        closes = make_linear(100.0, 0.5, 50)
        result = rsi(closes, 14)
        for v in result:
            if not math.isnan(v):
                assert 0.0 <= v <= 100.0

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            rsi([1.0, 2.0], 0)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

class TestMACD:
    def test_macd_warm_up_positions(self):
        closes = make_linear(100.0, 0.5, 60)
        macd_line, signal_line, histogram = macd(closes, 12, 26, 9)
        # MACD line valid from index 25 (EMA26 seed)
        for i in range(25):
            assert math.isnan(macd_line[i])
        # Signal valid from MACD seed + (signal_period - 1) = 25 + 8 = 33
        for i in range(33):
            assert math.isnan(signal_line[i])

    def test_first_valid_macd_signal_and_histogram_values(self):
        closes = make_linear(100.0, 1.0, 40)
        line, signal, histogram = macd(closes)
        assert math.isnan(line[24])
        assert line[25] == pytest.approx(7.0)
        assert math.isnan(signal[32])
        assert signal[33] == pytest.approx(np.mean(line[25:34]))
        assert histogram[33] == pytest.approx(line[33] - signal[33])

    def test_macd_line_direction(self):
        closes = make_linear(100.0, 1.0, 100)
        line, _, _ = macd(closes)
        assert all(value > 0 for value in line[25:])

    def test_falling_market_macd_line_is_negative(self):
        closes = make_linear(200.0, -1.0, 100)
        line, _, _ = macd(closes)
        assert all(value < 0 for value in line[25:])

    def test_macd_insufficient_signal_history(self):
        line, signal, histogram = macd(make_linear(10.0, 1.0, 33))
        assert not math.isnan(line[-1])
        assert math.isnan(signal[-1])
        assert math.isnan(histogram[-1])

    def test_macd_histogram_equals_line_minus_signal(self):
        closes = make_linear(100.0, 0.3, 100)
        ml, sl, hist = macd(closes, 12, 26, 9)
        for i in range(len(closes)):
            if not math.isnan(ml[i]) and not math.isnan(sl[i]):
                assert hist[i] == pytest.approx(ml[i] - sl[i], abs=1e-9)

    def test_invalid_fast_slow(self):
        with pytest.raises(ValueError):
            macd([1.0] * 50, fast=26, slow=12)

    def test_macd_flat_market_converges_to_zero(self):
        closes = make_flat(100.0, 100)
        ml, sl, hist = macd(closes, 12, 26, 9)
        for v in [ml[-1], sl[-1], hist[-1]]:
            assert v == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

class TestBollingerBands:
    def test_bands_symmetry(self):
        """upper - middle == middle - lower for each candle."""
        closes = make_linear(100.0, 0.5, 40)
        upper, middle, lower = bollinger_bands(closes, 20, 2.0)
        for i in range(19, 40):
            assert upper[i] - middle[i] == pytest.approx(middle[i] - lower[i], abs=1e-9)

    def test_bands_warm_up_nan(self):
        closes = make_linear(100.0, 1.0, 30)
        upper, middle, lower = bollinger_bands(closes, 20, 2.0)
        for i in range(19):
            assert math.isnan(upper[i])
            assert math.isnan(middle[i])
            assert math.isnan(lower[i])

    def test_middle_equals_sma(self):
        closes = make_linear(1.0, 1.0, 30)
        _, middle, _ = bollinger_bands(closes, 20, 2.0)
        expected_sma = sma(closes, 20)
        for i in range(19, 30):
            assert middle[i] == pytest.approx(expected_sma[i], abs=1e-9)

    def test_flat_series_bands_collapse(self):
        """Flat prices → std = 0 → upper == middle == lower."""
        closes = make_flat(100.0, 30)
        upper, middle, lower = bollinger_bands(closes, 20, 2.0)
        for i in range(19, 30):
            assert upper[i] == pytest.approx(100.0, abs=1e-9)
            assert lower[i] == pytest.approx(100.0, abs=1e-9)

    def test_known_std_value(self):
        # At index 4 (period=5), use population standard deviation.
        closes = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        upper, middle, lower = bollinger_bands(closes, 5, 2.0)
        window_at_4 = [2.0, 4.0, 4.0, 4.0, 5.0]
        m = np.mean(window_at_4)
        s = np.std(window_at_4, ddof=0)
        assert middle[4] == pytest.approx(m, rel=1e-9)
        assert upper[4] == pytest.approx(m + 2 * s, rel=1e-9)
        assert lower[4] == pytest.approx(m - 2 * s, rel=1e-9)

    def test_too_short_returns_all_nan(self):
        upper, middle, lower = bollinger_bands([1.0, 2.0], 20, 2.0)
        assert all(math.isnan(v) for v in upper)
        assert all(math.isnan(v) for v in lower)

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            bollinger_bands([1.0] * 10, 1, 2.0)


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

class TestATR:
    def _make_ohlcv(self, n: int, spread: float = 1.0):
        """Generate simple candles: close rises by 1 each step, spread ±0.5."""
        c = make_linear(100.0, 1.0, n)
        h = [v + spread for v in c]
        lo = [v - spread for v in c]
        return h, lo, c

    def test_atr_warm_up_nan(self):
        h, lo, c = self._make_ohlcv(30)
        result = atr(h, lo, c, 14)
        for i in range(14):
            assert math.isnan(result[i])

    def test_atr_first_valid_index(self):
        h, lo, c = self._make_ohlcv(30)
        result = atr(h, lo, c, 14)
        assert not math.isnan(result[14])

    def test_atr_flat_market_known_value(self):
        """
        Flat closes, spread = 1 → TR = H-L = 2 always (no gap from prev close).
        Wait: H=101, L=99, close=100; prev_close=100 → TR = max(2, |101-100|, |99-100|) = 2.
        ATR(1) of all-2 TR = 2.
        """
        n = 20
        c = make_flat(100.0, n)
        h = [101.0] * n
        lo = [99.0] * n
        result = atr(h, lo, c, 1)
        # ATR(1): seed = TR[1] = 2, then Wilder with period 1 → always 2
        for i in range(1, n):
            assert result[i] == pytest.approx(2.0, abs=1e-6)

    def test_atr_mismatched_lengths(self):
        with pytest.raises(ValueError):
            atr([1.0, 2.0], [0.5, 1.5], [1.0], 1)

    def test_atr_too_short(self):
        h, lo, c = self._make_ohlcv(5)
        result = atr(h, lo, c, 14)
        assert all(math.isnan(v) for v in result)

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            atr([1.0], [1.0], [1.0], 0)


# ---------------------------------------------------------------------------
# Edge-cases: empty / trivial inputs
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_sma_empty_list(self):
        result = sma([], 5)
        assert len(result) == 0

    def test_ema_single_element(self):
        result = ema([42.0], 1)
        assert result[0] == pytest.approx(42.0)

    def test_rsi_single_element(self):
        result = rsi([42.0], 14)
        assert len(result) == 1
        assert math.isnan(result[0])

    def test_bollinger_single_element(self):
        upper, _, lower = bollinger_bands([42.0], 20, 2.0)
        assert len(upper) == 1
        assert math.isnan(upper[0])

    def test_atr_single_element(self):
        result = atr([42.0], [41.0], [41.5], 14)
        assert len(result) == 1

    def test_sma_non_finite_propagates(self):
        """Input with NaN should propagate NaN into the window."""
        closes = [1.0, float("nan"), 3.0, 4.0, 5.0]
        result = sma(closes, 3)
        # Window containing NaN should produce NaN
        assert math.isnan(result[2])  # window [1, nan, 3]

    def test_macd_returns_all_nan_for_short_input(self):
        closes = [100.0] * 10
        ml, sl, hist = macd(closes, 12, 26, 9)
        assert all(math.isnan(v) for v in ml)
        assert all(math.isnan(v) for v in sl)
        assert all(math.isnan(v) for v in hist)
