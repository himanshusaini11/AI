from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router as core
from app.routes_status import router as status
from app.routes_clusters import router as clusters
from app.routes_provision import router as provision
from app.routes_hazards import router as hazards
from app.routes_frames import router as frames
from app.routes_events import router as events
from app.routes_routesafe import router as routesafe

import os
import threading
import time
import logging

from app.audit import AuditMiddleware
from app.routes_config import router as config_router
from app.config import CORS_ALLOW_ORIGINS
from app.workers.clusters import refresh_clusters, ClusterJobConfig

log = logging.getLogger("safelane.cluster" )

app = FastAPI(title="SafeLane API", version="0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)
app.include_router(core, prefix="/v1")
app.include_router(status)
app.include_router(provision, prefix="/v1")
app.include_router(hazards, prefix="/v1")
app.include_router(clusters, prefix="/v1")
app.include_router(config_router, prefix="/v1")
app.include_router(frames, prefix="/v1")
app.include_router(events, prefix="/v1")
app.include_router(routesafe, prefix="/v1")


def _start_cluster_refresh_thread():
    if os.getenv("SAFECLUSTER_DISABLE_AUTO", "false").lower() == "true":
        log.info("automatic cluster refresh disabled via SAFECLUSTER_DISABLE_AUTO")
        return

    interval = int(os.getenv("CLUSTER_REFRESH_INTERVAL_S", "900") or 900)

    def _loop():
        cfg = ClusterJobConfig()
        while True:
            try:
                refresh_clusters(cfg)
                log.info("hazard clusters refreshed")
            except Exception:  # pragma: no cover
                log.exception("cluster refresh failed")
            time.sleep(interval)

    thread = threading.Thread(target=_loop, name="cluster-refresh", daemon=True)
    thread.start()


@app.on_event("startup")
async def _startup_tasks() -> None:
    _start_cluster_refresh_thread()
