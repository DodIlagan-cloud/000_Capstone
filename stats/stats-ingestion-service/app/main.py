"""FastAPI application bootstrap for the Stats Ingestion Service."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.routes.health import router as health_router
from app.routes.ingest import router as ingest_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="PDF transaction ingestion and normalization service for Stats",
        debug=settings.debug,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(ingest_router, prefix=settings.api_prefix)

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
