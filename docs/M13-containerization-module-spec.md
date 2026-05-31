<!-- M13 - Containerization Start -->
<!-- Specifies the single Stats runtime container that packages all module APIs, Tesseract OCR, and Stats Web. -->

# Module 13 Containerization Module Specification

## Module Summary

Module 13 establishes the **Containerization Module** for the Stats project. It packages the complete Stats runtime â€” Stats Web, all Python module APIs, Tesseract OCR, OCR language data, and PDF rendering dependencies â€” into a single portable container so the full system can run consistently across developer machines, CI environments, and production targets without manual dependency installation.

M13 is the prerequisite for enabling live Tesseract OCR in M5. Until M13 is in place, OCR is intentionally disabled locally (`ALLOW_OCR_FALLBACK=false`) and document parsing falls back to direct PDF text extraction only. After M13, image files and scanned PDFs can be parsed end-to-end through the containerized runtime.

M13 does not own module business logic, API routes, database schema, cloud deployment infrastructure, or Stats Web page presentation. Those concerns belong to their owning modules and apps.

## Architecture Alignment

M13 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M5-document-parsing-module-spec.md`

The building-block plan defines this module as:

| Field | M13 Direction |
| --- | --- |
| Build order | `13` |
| Module | Containerization |
| Type | Infrastructure |
| Main responsibility | Local containers, Compose, service health checks, dependencies |
| Reusable output | Dockerfiles and Compose profiles |

M13 starts early relative to its roadmap position because M5 OCR requires Tesseract to be available in a portable runtime. M13 is not moved forward as a full cloud deployment module â€” it is scoped here to the single Stats runtime container that enables OCR and consistent local execution.

## Goals

- Package Stats Web, all current Python module APIs, Tesseract, OCR language data, and Python OCR dependencies into a single runnable Stats container.
- Enable Tesseract OCR for M5 document parsing inside the container runtime.
- Start module APIs in dependency order and confirm their health before Stats Web starts.
- Expose Stats Web on a configurable container port so the browser-facing app is the single entry point.
- Keep all runtime values â€” ports, hosts, OCR paths, directory roots, database URLs, API base URLs, token settings â€” configurable through environment variables and config files rather than hardcoded in the container image.
- Apply the central logging contract so all packaged services write redacted logs to stdout/stderr for Docker, CI, and later cloud collection.
- Provide a local Compose file so the full Stats runtime can be started and stopped with one command.
- Provide health check definitions for every packaged service.
- Enable M5 OCR end-to-end testing against the configured project fixture path, currently the logical `tests/input/` path resolved from `STATS_APP_ROOT`, inside the container.

## Non-Goals

- Cloud deployment to Azure, AWS, or any other provider. That belongs to M14 Cloud Readiness.
- Database provisioning, migrations, or schema management inside the container. Stats Data and Persistence (M9) owns that.
- Email ingestion runtime packaging. Email Ingestion Module (M12) owns that.
- Kubernetes or orchestration platform configuration.
- CI/CD pipeline definition.
- Multi-region or high-availability deployment configuration.
- Evaluation report generation. That belongs to M15 Evaluation Evidence.
- Changing module API behavior, routes, or business logic. Each module owns its own code.

## Owner Folder

```text
infrastructure/containers/stats/
infrastructure/compose/
```

Module-local container assets belong under `infrastructure/containers/stats/`. The Compose file for local full-stack testing belongs under `infrastructure/compose/`.

Integration contract tests for M13 belong under:

```text
tests/integration/test_m13_containerization_contract.py
```

## What Gets Packaged

The single Stats runtime container must include:

| Component | Source | Purpose |
| --- | --- | --- |
| Stats Web | `apps/stats-web/` | .NET encompassing front end and orchestration shell |
| Identity Access API | `modules/identity-access-module/` | Login, tokens, role checks â€” port 8013 |
| File Validation API | `modules/file-validation-module/` | File validation and ingestion â€” port 8014 |
| Document Parsing API | `modules/document-parsing-module/` | OCR/text extraction and classification â€” port 8015 |
| Transaction Extraction API | `modules/transaction-extraction-module/` | Transaction candidate extraction â€” port 8016 |
| Data Validation API | `modules/data-validation-module/` | Transaction normalization and validation checks â€” port 8017 |
| Tesseract OCR | System package | OCR engine required by M5 |
| OCR language data | `tesseract-ocr-eng` or equivalent | English language tessdata required by M5 |
| PyMuPDF | Python package | PDF rendering for scanned PDF OCR in M5 |
| Python runtime | `python:3.13-slim` or equivalent | Runtime for all module APIs |
| .NET runtime | `mcr.microsoft.com/dotnet/aspnet` | Runtime for Stats Web |

## Service Port Map

| Service | Internal Port | Notes |
| --- | --- | --- |
| Stats Web | 8080 (container) â†’ configurable host port | Browser entry point |
| Identity Access API | 8013 | Internal only; not exposed directly to host |
| File Validation API | 8014 | Internal only; not exposed directly to host |
| Document Parsing API | 8015 | Internal only; not exposed directly to host |
| Transaction Extraction API | 8016 | Internal only; not exposed directly to host |
| Data Validation API | 8017 | Internal only; not exposed directly to host |

## Container Structure

```text
infrastructure/
  containers/
    stats/
      Dockerfile                        # Single Stats runtime image
      start-stats-runtime.sh            # Startup orchestration script
  compose/
    stats-runtime.compose.yml           # Local full-stack Compose profile
```

### Dockerfile Requirements

The Dockerfile must:

- Use a multi-stage build: one stage for building the .NET Stats Web app, one stage for the final runtime image.
- Install Tesseract and the English OCR language data package from the base OS package manager.
- Install all Python module dependencies from each module's `requirements.txt`.
- Copy all module source code under their respective paths inside the image.
- Copy the built Stats Web output from the build stage.
- Set `TESSDATA_PREFIX` to the correct tessdata directory inside the image.
- Set `TESSERACT_CMD` to the Tesseract executable path inside the image.
- Copy `start-stats-runtime.sh` and set it as the container entrypoint.
- Expose the Stats Web port.
- Not hardcode environment-dependent values such as database URLs, token secrets, or Stats Web base URLs.
- Use `STATS_APP_ROOT` and logical directory variables for runtime paths that may change between local, container, and cloud environments. Stable Docker build-context source paths may remain in `COPY` instructions, but application startup and evidence execution must not depend on a developer machine root.

### Dockerfile Requirements

The Dockerfile must also run build-time verification steps after installing Python dependencies to fail fast if any OCR or PDF library is missing:

```dockerfile
RUN tesseract --version \
    && python3 -c "import fitz; print('PyMuPDF OK:', fitz.__version__)" \
    && python3 -c "import pytesseract; print('pytesseract OK:', pytesseract.__version__)" \
    && python3 -c "from PIL import Image; print('Pillow OK:', Image.__version__)"
```

### Startup Script Requirements

`start-stats-runtime.sh` must:

1. Wait for `stats-db` (PostgreSQL) to be reachable on its configured host and port.
2. Run Identity database init (`init_db()`) to create the users table if it does not exist.
3. Start the Identity Access API (`uvicorn`) on port 8013 in the background.
4. Start the File Validation API (`uvicorn`) on port 8014 in the background.
5. Start the Document Parsing API (`uvicorn`) on port 8015 in the background.
6. Start the Transaction Extraction API (`uvicorn`) on port 8016 in the background.
7. Start the Data Validation API (`uvicorn`) on port 8017 in the background.
8. Wait for each API to pass its `/health` endpoint before continuing.
9. Start Stats Web (`dotnet`) in the foreground as the final process.
10. Log each startup step clearly so container startup issues are visible in container logs.

The health wait must use a configurable timeout and fail clearly if a dependency does not become ready within the timeout window.

### Compose File Requirements

`stats-runtime.compose.yml` must:

- Define a `stats-db` PostgreSQL service with a `stats-db-data` persistent volume.
- Define the `stats` service using the built Stats runtime image with `depends_on: stats-db: condition: service_healthy`.
- Wire `DATABASE_URL` inside the `stats` service to point to the `stats-db` Compose service â€” not to `host.docker.internal`.
- Map the Stats Web container port to a configurable host port.
- Pass runtime environment variables through to the container using an `.env.container` file.
- Mount no source code volumes â€” the container must be self-contained for production-like validation.
- Include a `healthcheck` definition against the Stats Web `/health` endpoint.

**Architectural note:** M13 owns the runtime wiring of `stats-db` inside the Compose stack. M9 (Stats Data and Persistence) owns the full Stats schema, migrations, and persistence adapters. The `stats-db` service here satisfies the M1 identity persistence requirement; M9 will expand the schema when implemented.

## Runtime Configuration

All runtime values must be supplied through environment variables or config files following the M0 project-wide configuration standard. No environment-dependent value may be hardcoded in the Dockerfile or startup script.

Expected container environment variables:

| Variable | Purpose |
| --- | --- |
| `STATS_APP_ROOT` | Physical root of the Stats runtime in the current environment, default `/app` in the container |
| `STATS_RUNTIME_CONFIG` | Path to the central runtime configuration registry, default `/app/config/stats.runtime.json` in the container |
| `STATS_PATHS_CONFIG` | Path to the central logical path map, default `/app/config/stats.paths.json` in the container |
| `STATS_LOGGING_CONFIG` | Path to the central logging registry, default `/app/config/stats.logging.json` in the container |
| `STATS_STORAGE_PROVIDER` | Storage provider selector, default `LocalFileSystem`; future cloud value may be `AzureBlobStorage` |
| `IDENTITY_MODULE_DIR` | Resolved Identity Access module directory inside the runtime |
| `FILE_VALIDATION_MODULE_DIR` | Resolved File Validation module directory inside the runtime |
| `DOCUMENT_PARSING_MODULE_DIR` | Resolved Document Parsing module directory inside the runtime |
| `TRANSACTION_EXTRACTION_MODULE_DIR` | Resolved Transaction Extraction module directory inside the runtime |
| `DATA_VALIDATION_MODULE_DIR` | Resolved Data Validation module directory inside the runtime |
| `STATS_WEB_DIR` | Resolved published Stats Web directory inside the runtime |
| `DATABASE_URL` | Stats PostgreSQL connection string for M1 identity persistence |
| `ACCESS_TOKEN_SECRET_KEY` | JWT signing secret for M1 |
| `DEFAULT_ADMIN_EMAIL` | Optional seed administrator email |
| `DEFAULT_ADMIN_PASSWORD` | Optional seed administrator password |
| `ALLOW_OCR_FALLBACK` | Set to `true` inside the container to enable Tesseract OCR in M5 |
| `OCR_ENGINE` | Set to `tesseract` inside the container |
| `TESSERACT_CMD` | Path to Tesseract executable inside the image (set by Dockerfile) |
| `TESSDATA_PREFIX` | Path to tessdata directory inside the image (set by Dockerfile) |
| `OCR_LANGUAGES` | OCR language hint, default `eng` |
| `CORS_ALLOWED_ORIGINS` | Browser origins allowed to call module APIs |
| `STATS_WEB_PORT` | Stats Web container bind port, default `8080` |
| `STATS_WEB_HOST_PORT` | Optional Docker host port mapped to Stats Web, default `8080` |
| `StatsApi__BaseUrl` | Stats Web override for Identity Access API base URL |
| `StatsWeb__Downstream__FileValidationBaseUrl` | Stats Web override for File Validation API base URL |
| `StatsWeb__Downstream__FileIngestionBaseUrl` | Stats Web override for File Ingestion API base URL |
| `StatsWeb__Downstream__DocumentParsingBaseUrl` | Stats Web override for Document Parsing API base URL |
| `StatsWeb__Downstream__TransactionExtractionBaseUrl` | Stats Web override for Transaction Extraction API base URL |
| `StatsWeb__Downstream__DataValidationBaseUrl` | Stats Web override for Data Validation API base URL |

Inside the container, module API base URLs should point to `localhost` with their respective ports since all services share the same network namespace.

For browser-facing upload flows, downstream module URLs must remain same-origin by default. Stats Web owns browser API routing through `/api/v1/{path}` and server-side proxy targets. Container startup must blank browser downstream URLs and set server-side proxy targets for internal modules.

A committed `.env.container.example` should document the expected container environment variable names without real secrets.

## Logging Configuration

M13 packages services so their logs can be collected consistently. All packaged services must follow `config/stats.logging.json`.

Expected logging environment variables:

| Variable | Purpose |
| --- | --- |
| `LOG_LEVEL` | Minimum application log level, default `INFO` |
| `LOG_FORMAT` | Log output format, default `json` |
| `LOG_INCLUDE_CORRELATION_ID` | Include request or correlation identifiers when available |
| `LOG_REDACT_SENSITIVE_VALUES` | Redact known sensitive values before logging |
| `LOG_DESTINATION` | Runtime destination, currently `stdout` |

The container must not require file-based log scraping. Docker, CI, and later Azure logging should collect application logs from stdout/stderr.

## OCR Configuration in Container

The container enables OCR by setting:

```env
ALLOW_OCR_FALLBACK=true
OCR_ENGINE=tesseract
TESSERACT_CMD=/usr/bin/tesseract
TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
```

These values must match the actual installed paths in the base OS image. The Dockerfile must verify the Tesseract install path at build time or document the expected path clearly.

## Health Check Strategy

Each service exposes a `/health` endpoint. The startup script polls each endpoint before proceeding to the next service. The Compose definition includes a container-level health check against the Stats Web entry point.

| Service | Health Endpoint | Expected Response |
| --- | --- | --- |
| stats-db | `pg_isready` via Compose health check | PostgreSQL accepting connections |
| Identity Access API | `http://localhost:8013/health` | `{"status": "healthy"}` |
| File Validation API | `http://localhost:8014/health` | `{"status": "healthy"}` |
| Document Parsing API | `http://localhost:8015/health` | `{"status": "healthy", "ocr": {"enabled": true}}` |
| Transaction Extraction API | `http://localhost:8016/health` | `{"status": "healthy"}` |
| Data Validation API | `http://localhost:8017/health` | `{"status": "healthy"}` |
| Stats Web | `http://localhost:{STATS_WEB_PORT}/health` | `{"status": "healthy", "service": "Stats Web"}` |

Stats Web exposes `/health` via a `MapGet` minimal endpoint added in `Program.cs` specifically for M13 container and Compose health check support.

The Document Parsing API health check is the most critical â€” it must confirm `ocr.enabled: true` inside the container, proving Tesseract is configured and available.

## M5 OCR Validation Inside Container

After M13 is running, M5 OCR must be validated with the configured project fixture path. The current logical path is `tests/input/`, resolved from `STATS_APP_ROOT` on the host or copied into the configured container fixture directory for evidence execution:

- Copy every supported file from `tests/input/` into the running `stats-runtime` container for the evidence run.
- Confirm JPEG, PNG, and scanned/no-text PDF files use the OCR path.
- Confirm image parse results use `strategy: tesseract_ocr`.
- Confirm forced-PDF-OCR results use `method: ocr`.
- Confirm the parse status is `completed` or `completed_with_warnings`.
- Confirm extracted text is non-empty.

This validates the container OCR path: local project fixture â†’ `stats-runtime` â†’ Document Parsing â†’ PyMuPDF/Tesseract â†’ classification result.

Real local test fixtures for this validation use the central path convention:

```text
STATS_APP_ROOT + tests/input
```

Every supported file in the configured `tests/input/` logical path must be used by the M13 evidence runner. Supported fixture extensions are `.jpg`, `.jpeg`, `.png`, and `.pdf`. Source documents in this folder are local-only and ignored by Git.

## Testing Boundary

M13 establishes the container-first testing boundary that applies to all modules and future module work:

| Tier | What runs | Where | Tool |
| --- | --- | --- | --- |
| Unit / contract | Module-level checks, file/content assertions, static contracts | Stats runtime container | `tests\scripts\regression\run_module_unit_tests.ps1` |
| Acceptance / evidence | Full runtime validation with Tesseract OCR, real fixture files, live DB | Docker stack | `tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1` |

Host-side checks are development diagnostics only after M13. Any result used for module completion, regression, capstone assessment artefacts, or runtime acceptance must be produced inside the containerized Stats runtime.

## Testing

### Integration Contract Tests

Container-executed contract checks must verify:

- The Dockerfile exists at the expected path.
- The startup script exists and is executable.
- The Compose file exists at the expected path.
- The Dockerfile references Tesseract installation.
- The Dockerfile references tessdata language data installation.
- The startup script starts each module API before Stats Web.
- The startup script performs health checks before proceeding.
- The `.env.container.example` documents the required OCR environment variables.
- The container image copies test code/scripts, while evidence runners copy gitignored `tests/input` fixtures into the running container before execution.
- Future modules are added to the single Stats runtime container before their official tests are accepted.

### Container Runtime Tests

After building and starting the container:

- All module API `/health` endpoints return healthy.
- Document Parsing `/health` reports `ocr.enabled: true`.
- Stats Web is reachable on the configured host port.
- A text-layer PDF uploaded through Stats Web parses with `strategy: pdf_text`.
- Every image file (JPEG or PNG) in `tests/input/` parses with `strategy: tesseract_ocr`.
- Every PDF in `tests/input/` is forced through OCR for the evidence run and returns non-empty text.

### Evidence

M13 evidence must include:

- Raw container build output confirming Tesseract was installed.
- Raw container startup log showing each service health check passed.
- M5 parse response for every supported file in `tests/input/`.
- JPEG/PNG responses showing `strategy: tesseract_ocr` and non-empty text.
- PDF forced-OCR responses showing `method: ocr` and non-empty text.
- Stats Web browser screenshot showing a successfully parsed image or scanned document result.
- Container health check output.

## Deferred Items

- Cloud deployment, Azure Container Registry push, Azure Container Apps or AKS configuration belongs to M14 Cloud Readiness.
- Multi-container orchestration with separate database and module containers belongs to M14 if required.
- Email Ingestion Module (M12) runtime packaging belongs to M12/M14.
- CI/CD pipeline integration belongs to M14 or a separate infrastructure track.
- Stats Data and Persistence (M9) database container configuration belongs to M9/M14.

## Acceptance Criteria

M13 is complete when:

- `infrastructure/containers/stats/Dockerfile` builds a working Stats runtime image.
- `infrastructure/containers/stats/start-stats-runtime.sh` starts all module APIs, waits for health, then starts Stats Web.
- `infrastructure/compose/stats-runtime.compose.yml` starts the full Stats runtime with one command.
- All module API health endpoints return healthy inside the running container.
- Document Parsing `/health` reports `ocr.enabled: true` inside the container.
- M5 successfully parses a JPEG or PNG image using `strategy: tesseract_ocr` inside the container.
- M5 successfully parses a scanned PDF using `strategy: tesseract_ocr` inside the container.
- All runtime values are configurable through environment variables without modifying the image.
- The `.env.container.example` documents required environment variables without containing real secrets.
- Integration contract tests pass.
- Evidence confirms Tesseract is installed and OCR works end-to-end in the container runtime.

<!-- M13 End -->
