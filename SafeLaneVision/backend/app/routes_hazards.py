from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from sqlalchemy import text
from .db import SessionLocal
from .config import ALLOW_PUBLIC_READS
from .auth import verify_header
import json
import logging
log = logging.getLogger(__name__)

router = APIRouter()

@router.get("/hazards/nearby")
def hazards_nearby(
    lat: float,
    lon: float,
    r: int = 800,
    classes: Optional[str] = None,   # comma-separated: "pothole,cone"
    since_min: int = 1440,
    limit: int = 200,
    authorization: Optional[str] = Header(default=None),
):
    if not ALLOW_PUBLIC_READS:
        if not authorization:
            raise HTTPException(401, detail="Authorization required")
        verify_header(authorization)

    r = max(1, min(int(r), 5000))
    limit = max(1, min(int(limit), 1000))
    since_min = max(1, int(since_min))

    # normalize class list to a clean comma-separated string
    cls_str: Optional[str] = None
    if classes:
        parts = [c.strip() for c in classes.split(",") if c.strip()]
        if parts:
            cls_str = ",".join(parts)

    sql = """
      SELECT hazard_id, class, risk, ts,
             ST_AsGeoJSON(geom::geometry) AS geojson
      FROM hazards
      WHERE ST_DWithin(
              geom,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :r
            )
        AND ts >= now() - (CAST(:since_min AS integer) * interval '1 minute')
    """
    if cls_str:
        sql += " AND class = ANY(string_to_array(:cls, ','))"
    sql += " ORDER BY ts DESC LIMIT CAST(:lim AS integer)"

    params = {
        "lat": lat,
        "lon": lon,
        "r": r,
        "since_min": since_min,
        "lim": limit,
    }
    if cls_str:
        params["cls"] = cls_str

    db = SessionLocal()
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        log.exception("hazards_nearby query failed")
        raise HTTPException(status_code=500, detail=f"query_error: {e}")
    finally:
        db.close()

    features = []
    for hazard_id, cls, risk, ts, gj in rows:
        geom = None
        try:
            geom = json.loads(gj) if gj else None
        except Exception:
            pass
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "hazard_id": str(hazard_id),
                "class": cls,
                "risk": float(risk) if risk is not None else None,
                "ts": ts.isoformat() if ts else None,
            }
        })
    return {"type": "FeatureCollection", "features": features}