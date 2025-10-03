from fastapi import APIRouter, HTTPException, Depends
from .ext_overpass import overpass
from .ext_weather import weather
from .ext_directions import cycle_route
from .auth import require_device
from .rl import limit
from .config import ALLOW_PUBLIC_READS


router=APIRouter()

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
