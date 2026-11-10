from fastapi.testclient import TestClient

from app.main import app
from app.schemas.home import HomeResponse

client = TestClient(app)


def test_home_returns_valid_payload() -> None:
    res = client.get("/api/v1/home")

    assert res.status_code == 200
    HomeResponse.model_validate(res.json())


def test_home_plan_steps_are_contiguous() -> None:
    plan = client.get("/api/v1/home").json()["suggestion"]["plan"]
    steps = plan["steps"]

    assert [s["seq"] for s in steps] == list(range(1, len(steps) + 1))
    for prev, nxt in zip(steps, steps[1:], strict=False):
        assert nxt["start_offset_s"] == prev["start_offset_s"] + prev["duration_s"]
    assert plan["total_duration_s"] == sum(s["duration_s"] for s in steps)
