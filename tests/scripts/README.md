# Stats Test Helpers

This directory contains reusable evidence, regression, and helper scripts for the Stats capstone project.

## Testing Boundary (established in M13)

From M13 onward the Stats app is **container-first**. This boundary applies to all modules:

| Tier | Purpose | Where to run | Tool |
| --- | --- | --- | --- |
| Unit / static tests | Fast developer feedback, module-level assertions, contract checks | Host machine | `pytest` under root `tests/unit/<module>/` or `tests/integration/` |
| Acceptance, OCR, DB, cross-module regression | Production-like evidence against the full runtime | Docker stack | Scripts in this directory |

**Local unit tests are developer feedback. Docker evidence is the source of truth.**

Host commands are allowed only for: editing files, static contract tests, fast unit tests, linting, and inspecting code. Integrated builds, runtime validation, database validation, OCR validation, cross-module regression, browser evidence, and capstone assessment evidence must run against the Docker stack.

## Unit Test Layout

Automated tests live under the root `tests/` directory, not inside module source folders. They are segregated by test type:

| Folder | Type | Scope |
| --- | --- |
| `tests/unit/identity_access_module/` | Unit/module tests | M1 Identity Access |
| `tests/unit/file_validation_module/` | Unit/module tests | M3/M4 File Validation and Ingestion |
| `tests/unit/document_parsing_module/` | Unit/module tests | M5 Document Parsing |
| `tests/integration/` | Integration/static contracts | Cross-module and infrastructure checks |

Run consolidated host-side unit tests with:

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

The runner invokes each module folder in a separate pytest process because each Python service owns a top-level package named `app`.

## Docker Stack (required for acceptance evidence)

```powershell
# Start the full Stats runtime
docker compose --file infrastructure\compose\stats-runtime.compose.yml `
               --env-file infrastructure\compose\.env.container `
               up --build --detach

# Entry point
# Stats Web:  http://127.0.0.1:8080
# stats-db:   PostgreSQL 16 (internal to stats-runtime)
# stats-runtime container: Stats Web + M1 + M3/M4 + M5 + Tesseract OCR
```

Prerequisites:
- Docker Desktop running
- `infrastructure\compose\.env.container` populated from `.env.container.example` (never committed)
- `tests\\input\\` populated with real fixture files (gitignored; only `tests\\input\\README.md` is tracked)

## Fixture Source

All acceptance and evidence scripts use `tests\\input\\` as the required fixture directory. Do not use Google Drive paths, synthetic files, or host-installed tools as acceptance fixtures. Real source files under `tests\\input\\` are gitignored.

## Script Folders

| Folder | Module | Purpose |
| --- | --- | --- |
| `regression/` | M1-M5 | **Primary Docker regression evidence runner** (start here for capstone evidence) |
| `M13-Containerization/` | M13 | M13-specific Docker acceptance evidence (OCR, container health) |
| `M0-ArchitectureFoundation/` | M0 | Foundation architecture verification helpers |
| `M1-IdentityAccessManagement/` | M1 | Identity and user-access evidence helpers (local runtime) |
| `M2-StatsWebShell/` | M2 | Stats Web shell evidence helpers (local runtime) |
| `M3-M4-FileValidationIngestion/` | M3/M4 | File validation and ingestion evidence helpers (local runtime) |
| `M5-DocumentParsing/` | M5 | Document parsing evidence helpers (local runtime) |
| `cross-module-regression/` | M1-M5 | Cross-module regression helpers |
| `common/` | All | Shared utilities used by evidence scripts |
| `config/` | All | Settings JSON (shared and local-override) |

Scripts in `M1-*` through `M5-*` target the **local runtime** and are suitable for development-time evidence only. For capstone/assessment evidence use the Docker regression runner.

## Primary Evidence Runner

```powershell
# Run from the project root
.\tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

This script:
1. Starts (or reuses) the Docker stack
2. Verifies `stats-db` healthy and `users` table exists (M1)
3. Verifies Stats Web pages via HTTP (M2)
4. Validates every `tests/input/` fixture through M3 File Validation
5. Ingests every validated fixture through M4 File Ingestion
6. Parses every fixture through M5 Document Parsing with Tesseract OCR
7. Runs a cross-module validate -> ingest -> parse pipeline per fixture
8. Writes per-module JSON evidence to `tests/results/DockerRegression/M1/` through `M5/`
9. Writes a dated summary to `tests/results/DockerRegression/docker-regression-summary-YYYY-MM-DD.md`

## M13-Specific Acceptance Runner

```powershell
.\tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1
```

Covers: Docker build, all service health checks, Document Parsing `ocr.enabled=true`, per-fixture OCR parse evidence. Use this to validate a fresh container build.

## Static Contract Tests (host only)

```powershell
pytest tests\integration\test_m13_containerization_contract.py
```

Verifies that all required infrastructure files exist and contain the expected content. Does not require Docker or network access.

## Configuration

Directory paths are configured in `tests/scripts/config/test-script-settings.json`. Machine-specific overrides (e.g. alternate test data folders) belong in an uncommitted `tests/scripts/config/test-script-settings.local.json`. The `docker` section of settings.json defines the canonical Docker acceptance URLs and folder paths.

## Evidence Output

| Folder | Contents |
| --- | --- |
| `tests/results/DockerRegression/` | Full M1-M5 Docker regression evidence (primary) |
| `tests/results/DockerRegression/M1/` | M1 login and user listing JSON |
| `tests/results/DockerRegression/M2/` | M2 Stats Web HTTP status JSON |
| `tests/results/DockerRegression/M3/` | M3 file validation JSON per fixture |
| `tests/results/DockerRegression/M4/` | M4 ingestion record JSON per fixture |
| `tests/results/DockerRegression/M5/` | M5 parse result JSON per fixture |
| `tests/results/DockerRegression/cross-module/` | Cross-module pipeline summary JSON per fixture |
| `tests/results/M13-Containerization/` | M13 acceptance evidence |

Run all scripts from the repository root unless the script header says otherwise.
