"""M1 - User Access Management Start
Starts the standalone Identity Access API with authentication and user management routes.
M1 End"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.users import router as users_router


def create_app() -> FastAPI:
    """Create and configure the Identity Access API."""
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Identity access API for Stats authentication and authorization",
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
    application.include_router(auth_router, prefix=settings.api_prefix)
    application.include_router(users_router, prefix=settings.api_prefix)

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=settings.debug)
