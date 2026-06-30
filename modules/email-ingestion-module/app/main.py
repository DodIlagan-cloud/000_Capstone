"""M12 - Email Ingestion Module Start
Starts the standalone Email Ingestion API with health and automated-run routes.
M12 End"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.health import router as health_router
from app.routes.ingestions import router as ingestions_router
from app.routes.sources import router as sources_router


def create_app() -> FastAPI:
    """Create and configure the Email Ingestion API."""
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Reusable automated email attachment ingestion API for Stats",
        debug=settings.debug,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(sources_router, prefix=settings.api_prefix)
    application.include_router(ingestions_router, prefix=settings.api_prefix)

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=settings.debug)
