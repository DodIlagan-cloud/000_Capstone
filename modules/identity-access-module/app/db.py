"""M1 - User Access Management Start
Provides database connection and session management for Identity Access.
M1 End"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models.database import Base

# Create database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.database_echo,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database, creating all tables."""
    # M1 - User Access Management Start
    # Imports user models so user tables are registered before metadata creation.
    import app.models.user  # noqa: F401
    # M1 End

    Base.metadata.create_all(bind=engine)
