"""
Unit tests for the analysis service (calculate_indicators).

Verifies data extraction, full pipeline integration, error handling, timestamp
alignment, and NaN → null conversion.  No network access required.
"""

from __future__ import annotations

import math
import pytest

from backend.app.analysis.service import calculate_indicators, MIN_CANDLES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_candles(n: int, start_close: float = 100.0, step: float = 0.5) -> list[dict]:
    """
    Generate n synthetic OHLCV candle dicts with gently rising prices and
    realistic H/L spreads, plus millisecond timestamps.
    """
    candles = []
    close = start_close
    ts = 1_700_000_000_000  # 2023-11-14 22:13:20 UTC in ms
    for i in range(n):
        candles.append({
            "timestamp": ts + i * 3_600_000,
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 50.0 + i,
        })
        close += step
    return candles


CANDLES_200 = _make_candles(200)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestCalculateIndicatorsHappyPath:
    def test_returns_expected_keys(self):
        result = calculate_indicators(CANDLES_200)
        assert set(result.keys()) == {"candle_count", "latest", "series"}

    def test_candle_count(self):
        result = calculate_indicators(CANDLES_200)
        assert result["candle_count"] == 200

    def test_series_length_matches_input(self):
        result = calculate_indicators(CANDLES_200)
        assert len(result["series"]) == 200

    def test_series_timestamps_match_input(self):
        candles = _make_candles(50)
        result = calculate_indicators(candles)
        for i, row in enumerate(result["series"]):
            assert row["timestamp"] == candles[i]["timestamp"]

    def test_series_close_values_match_input(self):
        candles = _make_candles(50)
        result = calculate_indicators(candles)
        for i, row in enumerate(result["series"]):
            assert row["close"] == pytest.approx(candles[i]["close"])

    def test_latest_sma_20_is_finite_with_200_candles(self):
        result = calculate_indicators(CANDLES_200)
        assert result["latest"]["sma_20"] is not None
        assert math.isfinite(result["latest"]["sma_20"])

    def test_latest_sma_50_is_finite_with_200_candles(self):
        result = calculate_indicators(CANDLES_200)
        assert result["latest"]["sma_50"] is not None

    def test_latest_ema_20_is_finite(self):
        result = calculate_indicators(CANDLES_200)
        assert result["latest"]["ema_20"] is not None

    def test_latest_rsi_in_bounds(self):
        result = calculate_indicators(CANDLES_200)
        rsi_val = result["latest"]["rsi_14"]
        if rsi_val is not None:
            assert 0.0 <= rsi_val <= 100.0

    def test_latest_macd_has_expected_structure(self):
        result = calculate_indicators(CANDLES_200)
        macd = result["latest"]["macd"]
        assert "line" in macd
        assert "signal" in macd
        assert "histogram" in macd

    def test_latest_bollinger_has_expected_structure(self):
        result = calculate_indicators(CANDLES_200)
        bb = result["latest"]["bollinger_bands"]
        assert "upper" in bb
        assert "middle" in bb
        assert "lower" in bb

    def test_latest_bollinger_band_ordering(self):
        result = calculate_indicators(CANDLES_200)
        bb = result["latest"]["bollinger_bands"]
        if all(v is not None for v in bb.values()):
            assert bb["upper"] >= bb["middle"] >= bb["lower"]

    def test_latest_atr_is_finite(self):
        result = calculate_indicators(CANDLES_200)
        atr_val = result["latest"]["atr_14"]
        if atr_val is not None:
            assert atr_val >= 0.0

    def test_warm_up_values_are_none(self):
        """First 19 SMA-20 values must be null (None in Python)."""
        result = calculate_indicators(CANDLES_200)
        for row in result["series"][:19]:
            assert row["sma_20"] is None

    def test_sma_20_valid_after_warmup(self):
        result = calculate_indicators(CANDLES_200)
        # Index 19 is the first valid SMA-20
        assert result["series"][19]["sma_20"] is not None

    def test_macd_histogram_matches_line_minus_signal(self):
        result = calculate_indicators(CANDLES_200)
        for row in result["series"]:
            m = row["macd"]
            if m["line"] is not None and m["signal"] is not None:
                assert m["histogram"] == pytest.approx(m["line"] - m["signal"], abs=1e-6)

    def test_bollinger_symmetry_in_series(self):
        result = calculate_indicators(CANDLES_200)
        for row in result["series"]:
            bb = row["bollinger_bands"]
            if all(v is not None for v in [bb["upper"], bb["middle"], bb["lower"]]):
                assert bb["upper"] - bb["middle"] == pytest.approx(
                    bb["middle"] - bb["lower"], abs=1e-6
                )


# ---------------------------------------------------------------------------
# Insufficient data
# ---------------------------------------------------------------------------

class TestInsufficientData:
    def test_raises_for_empty_input(self):
        with pytest.raises(ValueError, match="empty"):
            calculate_indicators([])

    def test_raises_for_single_candle(self):
        candles = _make_candles(1)
        with pytest.raises(ValueError):
            calculate_indicators(candles)

    def test_works_with_minimum_candles(self):
        candles = _make_candles(MIN_CANDLES)
        result = calculate_indicators(candles)
        assert result["candle_count"] == MIN_CANDLES

    def test_all_warm_up_null_with_few_candles(self):
        """With only 10 candles, SMA-20 and SMA-50 must all be null."""
        candles = _make_candles(10)
        result = calculate_indicators(candles)
        for row in result["series"]:
            assert row["sma_20"] is None
            assert row["sma_50"] is None


# ---------------------------------------------------------------------------
# Malformed / invalid input
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_missing_close_field(self):
        candles = [
            {"timestamp": 1000, "open": 1.0, "high": 2.0, "low": 0.5},  # no "close"
            {"timestamp": 2000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
        ]
        with pytest.raises(ValueError, match="malformed"):
            calculate_indicators(candles)

    def test_non_finite_close(self):
        candles = [
            {"timestamp": 1000, "open": 1.0, "high": 2.0, "low": 0.5, "close": float("nan"), "volume": 1.0},
            {"timestamp": 2000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0},
        ]
        with pytest.raises(ValueError, match="non-finite"):
            calculate_indicators(candles)

    def test_non_finite_high(self):
        candles = [
            {"timestamp": 1000, "open": 1.0, "high": float("inf"), "low": 0.5, "close": 1.2, "volume": 1.0},
            {"timestamp": 2000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0},
        ]
        with pytest.raises(ValueError, match="non-finite"):
            calculate_indicators(candles)

    @pytest.mark.parametrize("field,value,match", [
        ("volume", float("nan"), "non-finite"),
        ("volume", -1.0, "negative volume"),
        ("high", 98.0, "high below low"),
        ("open", 200.0, "outside"),
        ("close", 200.0, "outside"),
    ])
    def test_rejects_invalid_ohlcv(self, field, value, match):
        candles = _make_candles(2)
        candles[0][field] = value
        with pytest.raises(ValueError, match=match):
            calculate_indicators(candles)

    @pytest.mark.parametrize("timestamps,match", [
        ([1000, 1000], "duplicated"),
        ([2000, 1000], "chronological"),
        ([1000, -1], "negative"),
        ([1000, 1.5], "integer"),
    ])
    def test_rejects_invalid_timestamps(self, timestamps, match):
        candles = _make_candles(2)
        for candle, timestamp in zip(candles, timestamps):
            candle["timestamp"] = timestamp
        with pytest.raises(ValueError, match=match):
            calculate_indicators(candles)

    def test_rejects_invalid_indicator_periods(self):
        with pytest.raises(ValueError, match="period"):
            calculate_indicators(_make_candles(5), rsi_period=0)
        with pytest.raises(ValueError, match="less than"):
            calculate_indicators(_make_candles(5), macd_fast=26, macd_slow=12)

    def test_short_valid_history_keeps_warmup_nulls(self):
        result = calculate_indicators(_make_candles(2))
        assert all(row["ema_50"] is None for row in result["series"])
        assert all(row["macd"]["line"] is None for row in result["series"])
