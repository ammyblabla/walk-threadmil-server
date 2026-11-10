from fastapi import FastAPI

from app.api.v1 import home, profile
from app.config import get_settings

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Walk Treadmill API",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url="/docs",
    )

    # Not /healthz: Cloud Run's Google Front End reserves some paths ending in "z" and 404s them.
    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        settings = get_settings()
        return {"status": "ok", "env": settings.env, "version": settings.git_sha}

    app.include_router(home.router, prefix=API_PREFIX)
    app.include_router(profile.router, prefix=API_PREFIX)
    return app


app = create_app()
