"""M5 - Document Parsing Module Start
Starts the standalone Document Parsing API with health and parsing routes.
M5/M6 End"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.health import router as health_router
from app.routes.parsing import router as parsing_router


def create_app() -> FastAPI:
    """Create and configure the Document Parsing API."""
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Reusable document parsing API for Stats",
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
    application.include_router(parsing_router, prefix=settings.api_prefix)

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=settings.debug)
