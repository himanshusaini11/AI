import time
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from .db import SessionLocal

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        device_id = None
        auth = request.headers.get("authorization")
        if auth and auth.startswith("Device "):
            try:
                d = dict(kv.split("=",1) for kv in auth[7:].replace(" ","").split(","))
                device_id = d.get("device_id")
            except Exception:
                device_id = None
        resp = await call_next(request)
        ms = int((time.perf_counter() - start) * 1000)
        try:
            db = SessionLocal()
            db.execute(text("""
              INSERT INTO request_audit(device_id, method, path, status, ms, ip, meta)
              VALUES(:d,:m,:p,:s,:ms,:ip, '{}'::jsonb)
            """), {"d": device_id, "m": request.method, "p": request.url.path,
                   "s": resp.status_code, "ms": ms,
                   "ip": request.client.host if request.client else None})
            db.commit()
        except Exception:
            pass
        return resp