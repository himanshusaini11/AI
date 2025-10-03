#!/usr/bin/env python3
"""Manual entry point to recompute hazard clusters."""

import argparse

from app.workers.clusters import ClusterJobConfig, refresh_clusters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute hazard clusters")
    defaults = ClusterJobConfig()
    parser.add_argument(
        "--lookback-min",
        type=int,
        default=defaults.lookback_min,
        help="Minutes of hazard history to cluster (default: %(default)s)",
    )
    parser.add_argument(
        "--grid-deg",
        type=float,
        default=defaults.grid_deg,
        help="Grid size in degrees for clustering snap (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = ClusterJobConfig(lookback_min=args.lookback_min, grid_deg=args.grid_deg)
    refresh_clusters(cfg)


if __name__ == "__main__":
    main()
