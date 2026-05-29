"""M7 - Transaction Extraction Module Start
Starts the standalone Transaction Extraction API with health and extraction routes.
M7 End"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.extractions import router as extractions_router
from app.routes.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the Transaction Extraction API."""
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Reusable transaction candidate extraction API for Stats",
        debug=settings.debug,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(extractions_router, prefix=settings.api_prefix)

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=settings.debug)
