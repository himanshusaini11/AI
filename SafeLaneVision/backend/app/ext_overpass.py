import os
import time
from typing import Any, Dict, Tuple
from .http import client, get_with_retry

Q = """[out:json][timeout:25];
(way["highway"="cycleway"](around:800,{lat},{lon});
 node["highway"="construction"](around:800,{lat},{lon}););
out geom;"""

def overpass(lat:float, lon:float):
    with client() as c:
        r = get_with_retry(c, "POST", "https://overpass-api.de/api/interpreter", data=Q.format(lat=lat,lon=lon))
        return r.json()

# Simple in-process cache for Overpass responses.
# Tunables via env:
#   OVERPASS_TTL_S       -> cache TTL in seconds (default 600)
#   OVERPASS_RADIUS_M    -> default search radius in meters (default 800)

OVERPASS_TTL_S: int = int(os.getenv("OVERPASS_TTL_S", "600"))
DEFAULT_RADIUS_M: int = int(os.getenv("OVERPASS_RADIUS_M", "800"))

Q = """[out:json][timeout:25];
(
  way["highway"="cycleway"](around:{r},{lat},{lon});
  node["highway"="construction"](around:{r},{lat},{lon});
);
out geom;"""

_CACHE: Dict[str, Tuple[float, Any]] = {}

def _key(lat: float, lon: float, r: int) -> str:
  # Round to ~10–12 m to improve hit rate without losing locality.
  return f"{round(lat, 4)}:{round(lon, 4)}:{r}"

def overpass(lat: float, lon: float, r: int = DEFAULT_RADIUS_M) -> Any:
  """
  Query Overpass API for cycleways and construction nodes around (lat, lon).
  Caches results in-process for OVERPASS_TTL_S seconds keyed by rounded lat/lon and radius.
  """
  now = time.time()
  k = _key(lat, lon, r)
  cached = _CACHE.get(k)
  if cached and cached[0] > now:
    return cached[1]

  with client() as c:
    resp = get_with_retry(
      c,
      "POST",
      "https://overpass-api.de/api/interpreter",
      data=Q.format(lat=lat, lon=lon, r=r),
    )
    data = resp.json()

  _CACHE[k] = (now + OVERPASS_TTL_S, data)

  # Best-effort eviction to avoid unbounded growth
  if len(_CACHE) > 256:
    expired = [kk for kk, (exp, _) in _CACHE.items() if exp <= now]
    for kk in expired[:128]:
      _CACHE.pop(kk, None)

  return data