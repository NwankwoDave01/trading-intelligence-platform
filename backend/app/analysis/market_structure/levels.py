"""Structural support and resistance zones from confirmed pivots."""

from __future__ import annotations

from typing import Any


def cluster_levels(swings: list[dict[str, Any]], tolerance: float) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for swing_type, zone_type in (("low", "support"), ("high", "resistance")):
        clusters: list[list[dict[str, Any]]] = []
        for swing in (s for s in swings if s["swing_type"] == swing_type):
            matches = [
                cluster for cluster in clusters
                if abs(swing["price"] - cluster[0]["price"]) <= tolerance
            ]
            if matches:
                min(matches, key=lambda c: abs(swing["price"] - c[0]["price"])).append(swing)
            else:
                clusters.append([swing])
        for cluster in clusters:
            prices = [point["price"] for point in cluster]
            zones.append({
                "zone_type": zone_type,
                "lower_bound": min(prices),
                "upper_bound": max(prices),
                "midpoint": sum(price / len(prices) for price in prices),
                "tolerance": tolerance,
                "contributing_swings": len(cluster),
                "source_swing_ids": [point["id"] for point in cluster],
                "source_timestamps": [point["timestamp"] for point in cluster],
                "confirmation_timestamps": [point["confirmation_candle_timestamp"] for point in cluster],
                "first_available_at": min(point["available_at"] for point in cluster),
                "last_available_at": max(point["available_at"] for point in cluster),
            })
    return sorted(zones, key=lambda zone: (zone["zone_type"], zone["lower_bound"]))
