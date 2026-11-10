# syntax=docker/dockerfile:1

# ---- build: resolve deps into /app/.venv with uv ----
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY app ./app

# ---- runtime: slim image, non-root ----
FROM python:3.14-slim
RUN useradd --create-home --uid 10001 api
WORKDIR /app
COPY --from=build --chown=api:api /app /app
# Commit SHA baked in by CI (docker build --build-arg GIT_SHA=...), shown on /healthz.
ARG GIT_SHA=dev
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=8080 GIT_SHA=${GIT_SHA}
USER api
EXPOSE 8080
# Cloud Run injects $PORT; default 8080 for local runs.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
