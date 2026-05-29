# Stats Test Helpers

This directory contains reusable evidence, regression, and helper scripts for the Stats capstone project.

Project testing follows the build-loop policy in `docs/testing-build-loop-policy.md`: tests are defined and run as features are built, not bolted on after implementation.

Evidence scripts must also follow `docs/privacy-security-data-governance-policy.md`: keep real fixture files local, avoid committing secrets or private paths, and prefer redacted summaries over full sensitive OCR text.

## Testing Boundary (established in M13)

From M13 onward the Stats app is **container-first**. This boundary applies to all modules and all future module work:

| Tier | Purpose | Where to run | Tool |
| --- | --- | --- | --- |
| Module unit/contract tests | Module-level assertions and contract checks | Stats runtime container | `tests/scripts/regression/run_module_unit_tests.ps1` |
| Acceptance, OCR, DB, cross-module regression | Production-like evidence against the full runtime | Stats runtime container / Docker stack | Scripts in this directory |

**Container evidence is the source of truth.**

Host commands are allowed only for editing files and inspecting code. Any test result used for module completion, regression, runtime validation, database validation, OCR validation, browser evidence, or capstone assessment evidence must run against the Docker stack.

## Test Artefact Layout

All test artefacts live under the root `tests/` directory, not inside module or app source folders. They are segregated by test type:

| Folder | Type | Scope |
| --- | --- |
| `tests/unit/identity_access_module/` | Unit/module tests | M1 Identity Access |
| `tests/unit/file_validation_module/` | Unit/module tests | M3/M4 File Validation and Ingestion |
| `tests/unit/document_parsing_module/` | Unit/module tests | M5 Document Parsing |
| `tests/integration/` | Integration/static contracts | Cross-module and infrastructure checks |
| `tests/scripts/` | Evidence scripts and helper scripts | All modules |
| `tests/results/` | Raw output, screenshots, JSON summaries, Markdown evidence | All modules |
| `tests/input/` | Local real-data fixtures | Evidence and real-data tests |

Do not create new module-local `test-results/` folders under `modules/` or `apps/`.

Run consolidated module unit tests inside the container with:

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

The runner starts the M13 Docker stack and invokes each module folder inside `stats-runtime` in a separate pytest process because each Python service owns a top-level package named `app`.

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
| `M1-IdentityAccessManagement/` | M1 | Historical/development helpers; official evidence must use Docker regression |
| `M2-StatsWebShell/` | M2 | Historical/development helpers; official evidence must use Docker regression |
| `M3-M4-FileValidationIngestion/` | M3/M4 | Historical/development helpers; official evidence must use Docker regression |
| `M5-DocumentParsing/` | M5 | Historical/development helpers; official evidence must use Docker regression |
| `cross-module-regression/` | M1-M5 | Cross-module regression helpers |
| `common/` | All | Shared utilities used by evidence scripts |
| `config/` | All | Settings JSON (shared and local-override) |

Scripts in `M1-*` through `M5-*` that target local processes are historical/development helpers only. For module completion, regression, and capstone/assessment evidence use the Docker regression runner.

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

## Container Contract Tests

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

Runs module and contract checks inside the Stats runtime container. Static host inspection may be useful during editing, but it is not official evidence after M13.

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
