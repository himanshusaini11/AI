import hmac, time
from hashlib import sha256
from fastapi import Header, HTTPException, Request
from typing import Optional, Tuple
from sqlalchemy import text
from .db import SessionLocal
from .config import DEVICE_SECRET, AUTH_CLOCK_SKEW_S

def _parse(auth: str) -> Tuple[str,int,str]:
    # Format: Authorization: Device device_id=abc,ts=1690000000,sig=hex
    if not auth.startswith("Device "): raise ValueError("bad scheme")
    parts = dict(kv.split("=",1) for kv in auth[7:].replace(" ","").split(","))
    return parts["device_id"], int(parts["ts"]), parts["sig"]

def _sign(device_id: str, ts: int) -> str:
    msg = f"{device_id}.{ts}".encode()
    return hmac.new(DEVICE_SECRET.encode(), msg, sha256).hexdigest()

def verify_header(auth_header: str) -> str:
    device_id, ts, sig = _parse(auth_header)
    now = int(time.time())
    if abs(now - ts) > AUTH_CLOCK_SKEW_S:
        raise HTTPException(401, detail="stale token")
    good = hmac.compare_digest(sig, _sign(device_id, ts))
    if not good: raise HTTPException(401, detail="bad signature")
    return device_id

async def require_device(request: Request, authorization: Optional[str]=Header(None)) -> str:
    if not authorization:
        raise HTTPException(401, detail="Authorization required")
    device_id = verify_header(authorization)
    # upsert device + last_seen
    db = SessionLocal()
    db.execute(text("""
        INSERT INTO devices(device_id, platform, last_seen)
        VALUES(:d, :p, now())
        ON CONFLICT (device_id) DO UPDATE SET last_seen=now()
    """), {"d": device_id, "p": request.headers.get("X-Device-Platform","unknown")})
    db.commit(); db.close()
    return device_id