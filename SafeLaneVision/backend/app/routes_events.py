from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB

from .db import SessionLocal
from .auth import verify_header

router = APIRouter()

class Geo(BaseModel):
    lat: float
    lon: float
    accuracy_m: Optional[float] = None

class EventIn(BaseModel):
    ts: datetime
    device_id: Optional[str] = None
    ride_id: Optional[str] = None           # UUID string or None
    frame_id: Optional[str] = None
    geo: Geo
    class_: str = Field(alias="class_")
    score: float
    bbox_xyxy: List[float]
    depth_m: Optional[float] = None
    lane_offset_m: Optional[float] = None
    ttc_s: Optional[float] = None
    risk: float
    embed_id: Optional[str] = None
    weather: Optional[Dict[str, Any]] = None

@router.post("/ingest/event", status_code=201)
def ingest_event(e: EventIn, authorization: Optional[str] = Header(default=None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    verify_header(authorization)  # HMAC check

    scores = {
        "score": e.score,
        "bbox_xyxy": e.bbox_xyxy,
        "depth_m": e.depth_m,
        "lane_offset_m": e.lane_offset_m,
        "ttc_s": e.ttc_s,
        "weather": e.weather or {},
    }

    sql = text("""
      INSERT INTO hazards (ts, geom, class, risk, scores, ride_id, frame_id, embed_id)
      VALUES (
        :ts,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :class,
        :risk,
        :scores,
        :ride_id,
        :frame_id,
        :embed_id
      )
      RETURNING hazard_id
    """).bindparams(bindparam("scores", type_=JSONB))

    params = {
        "ts": e.ts,
        "lon": e.geo.lon,
        "lat": e.geo.lat,
        "class": e.class_,      # maps to DB column "class"
        "risk": e.risk,
        "scores": scores,
        "ride_id": e.ride_id,   # None or UUID string
        "frame_id": e.frame_id,
        "embed_id": e.embed_id,
    }

    db = SessionLocal()
    try:
        row = db.execute(sql, params).fetchone()
        db.commit()
    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"event_insert_error: {ex}")
    finally:
        db.close()

    return {"ok": True, "hazard_id": row[0]}