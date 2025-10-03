import os
import time
import uuid
import hmac
import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("DEVICE_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _auth_header(device_id: str = "ios-test", ts: int | None = None) -> tuple[int, str]:
    if ts is None:
        ts = int(time.time())
    msg = f"{device_id}.{ts}".encode()
    secret = os.environ["DEVICE_SECRET"].encode()
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    header = f"Device device_id={device_id},ts={ts},sig={sig}"
    return ts, header


def _sample_payload(ts_iso: str) -> dict:
    return {
        "ts": ts_iso,
        "device_id": "ios-test",
        "ride_id": None,
        "frame_id": "frame-123",
        "geo": {"lat": 43.6532, "lon": -79.3832},
        "class_": "pothole",
        "score": 0.87,
        "bbox_xyxy": [5, 6, 25, 30],
        "depth_m": 2.3,
        "lane_offset_m": 0.2,
        "ttc_s": 1.4,
        "risk": 0.61,
        "embed_id": "embed-42",
        "weather": {"visibility": 9.0},
    }


def test_ingest_event_success():
    hazard_id = uuid.uuid4()
    ts, auth_header = _auth_header()
    payload = _sample_payload(datetime.now(timezone.utc).isoformat())

    with patch("app.routes_events.SessionLocal") as session_factory:
        session = MagicMock()
        session_factory.return_value = session

        result = MagicMock()
        result.fetchone.return_value = (hazard_id,)
        session.execute.return_value = result

        response = client.post(
            "/v1/ingest/event",
            json=payload,
            headers={"Authorization": auth_header},
        )

    assert response.status_code == 201
    assert response.json() == {"ok": True, "hazard_id": str(hazard_id)}

    session.execute.assert_called_once()
    session.commit.assert_called_once()
    session.close.assert_called_once()

    call_args, _ = session.execute.call_args
    params = call_args[1]
    assert params["class"] == payload["class_"]
    assert params["ride_id"] == payload["ride_id"]
    assert params["frame_id"] == payload["frame_id"]


def test_ingest_event_requires_auth():
    payload = _sample_payload(datetime.now(timezone.utc).isoformat())

    response = client.post("/v1/ingest/event", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization required"
