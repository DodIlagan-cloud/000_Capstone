# Foundation Module Specification

## Module Summary

The Foundation module establishes the shared backend base for the Stats capstone project. It provides the application bootstrap, configuration, database session management, common schemas, error response conventions, middleware, logging, and test scaffolding that later modules will build on.

This module does not implement full PDF ingestion, transaction extraction, OCR, reporting, authentication, or frontend workflows. It creates the stable service foundation those modules will depend on.

## Goals

- Provide a predictable FastAPI application entry point.
- Centralize application settings and environment variable behavior.
- Establish database engine, session, and initialization patterns.
- Define common response and error contracts.
- Configure baseline middleware and logging.
- Provide a clean structure for adding future routes, services, models, and tests.
- Confirm the service can start and expose basic health/status endpoints.

## Non-Goals

- Extracting transactions from PDFs.
- Persisting uploaded PDFs or parsed transactions beyond foundational database setup.
- Implementing OCR behavior.
- Building a frontend upload/review interface.
- Adding authentication or user management.
- Creating production deployment infrastructure beyond local runtime readiness.

## Current Target Service

The Foundation module applies to:

```text
stats/stats-ingestion-service
```

The service is a FastAPI backend for ingesting PDF documents, extracting financial transaction data, and exposing normalized results through API endpoints.

## Required Project Structure

The service should use this baseline structure:

```text
stats/stats-ingestion-service/
  app/
    __init__.py
    main.py
    config.py
    db.py
    errors.py
    logging_config.py
    models/
      __init__.py
      common.py
      database.py
      requests.py
      transaction.py
    routes/
      __init__.py
      health.py
    services/
      __init__.py
    utils/
      __init__.py
  tests/
    __init__.py
    conftest.py
    test_foundation.py
  requirements.txt
  .env.example
```

Existing files may be reused where they already satisfy the contract. Files should only be split or renamed when doing so improves clarity without creating unnecessary churn.

## Application Bootstrap

The application must expose a configured FastAPI app.

### Requirements

- Create the app in `app/main.py`.
- Set app metadata from settings:
  - `app_name`
  - `app_version`
  - description
  - debug mode
- Register middleware during startup.
- Register foundation routes.
- Provide a consistent pattern for adding future routers.
- Avoid duplicated app declarations in the same file.

### Required Endpoints

#### `GET /health`

Returns operational health metadata.

Expected response shape:

```json
{
  "status": "healthy",
  "service": "Stats Ingestion Service",
  "version": "1.0.0"
}
```

#### `GET /`

Returns basic service metadata.

Expected response shape:

```json
{
  "service": "Stats Ingestion Service",
  "version": "1.0.0",
  "message": "Stats Ingestion Service is running"
}
```

## Configuration

Configuration must be centralized in `app/config.py`.

### Required Settings

| Setting | Default | Description |
| --- | --- | --- |
| `app_name` | `Stats Ingestion Service` | Service display name |
| `app_version` | `1.0.0` | Service version |
| `debug` | `false` | Debug/runtime reload flag |
| `api_prefix` | `/api/v1` | Prefix for versioned API routes |
| `max_file_size_mb` | `50` | Maximum PDF upload size |
| `allowed_extensions` | `["pdf"]` | Allowed upload file extensions |
| `upload_directory` | `uploads` | Local upload directory |
| `enable_ocr` | `true` | Enables OCR behavior for future PDF processing |
| `ocr_timeout_seconds` | `300` | OCR timeout for future processing |
| `database_url` | `sqlite:///./stats_ingestion.db` | SQLAlchemy connection URL |
| `database_echo` | `false` | SQLAlchemy query logging |
| `log_level` | `INFO` | Application logging level |

### Environment Behavior

- Settings must support environment variable overrides.
- Boolean values should accept string values such as `true` and `false`.
- Integer values should be parsed safely.
- The configured upload directory should be created when settings initialize.
- Defaults should allow local development without requiring a `.env` file.

## Database Foundation

Database setup must live in `app/db.py` and shared database models must use a single declarative base.

### Requirements

- Create a SQLAlchemy engine from `settings.database_url`.
- Support SQLite local development with appropriate `check_same_thread` handling.
- Create a `SessionLocal` session factory.
- Provide a `get_db()` dependency that yields and closes sessions.
- Provide an `init_db()` function that creates tables from metadata.
- Keep the declarative `Base` importable by database model modules.

### Out of Scope

- Alembic migration generation.
- Production database provisioning.
- Repository-specific persistence methods for PDF and transaction records.

## Shared Schemas

The module must define reusable Pydantic schemas for common service responses.

### Required Schemas

#### Error Response

```json
{
  "type": "ERROR_TYPE",
  "message": "Human-readable error message"
}
```

#### Health Response

```json
{
  "status": "healthy",
  "service": "Stats Ingestion Service",
  "version": "1.0.0"
}
```

#### Root Response

```json
{
  "service": "Stats Ingestion Service",
  "version": "1.0.0",
  "message": "Stats Ingestion Service is running"
}
```

Schemas should be compatible with the installed Pydantic version and configured for ORM compatibility where needed.

## Error Handling Contract

The Foundation module must define a consistent error convention for later modules.

### Required Error Types

- `INVALID_REQUEST`
- `INVALID_FILE_TYPE`
- `FILE_TOO_LARGE`
- `PROCESSING_ERROR`
- `DATABASE_ERROR`
- `NOT_FOUND`
- `INTERNAL_ERROR`

### Requirements

- Error responses must include `type` and `message`.
- API handlers should avoid leaking internal stack traces to clients.
- Internal details should be logged for debugging.
- Later modules should be able to reuse these error types rather than inventing separate shapes.

## Logging

Logging configuration should be centralized.

### Requirements

- Configure logging level from `settings.log_level`.
- Provide a reusable logger setup function.
- Use a format that includes timestamp, level, logger name, and message.
- Avoid noisy debug logging unless debug mode or log level enables it.

## Middleware

The Foundation module must configure baseline middleware.

### Required Middleware

- CORS middleware.

### CORS Defaults

Initial local-development defaults may allow all origins, methods, and headers. The structure should allow stricter production settings later.

## Testing

The Foundation module must include tests proving that the base service works.

### Required Tests

- App imports successfully.
- `GET /health` returns HTTP 200.
- `GET /health` response includes:
  - `status`
  - `service`
  - `version`
- `GET /` returns HTTP 200.
- `GET /` response includes:
  - `service`
  - `version`
  - `message`
- Settings expose expected default values.
- Database initialization function is callable.

### Test Tooling

- Use `pytest`.
- Use FastAPI `TestClient` for endpoint tests.
- Keep test setup reusable through `tests/conftest.py` if shared fixtures are needed.

## Runtime Requirements

The service must be runnable locally with:

```powershell
uvicorn app.main:app --reload
```

from:

```text
stats/stats-ingestion-service
```

The module should also support direct execution through `python -m app.main` if retained by the implementation.

## Dependencies

The Foundation module requires these baseline dependencies:

- `fastapi`
- `uvicorn`
- `pydantic`
- `python-dotenv`
- `pytest`
- `httpx`
- `sqlalchemy`

Existing PDF-specific dependencies may remain in `requirements.txt`, but the Foundation module itself should not depend on PDF parsing packages.

## Acceptance Criteria

The Foundation module is complete when:

- The service has one clear FastAPI app declaration.
- `/health` and `/` respond successfully.
- Configuration loads defaults and supports environment overrides.
- The upload directory is created automatically.
- Database engine/session/init patterns are available.
- Shared response and error schemas are defined.
- Logging configuration is centralized.
- CORS middleware is configured.
- Foundation tests pass.
- Future modules can add routes, services, schemas, and database models without changing the foundation structure.

## Implementation Notes

- Existing service files should be reused where practical.
- Duplicated code in `app/main.py` should be cleaned up during implementation.
- Existing ingestion-specific code should not be expanded as part of the Foundation module.
- Any behavior outside this spec should be deferred to the relevant future module.
