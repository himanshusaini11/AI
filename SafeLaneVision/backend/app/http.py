import httpx
from .config import HTTP_TIMEOUT_S

def client():
    return httpx.Client(timeout=HTTP_TIMEOUT_S, headers={"User-Agent":"SafeLane/0.1"})

def aclient():
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT_S, headers={"User-Agent":"SafeLane/0.1"})

def get_with_retry(c, method, url, **kw):
    for i in range(3):
        try:
            r = c.request(method, url, **kw)
            r.raise_for_status()
            return r
        except httpx.HTTPError as e:
            if i == 2: raise