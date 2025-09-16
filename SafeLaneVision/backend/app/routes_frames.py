

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
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

class FrameIn(BaseModel):
    frame_id: str
    ts: datetime
    device_id: Optional[str] = None
    ride_id: Optional[str] = None  # UUID string or None
    geo: Geo
    speed_mps: Optional[float] = None
    weather: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

@router.post("/ingest/frame", status_code=201)
def ingest_frame(
    f: FrameIn,
    authorization: Optional[str] = Header(default=None),
):
    """
    Store per-frame telemetry. Requires HMAC device auth.
    Upserts by frame_id to be idempotent.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    # Will raise HTTPException if invalid
    #verify_header(authorization, expected_device_id=f.device_id)
    verify_header(authorization)  # raises 401 if bad HMAC

    sql = text(

                """
                INSERT INTO frames (frame_id, ride_id, ts, geom, speed_mps, weather, meta)
                VALUES (
                    :frame_id,
                    :ride_id,
                    :ts,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :speed_mps,
                    COALESCE(:weather, '{}'::jsonb),
                    COALESCE(:meta, '{}'::jsonb)
                )
                ON CONFLICT (frame_id) DO UPDATE
                SET
                    ts = EXCLUDED.ts,
                    geom = EXCLUDED.geom,
                    speed_mps = EXCLUDED.speed_mps,
                    weather = COALESCE(frames.weather, '{}'::jsonb) || EXCLUDED.weather,
                    meta = COALESCE(frames.meta, '{}'::jsonb) || EXCLUDED.meta
                RETURNING frame_id
                """
                ).bindparams(
                    bindparam("weather", type_=JSONB),
                    bindparam("meta", type_=JSONB),
                    )

    params = {
            "frame_id": f.frame_id,
            "ride_id": f.ride_id,          # None or UUID string both OK
            "ts": f.ts,                    # pass datetime, not iso string
            "lat": f.geo.lat,
            "lon": f.geo.lon,
            "speed_mps": f.speed_mps,
            "weather": f.weather or {},    # dict -> JSONB
            "meta": f.meta or {},          # dict -> JSONB
            }

    db = SessionLocal()
    try:
        row = db.execute(sql, params).fetchone()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"frame_insert_error: {e}")
    finally:
        db.close()

    return {"ok": True, "frame_id": row[0] if row else f.frame_id}