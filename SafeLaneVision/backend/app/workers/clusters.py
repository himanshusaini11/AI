from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.db import SessionLocal

DEFAULT_LOOKBACK_MIN = 1440
DEFAULT_GRID_DEG = 0.0005

TRUNCATE_SQL = text("TRUNCATE hazard_clusters")

INSERT_SQL = text(
    """
    INSERT INTO hazard_clusters (class, centroid, count, bbox, last_ts)
    SELECT
      class,
      ST_Centroid(ST_Collect(geom::geometry))::geography AS centroid,
      COUNT(*) AS count,
      ST_Envelope(ST_Collect(geom::geometry))::geography AS bbox,
      MAX(ts) AS last_ts
    FROM hazards
    WHERE ts >= now() - CAST(:lookback_min AS integer) * interval '1 minute'
    GROUP BY class, ST_SnapToGrid(geom::geometry, :grid_deg)
    ORDER BY last_ts DESC
    """
)


@dataclass
class ClusterJobConfig:
    lookback_min: int = DEFAULT_LOOKBACK_MIN
    grid_deg: float = DEFAULT_GRID_DEG


def refresh_clusters(config: ClusterJobConfig | None = None) -> None:
    cfg = config or ClusterJobConfig()
    session = SessionLocal()
    try:
        session.execute(TRUNCATE_SQL)
        session.execute(
            INSERT_SQL,
            {
                "lookback_min": cfg.lookback_min,
                "grid_deg": cfg.grid_deg,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
