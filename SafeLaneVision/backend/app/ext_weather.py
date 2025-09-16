import math, time
from .http import client, get_with_retry
from .config import OPENWEATHER_KEY

_CACHE = {}  # key -> (expires, json)
TTL_S = 300

def _round(x): return round(float(x), 3)  # ~110 m; adjust if you want

def _get_cached(key):
    v = _CACHE.get(key)
    if not v: return None
    exp, j = v
    if time.time() > exp: _CACHE.pop(key, None); return None
    return j

def _set_cached(key, j): _CACHE[key] = (time.time()+TTL_S, j)

def weather(lat: float, lon: float):
    if not OPENWEATHER_KEY: return {"error":"OPENWEATHER_KEY missing"}
    key = ("ow", _round(lat), _round(lon))
    j = _get_cached(key)
    if j: return j
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={OPENWEATHER_KEY}"
    with client() as c:
        j = get_with_retry(c, "GET", url).json()
        _set_cached(key, j)
        return j