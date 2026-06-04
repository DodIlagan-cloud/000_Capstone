"""M1 - User Access Management Start
Provides database connection and session management for Identity Access.
M1 End"""

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models.database import Base


def _azure_sqlalchemy_url():
    """Build a SQLAlchemy URL for Azure SQL without logging secret values."""
    connection_string = settings.azure_sql_connectionstring
    if connection_string.startswith("mssql+"):
        return connection_string
    if "Driver=" not in connection_string:
        connection_string = "Driver={ODBC Driver 18 for SQL Server};" + connection_string
    connection_string = (
        connection_string
        .replace("Initial Catalog=", "Database=")
        .replace("User ID=", "UID=")
        .replace("Password=", "PWD=")
        .replace("Encrypt=True", "Encrypt=yes")
        .replace("Encrypt=False", "Encrypt=no")
        .replace("TrustServerCertificate=True", "TrustServerCertificate=yes")
        .replace("TrustServerCertificate=False", "TrustServerCertificate=no")
    )
    return URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})


def _engine_target():
    if settings.database_provider.lower() == "azuresql":
        return _azure_sqlalchemy_url()
    return settings.database_url


def _connect_args():
    if settings.database_provider.lower() == "azuresql":
        return {}
    return {"check_same_thread": False} if "sqlite" in settings.database_url else {}


# Create database engine
engine = create_engine(
    _engine_target(),
    connect_args=_connect_args(),
    echo=settings.database_echo,
    pool_pre_ping=True,
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
