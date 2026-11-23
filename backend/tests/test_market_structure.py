"""Deterministic, offline tests for market structure calculations."""

from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.analysis.market_structure import calculate_market_structure
from backend.app.analysis.market_structure.breaks import detect_breaks
from backend.app.analysis.market_structure.levels import cluster_levels
from backend.app.analysis.market_structure.swings import detect_swings
from backend.app.analysis.market_structure.trend import classify_trend


def make_candles(highs: list[float], lows: list[float] | None = None, closes: list[float] | None = None) -> list[dict]:
    lows = lows or [high - 2 for high in highs]
    closes = closes or [(high + low) / 2 for high, low in zip(highs, lows)]
    return [{
        "timestamp": 1_700_000_000_000 + i * 3_600_000,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1.0,
    } for i, (high, low, close) in enumerate(zip(highs, lows, closes))]


def test_swing_confirmation_waits_for_right_bars_and_records_availability():
    candles = make_candles([1, 2, 5, 2, 1, 2, 3])
    result = calculate_market_structure(candles, left_bars=2, right_bars=2)
    high = next(point for point in result["confirmed_swings"] if point["swing_type"] == "high")
    assert high["timestamp"] == candles[2]["timestamp"]
    assert high["confirmation_candle_timestamp"] == candles[4]["timestamp"]
    assert high["available_at"] == candles[4]["timestamp"] + 3_600_000
    assert high["confirmation_delay_bars"] == 2


def test_equal_highs_and_lows_disqualify_tied_pivots():
    candles = make_candles([1, 3, 3, 1], [0, -2, -2, 0])
    assert detect_swings(candles, 1, 1, 3_600_000) == []


def test_insufficient_left_or_right_history_produces_no_swings():
    assert detect_swings(make_candles([1, 5]), 2, 1, 3_600_000) == []
    assert detect_swings(make_candles([1, 5, 1]), 1, 2, 3_600_000) == []


def test_swing_classification_compares_only_matching_swing_types():
    candles = make_candles([1, 5, 2, 6, 3, 4, 1, 3, 0], [0, 1, -2, 2, -1, 1, -3, 0, -4])
    swings = detect_swings(candles, 1, 1, 3_600_000)
    highs = [item["classification"] for item in swings if item["swing_type"] == "high"]
    lows = [item["classification"] for item in swings if item["swing_type"] == "low"]
    assert highs == [None, "HH", "LH", "LH"]
    assert lows == [None, "HL", "LL"]


def test_trend_requires_agreeing_confirmed_high_and_low_structure():
    assert classify_trend([]) == "undetermined"
    assert classify_trend([{"swing_type": "high", "classification": "HH"}]) == "undetermined"
    bullish = [
        {"swing_type": "high", "classification": "HH"},
        {"swing_type": "low", "classification": "HL"},
    ]
    bearish = [
        {"swing_type": "high", "classification": "LH"},
        {"swing_type": "low", "classification": "LL"},
    ]
    assert classify_trend(bullish) == "bullish"
    assert classify_trend(bearish) == "bearish"
    assert classify_trend([bullish[0], {"swing_type": "low", "classification": "LL"}]) == "ranging"


def test_bullish_bos_and_choch_require_close_crossing():
    highs = [2, 5, 3, 4, 2, 3, 4, 4, 6]
    lows = [0, 1, -1, 0, -2, -1, 0, 0, 2]
    closes = [1, 4, 2, 3, 0, 2, 3, 3, 5.5]
    result = calculate_market_structure(make_candles(highs, lows, closes), left_bars=1, right_bars=1)
    assert any(event["event_type"] in {"BOS", "CHoCH"} for event in result["break_events"])
    assert all(event["available_at"] > event["confirmation_candle_timestamp"] for event in result["break_events"])


def test_wick_cross_without_close_is_only_an_unconfirmed_potential():
    candles = make_candles([2, 5, 3, 4, 2, 3, 4, 4, 6], [0, 1, -1, 0, -2, -1, 0, 0, 2], [1, 4, 2, 3, 0, 2, 3, 3, 3.5])
    result = calculate_market_structure(candles, left_bars=1, right_bars=1)
    assert not any(event["confirmation_candle_timestamp"] == candles[-1]["timestamp"] for event in result["break_events"])
    assert result["potential_breaks"]
    assert all(event["status"] == "unconfirmed" for event in result["potential_breaks"])


@pytest.mark.parametrize(
    ("trend", "direction", "expected"),
    [
        ("bullish", "bullish", "BOS"),
        ("bearish", "bearish", "BOS"),
        ("bullish", "bearish", "CHoCH"),
        ("bearish", "bullish", "CHoCH"),
    ],
)
def test_bos_and_choch_classify_both_break_directions(trend, direction, expected):
    high_class, low_class = ("HH", "HL") if trend == "bullish" else ("LH", "LL")
    swings = [
        {"id": "high:0", "swing_type": "high", "price": 10.0, "timestamp": 1,
         "confirmation_index": 0, "confirmation_candle_timestamp": 1,
         "available_at": 101, "classification": high_class},
        {"id": "low:0", "swing_type": "low", "price": 5.0, "timestamp": 1,
         "confirmation_index": 0, "confirmation_candle_timestamp": 1,
         "available_at": 101, "classification": low_class},
    ]
    prior_close, crossing_close = (9.0, 11.0) if direction == "bullish" else (6.0, 4.0)
    candles = [
        {"timestamp": 100, "close": prior_close, "high": 11.0, "low": 4.0},
        {"timestamp": 200, "close": crossing_close,
         "high": 12.0 if direction == "bullish" else crossing_close + 1,
         "low": crossing_close - 1 if direction == "bullish" else 3.0},
    ]
    events, _ = detect_breaks(candles, swings, 0.0, 100)
    assert len(events) == 1
    assert events[0]["event_type"] == expected
    assert events[0]["direction"] == direction


def test_break_that_precedes_pivot_confirmation_is_never_backdated():
    swings = [
        {"id": "high:1", "swing_type": "high", "price": 10.0, "timestamp": 100,
         "confirmation_index": 1, "confirmation_candle_timestamp": 200,
         "available_at": 300, "classification": "HH"},
        {"id": "low:1", "swing_type": "low", "price": 5.0, "timestamp": 100,
         "confirmation_index": 1, "confirmation_candle_timestamp": 200,
         "available_at": 300, "classification": "HL"},
    ]
    candles = [
        {"timestamp": 100, "close": 9.0, "high": 10.0, "low": 5.0},
        {"timestamp": 200, "close": 11.0, "high": 12.0, "low": 8.0},
        {"timestamp": 300, "close": 12.0, "high": 13.0, "low": 9.0},
    ]
    events, _ = detect_breaks(candles, swings, 0.0, 100)
    assert events == []


def test_break_buffer_delays_close_confirmation():
    candles = make_candles([2, 5, 3, 4, 2, 3, 4, 4, 6], [0, 1, -1, 0, -2, -1, 0, 0, 2], [1, 4, 2, 3, 0, 2, 3, 3, 4.5])
    no_buffer = calculate_market_structure(candles, "1h", 1, 1, 0.0)
    buffered = calculate_market_structure(candles, "1h", 1, 1, 1.0)
    assert no_buffer["break_events"]
    assert buffered["break_events"] == []


def test_break_events_do_not_duplicate_same_source_level():
    candles = make_candles([2, 5, 3, 4, 2, 3, 4, 4, 6, 7, 8], [0, 1, -1, 0, -2, -1, 0, 0, 2, 3, 4], [1, 4, 2, 3, 0, 2, 3, 3, 5.5, 6.5, 7.5])
    result = calculate_market_structure(candles, left_bars=1, right_bars=1)
    keys = [(event["source_swing_id"], event["direction"]) for event in result["break_events"]]
    assert len(keys) == len(set(keys))


def test_support_resistance_zone_clustering_preserves_source_swings():
    swings = [
        {"id": "low:1", "swing_type": "low", "price": 100.0, "timestamp": 1, "confirmation_candle_timestamp": 2, "available_at": 3},
        {"id": "low:2", "swing_type": "low", "price": 100.4, "timestamp": 4, "confirmation_candle_timestamp": 5, "available_at": 6},
        {"id": "high:3", "swing_type": "high", "price": 110.0, "timestamp": 7, "confirmation_candle_timestamp": 8, "available_at": 9},
    ]
    zones = cluster_levels(swings, 0.5)
    support = next(zone for zone in zones if zone["zone_type"] == "support")
    assert support["contributing_swings"] == 2
    assert support["source_swing_ids"] == ["low:1", "low:2"]
    assert support["lower_bound"] == 100.0
    assert support["upper_bound"] == 100.4


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_invalid_ohlcv_or_parameters_are_rejected(bad):
    candles = make_candles([1, 3, 1])
    malformed = deepcopy(candles)
    malformed[1]["high"] = bad
    with pytest.raises(ValueError):
        calculate_market_structure(malformed)
    with pytest.raises(ValueError):
        calculate_market_structure(candles, break_buffer=bad)


def test_empty_data_and_bad_timestamp_order_are_rejected():
    with pytest.raises(ValueError):
        calculate_market_structure([])
    candles = make_candles([1, 3, 1])
    candles[2]["timestamp"] = candles[1]["timestamp"]
    with pytest.raises(ValueError):
        calculate_market_structure(candles)
