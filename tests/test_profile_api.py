from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.auth
import app.db
from app.config import Settings
from app.db import get_session
from app.main import app as fastapi_app

URL = "/api/v1/me/profile"


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


def test_get_creates_profile_with_defaults(client: TestClient) -> None:
    res = client.get(URL)

    assert res.status_code == 200
    body = res.json()
    assert body["treadmill_max_speed_kmh"] == 12.0
    assert body["treadmill_speed_step"] == 0.1
    assert body["hr_zones"] is None  # no max_hr / birth_year yet


def test_put_then_get_round_trip_with_computed_zones(client: TestClient) -> None:
    payload = {"weight_kg": 58.5, "max_hr": 190, "resting_hr": 60, "treadmill_max_speed_kmh": 10}

    put = client.put(URL, json=payload)
    got = client.get(URL)

    assert put.status_code == 200
    body = got.json()
    assert body["weight_kg"] == 58.5
    assert body["treadmill_max_speed_kmh"] == 10.0
    assert body["effective_max_hr"] == 190
    assert body["hr_zones"][1] == {"zone": 2, "min_bpm": 138, "max_bpm": 151}  # Karvonen


def test_put_is_full_replace(client: TestClient) -> None:
    client.put(URL, json={"weight_kg": 60, "max_hr": 190})

    body = client.put(URL, json={"birth_year": 1996}).json()

    assert body["weight_kg"] is None
    assert body["max_hr"] is None
    assert body["effective_max_hr"] is not None  # estimated from birth_year


@pytest.mark.parametrize(
    "payload",
    [
        {"max_hr": 300},
        {"treadmill_min_speed_kmh": 8, "treadmill_max_speed_kmh": 6},
        {"max_hr": 150, "resting_hr": 160},
        {"unknown_field": 1},
    ],
)
def test_put_rejects_invalid(client: TestClient, payload: dict) -> None:
    assert client.put(URL, json=payload).status_code == 422


def test_prod_refuses_without_real_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app.auth, "get_settings", lambda: Settings(env="prod"))

    assert client.get(URL).status_code == 401


def test_returns_503_when_database_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app.db, "get_settings", lambda: Settings(database_url=None))

    assert TestClient(fastapi_app).get(URL).status_code == 503
