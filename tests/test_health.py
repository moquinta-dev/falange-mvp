from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_returns_app_metadata() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "falange-mvp"


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
