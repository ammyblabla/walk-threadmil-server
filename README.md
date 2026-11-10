# walk-treadmill-server

API for the treadmill workout planner. Python 3.14, FastAPI, deployed to Google Cloud Run.

- Design: [ADR-0001 tech stack](docs/adr/0001-tech-stack.md), [DB schema and REST API](docs/requirement/02-db-schema-and-api.md)
- Deploy setup: [docs/deploy/cloud-run.md](docs/deploy/cloud-run.md)

> **Status: MVP skeleton.** `GET /api/v1/home` returns **mock data**. There's no database, auth or planner yet.

## Run locally

```bash
uv sync                      # creates .venv/ with Python 3.14 + deps
uv run uvicorn app.main:app --reload --port 8080
```

You can also activate the venv and use plain commands:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8080
pytest
```

Then open:
- http://localhost:8080/health
- http://localhost:8080/api/v1/home
- http://localhost:8080/docs (Swagger UI) · OpenAPI JSON at `/api/v1/openapi.json`

## Test and lint

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## Docker

```bash
docker compose up --build    # http://localhost:8080
```

## Deploy

Every push to `main` runs tests. If they pass, it builds the image, pushes it to Artifact Registry and deploys it to Cloud Run (see `.github/workflows/ci.yml`). The one-time setup is in [docs/deploy/cloud-run.md](docs/deploy/cloud-run.md).

## Layout

```
app/
  main.py          create_app(), /health, mounts /api/v1
  config.py        settings from env vars
  api/v1/          routers (one file per resource)
  schemas/         Pydantic request/response models
tests/
infra/terraform/   Cloud Run, Artifact Registry, GitHub deploy auth, budget
```
