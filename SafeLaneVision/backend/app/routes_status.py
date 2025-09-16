from fastapi import APIRouter
import os

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True}

@router.get("/config")
def config():
    return {
        "provider_mode": os.getenv("PROVIDER_MODE", "free"),
        "http_timeout_s": float(os.getenv("HTTP_TIMEOUT_S", "15") or 15),
        "has_openweather": bool(os.getenv("OPENWEATHER_KEY")),
        "has_mapbox": bool(os.getenv("MAPBOX_TOKEN")),
    }