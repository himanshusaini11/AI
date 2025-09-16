from fastapi import APIRouter, Header
from pydantic import BaseModel
from sqlalchemy import text
from .db import SessionLocal

router = APIRouter()

class ProvisionIn(BaseModel):
    device_id: str
    platform: str = "unknown"

@router.post("/provision")
def provision(p: ProvisionIn, authorization: str | None = Header(default=None)):
    db = SessionLocal()
    db.execute(text("""
      INSERT INTO devices(device_id, platform, last_seen)
      VALUES(:d,:p, now())
      ON CONFLICT (device_id) DO UPDATE SET platform=:p, last_seen=now()
    """), {"d": p.device_id, "p": p.platform})
    db.commit(); db.close()
    # minimal config for client boot
    return {
        "ok": True,
        "device_id": p.device_id,
        "classes": ["pothole","debris","cone","lane_block","flood","ice"],
        "overpass_radius_m": 800,
        "weather_ttl_s": 300,
        "rate_limits": {"weather_rps": 1.0, "route_rps": 1.0}
    }