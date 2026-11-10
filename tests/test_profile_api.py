from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.auth
import app.db
import app.firebase_auth
from app.config import Settings
from app.db import get_session
from app.main import app as fastapi_app
from tests.test_firebase_auth import StaticKeys, make_token

URL = "/api/v1/me/profile"


@pytest.fixture
def db_client(db_session: Session) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(db_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Dev auth: every request is the local owner."""
    monkeypatch.setattr(app.auth, "get_settings", lambda: Settings(auth_mode="dev"))
    return db_client


@pytest.fixture
def firebase_client(db_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Firebase auth with test-signed tokens instead of Google's JWKS."""
    monkeypatch.setattr(app.auth, "get_settings", lambda: Settings(auth_mode="firebase"))
    monkeypatch.setattr(app.firebase_auth, "google_jwks", lambda: StaticKeys())
    return db_client


def _bearer(uid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=uid)}"}


# ── profile behaviour (dev auth) ──


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


# ── Firebase auth ──


def test_firebase_requires_token(firebase_client: TestClient) -> None:
    res = firebase_client.get(URL)

    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


def test_firebase_rejects_bad_token(firebase_client: TestClient) -> None:
    res = firebase_client.get(URL, headers={"Authorization": "Bearer nope"})

    assert res.status_code == 401


def test_firebase_users_are_isolated(firebase_client: TestClient) -> None:
    alice, bob = _bearer("uid-alice"), _bearer("uid-bob")

    firebase_client.put(URL, json={"weight_kg": 55}, headers=alice)
    firebase_client.put(URL, json={"weight_kg": 80}, headers=bob)

    assert firebase_client.get(URL, headers=alice).json()["weight_kg"] == 55.0
    assert firebase_client.get(URL, headers=bob).json()["weight_kg"] == 80.0


# ── config guards ──


def test_dev_auth_refused_in_prod() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE=dev"):
        Settings(env="prod", auth_mode="dev")


def test_returns_503_when_database_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app.db, "get_settings", lambda: Settings(database_url=None))

    assert TestClient(fastapi_app).get(URL).status_code == 503
