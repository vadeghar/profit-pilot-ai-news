from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_market_brain_snapshot_is_empty() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/market-brain/snapshot")
    assert response.status_code == 200
    assert response.json()["nodes"] == []
