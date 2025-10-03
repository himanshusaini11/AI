import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SAFECLUSTER_DISABLE_AUTO", "true")

from app.workers.clusters import ClusterJobConfig, refresh_clusters, INSERT_SQL, TRUNCATE_SQL


def test_refresh_clusters_executes_expected_sql(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr("app.workers.clusters.SessionLocal", lambda: session)

    cfg = ClusterJobConfig(lookback_min=60, grid_deg=0.0002)
    refresh_clusters(cfg)

    session.execute.assert_any_call(TRUNCATE_SQL)
    session.execute.assert_any_call(
        INSERT_SQL,
        {"lookback_min": cfg.lookback_min, "grid_deg": cfg.grid_deg},
    )
    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_refresh_clusters_rolls_back_on_failure(monkeypatch):
    session = MagicMock()

    def raise_insert(sql, params=None):  # noqa: ANN001
        if sql == INSERT_SQL:
            raise RuntimeError("boom")
        return None

    session.execute.side_effect = raise_insert
    monkeypatch.setattr("app.workers.clusters.SessionLocal", lambda: session)

    with pytest.raises(RuntimeError):
        refresh_clusters()

    session.rollback.assert_called_once()
    session.close.assert_called_once()
