from fastapi import APIRouter, Header, HTTPException
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from .db import SessionLocal
from .config import ALLOW_PUBLIC_READS
from .auth import verify_header
import json

router = APIRouter()

@router.get("/hazards/clustered")
def hazards_clustered(
    lat: float,
    lon: float,
    r: int = 800,
    eps_m: int = 50,
    min_pts: int = 3,
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
    eps_m = max(1, min(int(eps_m), 500))
    min_pts = max(1, min(int(min_pts), 50))
    limit = max(1, min(int(limit), 200))
    since_min = max(1, int(since_min))

    cls_str: Optional[str] = None
    if classes:
        parts = [c.strip() for c in classes.split(",") if c.strip()]
        if parts:
            cls_str = ",".join(parts)

    sql = """
    WITH q AS (
      SELECT hazard_id, class, risk, ts, geom
      FROM hazards
      WHERE ST_DWithin(
              geom,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :r
            )
        AND ts >= now() - (CAST(:since_min AS integer) * interval '1 minute')
    ),
    g AS (
      SELECT *,
        ST_ClusterDBSCAN(
          ST_Transform(geom::geometry, 3857),
          eps := :eps_m,
          minpoints := :min_pts
        ) OVER () AS cid
      FROM q
    )
    SELECT
      cid,
      COUNT(*) AS count,
      MIN(ts) AS first_ts,
      MAX(ts) AS last_ts,
      ARRAY_AGG(hazard_id ORDER BY ts DESC) AS members,
      ARRAY_AGG(class) AS classes,
      ST_AsGeoJSON(ST_Centroid(ST_Collect(geom::geometry))) AS centroid,
      ST_AsGeoJSON(ST_Envelope(ST_Collect(geom::geometry))) AS bbox
    FROM g
    WHERE cid IS NOT NULL
    {class_filter}
    GROUP BY cid
    ORDER BY count DESC
    LIMIT CAST(:lim AS integer)
    """

    class_filter_sql = ""
    params = {"lat": lat, "lon": lon, "r": r, "since_min": since_min,
              "eps_m": eps_m, "min_pts": min_pts, "lim": limit}
    if cls_str:
        class_filter_sql = "HAVING BOOL_OR(class = ANY(string_to_array(:cls, ',')))"
        params["cls"] = cls_str
    sql = sql.format(class_filter=class_filter_sql)

    db = SessionLocal()
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"cluster_query_error: {e}")
    finally:
        db.close()

    def class_hist(classes: List[str]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for c in classes or []:
            out[c] = out.get(c, 0) + 1
        return out

    features: List[Dict[str, Any]] = []
    for cid, count, first_ts, last_ts, members, classes_arr, centroid_gj, bbox_gj in rows:
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
                "cluster_id": int(cid),
                "count": int(count),
                "first_ts": first_ts.isoformat() if first_ts else None,
                "last_ts": last_ts.isoformat() if last_ts else None,
                "members": [str(m) for m in (members or [])],
                "class_hist": class_hist(classes_arr or []),
                "bbox": bbox
            }
        })
    return {"type": "FeatureCollection", "features": features}