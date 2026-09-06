from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_sqlite() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_market_brain_snapshot_is_empty() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/market-brain/snapshot")
    assert response.status_code == 200
    assert response.json()["nodes"] == []


def test_news_ingestion_persists_events() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/news/ingest")
        assert response.status_code == 200
        assert len(response.json()) == 2

        listed = client.get("/api/v1/news").json()
        ids = {item["id"] for item in listed}
        assert {"stub-reliance-001", "stub-tcs-001"}.issubset(ids)
