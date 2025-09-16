

from fastapi import APIRouter
from .config import (
    PROVIDER_MODE,
    WEATHER_TTL_S,
    DEFAULT_RADIUS_M,
    DEFAULT_SINCE_MIN,
    DEFAULT_LIMIT,
    ROUTE_RPS,
    WEATHER_RPS,
)

router = APIRouter()

@router.get("/config")
def get_config():
    return {
        "ok": True,
        "provider_mode": PROVIDER_MODE,
        "defaults": {
            "nearby_radius_m": DEFAULT_RADIUS_M,
            "nearby_since_min": DEFAULT_SINCE_MIN,
            "nearby_limit": DEFAULT_LIMIT,
        },
        "weather_ttl_s": WEATHER_TTL_S,
        "rate_limits": {
            "route_rps": ROUTE_RPS,
            "weather_rps": WEATHER_RPS,
        },
    }