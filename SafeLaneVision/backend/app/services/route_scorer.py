import json
from dataclasses import dataclass

from sqlalchemy import text


@dataclass
class RouteScore:
    hazard_count: int
    cluster_weight: float


_SCORE_SQL = text(
    """
    SELECT
        COALESCE(SUM(count), 0) AS total_weight,
        COALESCE(SUM(count)::int, 0) AS cluster_sum
    FROM hazard_clusters
    WHERE ST_DWithin(
        centroid,
        ST_SetSRID(ST_GeomFromGeoJSON(:geojson)::geometry, 4326)::geography,
        :buffer_m
    )
    """
)


def score_route_by_clusters(session, coordinates, buffer_m=100.0) -> RouteScore:
    """Estimate hazard exposure for a route using cluster centroids.

    Args:
        session: SQLAlchemy session bound to the SafeLane database.
        coordinates: Sequence of [lon, lat] pairs describing the route polyline.
        buffer_m: Distance in meters to consider around the polyline.

    Returns:
        RouteScore describing total cluster count/weight within the buffer.
    """

    line_geojson = json.dumps({"type": "LineString", "coordinates": coordinates})
    row = session.execute(
        _SCORE_SQL,
        {"geojson": line_geojson, "buffer_m": float(buffer_m)},
    ).fetchone()
    if not row:
        return RouteScore(hazard_count=0, cluster_weight=0.0)
    return RouteScore(
        hazard_count=int(row.cluster_sum or 0),
        cluster_weight=float(row.total_weight or 0.0),
    )
