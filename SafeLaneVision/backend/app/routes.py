from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.db import SessionLocal
from sqlalchemy import text
from .ext_overpass import overpass
from .ext_weather import weather
from .ext_directions import cycle_route
from .auth import require_device
from .rl import limit
from .config import ALLOW_PUBLIC_READS


router=APIRouter()

class Geo(BaseModel):
    lat: float; lon: float; accuracy_m: Optional[float]=None

class EventIn(BaseModel):
    ts: str; device_id: str; geo: Geo; class_: str = "pothole"
    score: float; bbox_xyxy: List[float]; depth_m: float
    lane_offset_m: float; ttc_s: float; risk: float
    weather: dict | None = None; embed_id: str | None = None; frame_id: str | None = None

@router.post("/ingest/event")
def ingest_event(e: EventIn, device_id: str = Depends(require_device)):
    db = SessionLocal()
    db.execute(text("""
      INSERT INTO hazards (ts, geom, class, risk, scores, frame_id, ride_id, embed_id)
      VALUES (:ts, ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography, :class, :risk,
              jsonb_build_object('score',:score,'depth_m',:depth,'lane_offset_m',:off,'ttc_s',:ttc),
              :frame_id, NULL, :embed_id)
    """), {
        "ts": e.ts,
        "lon": e.geo.lon, "lat": e.geo.lat,
        "class": e.class_, "risk": e.risk,
        "score": e.score, "depth": e.depth_m, "off": e.lane_offset_m, "ttc": e.ttc_s,
        "frame_id": e.frame_id, "embed_id": e.embed_id
    })
    db.commit(); db.close()
    return {"ok": True}

@router.get("/overpass")
def q_overpass(lat:float, lon:float):
    try: return overpass(lat,lon)
    except Exception as e: raise HTTPException(502, detail=str(e))

@router.get("/weather")
def q_weather(lat:float, lon:float, throttle: None = Depends(limit("weather", rate=2.0, burst=5))):
    if not ALLOW_PUBLIC_READS:
        _ = Depends(require_device)  # enforce device header if you flip the flag
    try: return weather(lat,lon)
    except Exception as e: raise HTTPException(502, detail=str(e))

@router.get("/route")
def q_route(lat1:float, lon1:float, lat2:float, lon2:float,
            throttle: None = Depends(limit("route", rate=2.0, burst=4))):
    try: return cycle_route(lat1,lon1,lat2,lon2)
    except Exception as e: raise HTTPException(502, detail=str(e))