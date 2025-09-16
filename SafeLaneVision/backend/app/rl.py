import time
from fastapi import Request, HTTPException

_buckets = {}  # key -> (tokens, last_ts)

def limit(scope: str, rate: float=1.0, burst: int=3):
    def dep(request: Request):
        # prefer device id if present, else client IP
        aid = request.headers.get("X-Device-Id")
        key = f"{scope}:{aid or request.client.host}"
        now = time.monotonic()
        tokens, last = _buckets.get(key, (float(burst), now))
        # refill
        tokens = min(float(burst), tokens + rate * (now - last))
        if tokens < 1.0:
            raise HTTPException(429, detail="rate_limited")
        tokens -= 1.0
        _buckets[key] = (tokens, now)
    return dep