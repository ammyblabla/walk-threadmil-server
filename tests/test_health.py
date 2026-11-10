from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_returns_ok() -> None:
    res = client.get("/healthz")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_openapi_served_under_api_prefix() -> None:
    res = client.get("/api/v1/openapi.json")

    assert res.status_code == 200
    assert "/api/v1/home" in res.json()["paths"]
