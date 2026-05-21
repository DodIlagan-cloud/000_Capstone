# M0 Foundation Module File Inventory

<!-- M0 Foundation: file-level inventory of created and modified artefacts. -->

## Summary

This document lists the files created or modified for **M0 - Foundation Module** and describes the purpose of each change.

The M0 Foundation Module establishes the shared backend base for the Stats capstone project, including application bootstrap, configuration, database setup, shared response schemas, error handling, logging, health endpoints, tests, and test evidence artefacts.

## Specification and Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M0-foundation-module-spec.md` | Created | Defines the Foundation module specification, including scope, goals, required structure, configuration, database foundation, shared schemas, logging, middleware, tests, and acceptance criteria. |
| `docs/M0-foundation-file-inventory.md` | Created | Documents the files created or modified for M0 and explains the purpose of each change. |

## Repository Setup

| File | Change Type | Description |
| --- | --- | --- |
| `.gitignore` | Created | Excludes Python cache files, test cache folders, local runtime files, virtual environments, local tool folders, and OS-specific files from Git tracking. |

## Foundation Application Files

| File | Change Type | Description |
| --- | --- | --- |
| `stats/stats-ingestion-service/.env.example` | Created | Provides example environment variables for local configuration, including app metadata, API prefix, upload settings, OCR settings, database URL, and logging level. |
| `stats/stats-ingestion-service/app/main.py` | Modified | Replaced duplicated FastAPI app declarations with a single clean `create_app()` bootstrap, middleware registration, health route registration, ingest route registration, and direct runtime entry point. |
| `stats/stats-ingestion-service/app/config.py` | Modified | Added safer environment parsing for booleans, integers, allowed extensions, app name, app version, database echo, upload directory, and default settings. |
| `stats/stats-ingestion-service/app/db.py` | Existing Foundation File | Provides SQLAlchemy engine creation, session factory, `get_db()` dependency, and `init_db()` table initialization function. |
| `stats/stats-ingestion-service/app/logging_config.py` | Created | Adds centralized logging configuration using the configured log level and a reusable log format. |
| `stats/stats-ingestion-service/app/errors.py` | Created | Defines reusable API error types and a helper for producing consistent FastAPI error responses. |
| `stats/stats-ingestion-service/app/__init__.py` | Existing Package File | Marks the `app` directory as a Python package. |

## Routes

| File | Change Type | Description |
| --- | --- | --- |
| `stats/stats-ingestion-service/app/routes/health.py` | Created | Adds Foundation routes for `GET /health` and `GET /`, returning structured service health and metadata responses. |
| `stats/stats-ingestion-service/app/routes/ingest.py` | Modified | Cleaned duplicate route definitions and aligned placeholder ingest behavior with the shared error response pattern and current response schema. |
| `stats/stats-ingestion-service/app/routes/__init__.py` | Modified | Cleaned duplicate package docstrings and retained a single package description. |

## Models and Schemas

| File | Change Type | Description |
| --- | --- | --- |
| `stats/stats-ingestion-service/app/models/common.py` | Created | Adds shared Pydantic schemas for `ErrorResponse`, `HealthResponse`, and `RootResponse`. |
| `stats/stats-ingestion-service/app/models/requests.py` | Modified | Reused the shared `ErrorResponse`, aligned transaction date typing, and updated ORM compatibility configuration for Pydantic v2. |
| `stats/stats-ingestion-service/app/models/transaction.py` | Modified | Updated date typing and schema configuration for Pydantic v2 compatibility. |
| `stats/stats-ingestion-service/app/models/database.py` | Modified | Updated SQLAlchemy declarative base import to the SQLAlchemy 2 compatible import path. |
| `stats/stats-ingestion-service/app/models/__init__.py` | Modified | Cleaned duplicate package docstrings and retained a single package description. |

## Existing Supporting Structure

| File | Change Type | Description |
| --- | --- | --- |
| `stats/stats-ingestion-service/app/services/__init__.py` | Existing Package File | Marks the `services` directory as a Python package for future service modules. |
| `stats/stats-ingestion-service/app/services/pdf_processor.py` | Existing Supporting File | Existing PDF processing service retained for later PDF processing modules. Not expanded as part of M0. |
| `stats/stats-ingestion-service/app/utils/__init__.py` | Existing Package File | Marks the `utils` directory as a Python package for future shared utilities. |
| `stats/stats-ingestion-service/requirements.txt` | Existing Dependency File | Retains FastAPI, testing, database, and PDF-related dependencies required by the current service. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `stats/stats-ingestion-service/tests/conftest.py` | Created | Adds a shared FastAPI `TestClient` fixture for endpoint tests. |
| `stats/stats-ingestion-service/tests/test_foundation.py` | Created | Adds Foundation tests for app import, health endpoint, root endpoint, settings defaults, and database initializer availability. |
| `stats/stats-ingestion-service/tests/test_main.py` | Existing Test File | Existing main endpoint tests retained and still passing. |
| `stats/stats-ingestion-service/tests/test_ingest.py` | Existing Test File | Existing ingest validation tests retained and still passing. |
| `stats/stats-ingestion-service/tests/__init__.py` | Existing Package File | Marks the `tests` directory as a Python package. |

## Test Results and Evidence

| File | Change Type | Description |
| --- | --- | --- |
| `stats/stats-ingestion-service/test-results/foundation-test-results-2026-05-21.md` | Created | Documents the Foundation module direct verification test results. |
| `stats/stats-ingestion-service/test-results/foundation-test-raw-output-2026-05-21.txt` | Created | Stores raw terminal-style output from the Foundation verification command. |
| `stats/stats-ingestion-service/test-results/foundation-manual-test-checklist.md` | Created | Provides a manual checklist for verifying the Foundation module without pytest. |
| `stats/stats-ingestion-service/test-results/foundation-screenshot-evidence-2026-05-21.md` | Created | Indexes the retained screenshot evidence and explains what each screenshot proves. |
| `stats/stats-ingestion-service/test-results/foundation-windows-browser-health-2026-05-21.png` | Created | Actual cropped Windows browser screenshot showing the `/health` endpoint response. |
| `stats/stats-ingestion-service/test-results/foundation-windows-browser-root-2026-05-21.png` | Created | Actual cropped Windows browser screenshot showing the `/` root endpoint response. |
| `stats/stats-ingestion-service/test-results/foundation-windows-browser-docs-2026-05-21.png` | Created | Actual cropped Windows browser screenshot showing the FastAPI `/docs` page. |
| `stats/stats-ingestion-service/test-results/foundation-windows-terminal-test-2026-05-21.png` | Created | Actual cropped Windows terminal screenshot showing Foundation checks passing. |
| `stats/stats-ingestion-service/test-results/foundation_terminal_check.py` | Created | Helper script used to generate repeatable terminal evidence for the Foundation module. |

## Reusable Evidence Skill

| File | Change Type | Description |
| --- | --- | --- |
| `skills/module-test-evidence/SKILL.md` | Created | Defines the reusable module test evidence workflow for future modules, including actual Windows screenshots, cropping, raw logs, checklists, and evidence indexes. |
| `skills/module-test-evidence/agents/openai.yaml` | Created | Provides UI metadata for the reusable module test evidence skill. |
| `skills/module-test-evidence/scripts/crop_screenshots.py` | Created | Adds a helper script for repeatable in-place screenshot cropping. |

## Verification

The M0 Foundation module was verified with:

```text
pytest
```

Result:

```text
9 passed
```

Additional non-pytest verification evidence is stored under:

```text
stats/stats-ingestion-service/test-results/
```

## Notes

- Earlier rendered-response screenshots were removed.
- Only actual Windows browser and terminal screenshots are retained as screenshot evidence.
- Screenshots were cropped to show only the relevant browser or terminal content.
- The Foundation module is now committed and available in the GitHub repository.
