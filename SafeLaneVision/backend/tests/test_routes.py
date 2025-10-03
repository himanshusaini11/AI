import os
import time
from datetime import datetime, timezone
import hmac
import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("DEVICE_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SAFECLUSTER_DISABLE_AUTO", "true")

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app import auth
from app.rl import limit
from app.routes_routesafe import _pick_best_route


client = TestClient(app)


def _auth_header(device_id: str = "ios-test", ts: int | None = None) -> str:
    if ts is None:
        ts = int(time.time())
    sig = hmac.new(
        os.environ["DEVICE_SECRET"].encode(),
        f"{device_id}.{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"Device device_id={device_id},ts={ts},sig={sig}"


def test_provision_upserts_device():
    mock_session = MagicMock()
    with patch("app.routes_provision.SessionLocal", return_value=mock_session):
        resp = client.post(
            "/v1/provision",
            json={"device_id": "ios-123", "platform": "ios"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


def test_hazards_nearby_returns_features(monkeypatch):
    row = (
        "haz-1",
        "pothole",
        0.7,
        datetime.now(timezone.utc),
        '{"type":"Point","coordinates":[-79.38,43.65]}',
    )
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [row]

    monkeypatch.setattr("app.routes_hazards.SessionLocal", lambda: mock_session)
    monkeypatch.setattr("app.routes_hazards.ALLOW_PUBLIC_READS", True, raising=False)

    resp = client.get(
        "/v1/hazards/nearby",
        params={"lat": 43.6532, "lon": -79.3832, "classes": "pothole"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["features"][0]["properties"]["class"] == "pothole"
    mock_session.close.assert_called_once()


def test_hazards_nearby_requires_auth_when_private(monkeypatch):
    monkeypatch.setattr("app.routes_hazards.ALLOW_PUBLIC_READS", False, raising=False)
    resp = client.get("/v1/hazards/nearby", params={"lat": 0, "lon": 0})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authorization required"


def test_hazards_clustered_returns_precomputed(monkeypatch):
    row = (
        42,
        "pothole",
        5,
        datetime.now(timezone.utc),
        '{"type":"Point","coordinates":[-79.38,43.65]}',
        '{"type":"Polygon","coordinates":[[[-79.39,43.64],[-79.37,43.64],[-79.37,43.66],[-79.39,43.66],[-79.39,43.64]]]}',
    )
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [row]

    monkeypatch.setattr("app.routes_clusters.SessionLocal", lambda: mock_session)
    monkeypatch.setattr("app.routes_clusters.ALLOW_PUBLIC_READS", True, raising=False)

    resp = client.get(
        "/v1/hazards/clustered",
        params={"lat": 43.6532, "lon": -79.3832},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["features"][0]["properties"]["cluster_id"] == 42
    assert data["features"][0]["properties"]["class"] == "pothole"
    mock_session.close.assert_called_once()


def test_rate_limiter_exhausts_tokens():
    limiter = limit("unit", rate=0.0, burst=2)
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))

    limiter(request)
    limiter(request)

    with pytest.raises(HTTPException) as excinfo:
        limiter(request)
    assert excinfo.value.status_code == 429


def test_verify_header_errors_on_bad_sig():
    ts = int(time.time())
    header = f"Device device_id=ios-test,ts={ts},sig=deadbeef"
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_header(header)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "bad signature"


def test_ingest_frame_upsert(monkeypatch):
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchone.return_value = ("frame-1",)
    monkeypatch.setattr("app.routes_frames.SessionLocal", lambda: mock_session)

    header = _auth_header()
    payload = {
        "frame_id": "frame-1",
        "ts": "2025-09-16T19:00:00Z",
        "geo": {"lat": 43.65, "lon": -79.38},
        "ride_id": None,
        "speed_mps": 5.5,
        "weather": {"visibility": 9000},
        "meta": {"fps": 12},
    }

    with patch("app.routes_frames.verify_header", return_value="ios-test"):
        resp = client.post(
            "/v1/ingest/frame",
            json=payload,
            headers={"Authorization": header},
        )

    assert resp.status_code == 201
    assert resp.json()["frame_id"] == "frame-1"
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


def test_routes_safe_selects_lowest_cluster_route(monkeypatch):
    raw_response = {
        "routes": [
            {
                "distance": 1200,
                "duration": 400,
                "geometry": {"coordinates": [[-79.4, 43.6], [-79.39, 43.61]]},
            },
            {
                "distance": 1250,
                "duration": 420,
                "geometry": {"coordinates": [[-79.38, 43.65], [-79.37, 43.66]]},
            },
        ]
    }

    class FakeResult:
        def __init__(self, weight, count):
            self.total_weight = weight
            self.cluster_sum = count

        def fetchone(self):
            return self

    class FakeSession:
        def __init__(self, responses):
            self.responses = responses
            self.executed = 0

        def execute(self, *_, **__):
            resp = self.responses[self.executed]
            self.executed += 1
            return resp

        def close(self):
            pass

    session = FakeSession([
        FakeResult(5.0, 5),
        FakeResult(2.0, 2),
    ])

    best, alternatives = _pick_best_route(raw_response, session, buffer_m=100.0)
    assert best["distance"] == 1250
    assert best["hazard_score"]["cluster_weight"] == 2.0
    assert len(alternatives) == 2


def test_routes_safe_endpoint(monkeypatch):
    raw_response = {
        "routes": [
            {
                "distance": 900,
                "duration": 300,
                "geometry": {"coordinates": [[-79.4, 43.6], [-79.39, 43.61]]},
            },
            {
                "distance": 950,
                "duration": 310,
                "geometry": {"coordinates": [[-79.38, 43.65], [-79.37, 43.66]]},
            },
        ]
    }

    class FakeResult:
        def __init__(self, weight, count):
            self.total_weight = weight
            self.cluster_sum = count

        def fetchone(self):
            return self

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def execute(self, *args, **kwargs):
            response = [FakeResult(3.0, 3), FakeResult(1.0, 1)][self.calls]
            self.calls += 1
            return response

        def close(self):
            pass

    monkeypatch.setattr("app.routes_routesafe.cycle_route", lambda *a, **k: raw_response)
    monkeypatch.setattr("app.routes_routesafe.SessionLocal", lambda: FakeSession())

    resp = client.get(
        "/v1/routes/safe",
        params={"lat1": 43.6, "lon1": -79.4, "lat2": 43.66, "lon2": -79.37},
        headers={"Authorization": _auth_header()},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["best"]["hazard_score"]["cluster_weight"] == 1.0
