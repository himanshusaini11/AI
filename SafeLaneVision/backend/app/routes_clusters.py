from fastapi import APIRouter, Header, HTTPException
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from .db import SessionLocal
from .config import ALLOW_PUBLIC_READS
from .auth import verify_header
import json

router = APIRouter()

CLUSTER_SQL = """
  SELECT
    cluster_id,
    class,
    count,
    last_ts,
    ST_AsGeoJSON(centroid::geometry) AS centroid,
    ST_AsGeoJSON(bbox::geometry) AS bbox
  FROM hazard_clusters
  WHERE ST_DWithin(
          centroid,
          ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
          :r
        )
    AND last_ts >= now() - (CAST(:since_min AS integer) * interval '1 minute')
    {class_filter}
  ORDER BY last_ts DESC
  LIMIT CAST(:lim AS integer)
"""


@router.get("/hazards/clustered")
def hazards_clustered(
    lat: float,
    lon: float,
    r: int = 800,
    since_min: int = 1440,
    limit: int = 50,
    classes: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    if not ALLOW_PUBLIC_READS:
        if not authorization:
            raise HTTPException(401, detail="Authorization required")
        verify_header(authorization)

    r = max(1, min(int(r), 5000))
    limit = max(1, min(int(limit), 200))
    since_min = max(1, int(since_min))

    cls_str: Optional[str] = None
    if classes:
        parts = [c.strip() for c in classes.split(",") if c.strip()]
        if parts:
            cls_str = ",".join(parts)

    class_filter_sql = ""
    params = {
        "lat": lat,
        "lon": lon,
        "r": r,
        "since_min": since_min,
        "lim": limit,
    }
    if cls_str:
        class_filter_sql = " AND class = ANY(string_to_array(:cls, ','))"
        params["cls"] = cls_str

    sql = CLUSTER_SQL.format(class_filter=class_filter_sql)

    db = SessionLocal()
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"cluster_query_error: {e}")
    finally:
        db.close()

    features: List[Dict[str, Any]] = []
    for cluster_id, cls, count, last_ts, centroid_gj, bbox_gj in rows:
        try:
            centroid = json.loads(centroid_gj) if centroid_gj else None
        except Exception:
            centroid = None
        try:
            bbox = json.loads(bbox_gj) if bbox_gj else None
        except Exception:
            bbox = None

        features.append({
            "type": "Feature",
            "geometry": centroid,
            "properties": {
                "cluster_id": int(cluster_id),
                "count": int(count),
                "last_ts": last_ts.isoformat() if last_ts else None,
                "class": cls,
                "bbox": bbox,
            },
        })
    return {"type": "FeatureCollection", "features": features}
