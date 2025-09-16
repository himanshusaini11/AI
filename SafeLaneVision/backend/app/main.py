from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router as core
from app.routes_status import router as status
from app.routes_clusters import router as clusters
from app.routes_provision import router as provision
from app.routes_hazards import router as hazards
from app.routes_frames import router as frames
from app.routes_events import router as events

from app.audit import AuditMiddleware
from app.routes_config import router as config_router
from app.config import CORS_ALLOW_ORIGINS

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