from fastapi.testclient import TestClient

from app.main import app


def test_source_reliability_endpoint() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/news/ingest")
        assert response.status_code == 200
        event_id = response.json()[0]["id"]

        reliability = client.get(f"/api/v1/news/{event_id}/source-reliability")
        assert reliability.status_code == 200
        body = reliability.json()
        assert 0 <= body["score"] <= 1
        assert body["tier"] in {"A", "B", "C", "D"}
