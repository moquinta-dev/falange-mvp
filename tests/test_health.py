import asyncio

import httpx

from app.main import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_root_returns_app_metadata() -> None:
    response = get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "falange-mvp"


def test_health_returns_ok() -> None:
    response = get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
