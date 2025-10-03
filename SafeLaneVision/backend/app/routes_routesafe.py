from fastapi import APIRouter, HTTPException, Depends, Header

from .ext_directions import cycle_route
from .services.route_scorer import score_route_by_clusters
from .db import SessionLocal
from .rl import limit
from .config import ALLOW_PUBLIC_READS
from .auth import verify_header


router = APIRouter()


def _pick_best_route(mapbox_response, session, buffer_m=100.0):
    routes = mapbox_response.get("routes", [])
    scored = []
    for idx, route in enumerate(routes):
        geometry = route.get("geometry", {})
        coords = geometry.get("coordinates")
        if not coords:
            continue
        score = score_route_by_clusters(session, coords, buffer_m=buffer_m)
        route_copy = dict(route)
        route_copy["hazard_score"] = {
            "cluster_count": score.hazard_count,
            "cluster_weight": score.cluster_weight,
        }
        scored.append(route_copy)
    if not scored:
        return None, []
    best = min(scored, key=lambda r: (r["hazard_score"]["cluster_weight"], r.get("distance", 0)))
    return best, scored


@router.get("/routes/safe")
def safest_route(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    buffer_m: float = 100.0,
    authorization: str | None = Header(default=None),
    throttle: None = Depends(limit("route_safe", rate=1.0, burst=3)),
):
    if not ALLOW_PUBLIC_READS:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization required")
        verify_header(authorization)
    session = SessionLocal()
    try:
        raw = cycle_route(lat1, lon1, lat2, lon2)
        best, alternatives = _pick_best_route(raw or {}, session, buffer_m=buffer_m)
    except Exception as exc:  # pragma: no cover
        session.close()
        raise HTTPException(status_code=502, detail=f"routing_error: {exc}")
    finally:
        session.close()

    if best is None:
        raise HTTPException(status_code=502, detail="no_routes_returned")

    return {
        "best": best,
        "alternatives": alternatives,
    }
