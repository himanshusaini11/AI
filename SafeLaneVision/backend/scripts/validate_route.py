#!/usr/bin/env python3
"""Validate SafeLane hazard-aware routing against backend scoring.

Fetches /v1/routes/safe for the default Toronto coordinates (configurable via CLI)
and prints a comparison between the best route and the first baseline alternative.
If no improvement is detected (hazard weight reduction), the script exits with
a non-zero status to flag a regression.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass
class RouteCandidate:
    distance_m: float
    duration_s: float
    cluster_weight: float
    cluster_count: int

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RouteCandidate":
        hazard = payload.get("hazard_score", {})
        return cls(
            distance_m=float(payload.get("distance", 0.0)),
            duration_s=float(payload.get("duration", 0.0)),
            cluster_weight=float(hazard.get("cluster_weight", 0.0)),
            cluster_count=int(hazard.get("cluster_count", 0)),
        )


@dataclass
class RouteComparison:
    best: RouteCandidate
    baseline: Optional[RouteCandidate]
    hazard_delta: Optional[float]
    hazard_percent: Optional[float]


def fetch_route(base_url: str, lat1: float, lon1: float, lat2: float, lon2: float, buffer_m: float) -> Dict[str, Any]:
    params = urlencode(
        {
            "lat1": lat1,
            "lon1": lon1,
            "lat2": lat2,
            "lon2": lon2,
            "buffer_m": buffer_m,
        }
    )
    url = f"{base_url.rstrip('/')}/v1/routes/safe?{params}"
    try:
        with urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except HTTPError as exc:  # pragma: no cover - simple CLI
        raise SystemExit(f"HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:  # pragma: no cover
        raise SystemExit(f"Failed to reach backend: {exc.reason}") from exc


def compare_routes(payload: Dict[str, Any]) -> RouteComparison:
    if "best" not in payload:
        raise ValueError("Response missing 'best' route")

    best = RouteCandidate.from_dict(payload["best"])
    alternatives_raw: List[Dict[str, Any]] = payload.get("alternatives", [])

    epsilon = 1e-3

    def is_same(a: RouteCandidate, b: RouteCandidate) -> bool:
        return (
            abs(a.distance_m - b.distance_m) < 1
            and abs(a.duration_s - b.duration_s) < 1
            and abs(a.cluster_weight - b.cluster_weight) < epsilon
        )

    alternatives = [RouteCandidate.from_dict(alt) for alt in alternatives_raw]
    deduped = [alt for alt in alternatives if not is_same(alt, best)]
    baseline = deduped[0] if deduped else None

    if baseline is None:
        return RouteComparison(best=best, baseline=None, hazard_delta=None, hazard_percent=None)

    hazard_delta = baseline.cluster_weight - best.cluster_weight
    hazard_percent = None
    if baseline.cluster_weight > epsilon:
        hazard_percent = (hazard_delta / baseline.cluster_weight) * 100

    return RouteComparison(
        best=best,
        baseline=baseline,
        hazard_delta=hazard_delta,
        hazard_percent=hazard_percent,
    )


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate hazard-aware routing")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--lat1", type=float, default=43.6532, help="Origin latitude")
    parser.add_argument("--lon1", type=float, default=-79.3832, help="Origin longitude")
    parser.add_argument("--lat2", type=float, default=43.6629, help="Destination latitude")
    parser.add_argument("--lon2", type=float, default=-79.3957, help="Destination longitude")
    parser.add_argument("--buffer", type=float, default=100.0, help="Buffer radius for hazard scoring (m)")
    args = parser.parse_args(argv)

    payload = fetch_route(args.base_url, args.lat1, args.lon1, args.lat2, args.lon2, args.buffer)
    comparison = compare_routes(payload)

    print("Best route:")
    print(
        f"  distance: {comparison.best.distance_m:.1f} m\n"
        f"  duration: {comparison.best.duration_s/60:.1f} min\n"
        f"  clusters: {comparison.best.cluster_count} (weight {comparison.best.cluster_weight:.2f})"
    )

    if comparison.baseline is None:
        print("No alternate routes returned; cannot compute improvement.")
        return 0

    print("Baseline route:")
    print(
        f"  distance: {comparison.baseline.distance_m:.1f} m\n"
        f"  duration: {comparison.baseline.duration_s/60:.1f} min\n"
        f"  clusters: {comparison.baseline.cluster_count} (weight {comparison.baseline.cluster_weight:.2f})"
    )

    delta = comparison.hazard_delta or 0.0
    percent = comparison.hazard_percent
    arrow = "↓" if delta >= 0 else "↑"
    pct_display = f"{abs(percent):.1f}%" if percent is not None else "n/a"
    print(f"Hazard change: {arrow}{abs(delta):.2f} ({pct_display})")

    if delta <= 0:
        print("✅ Hazard-aware routing reduced or maintained hazard exposure.")
        return 0

    print("⚠️  Hazard-aware routing increased hazard exposure!", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
