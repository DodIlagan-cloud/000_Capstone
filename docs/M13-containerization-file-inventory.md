<!-- M13 - Containerization Start -->
<!-- Documents the files created or modified for M13 Containerization. -->

# M13 Containerization File Inventory

## Summary

This document lists the files created or modified for **M13 Containerization**. M13 packages the full Stats runtime into a single container with a companion `stats-db` PostgreSQL service, enabling Tesseract OCR for M5 and consistent local execution across environments.

Current status: **implementation complete** for all container infrastructure files, startup orchestration, Compose profile with `stats-db`, environment example, Stats Web `/health` endpoint, and integration contract tests (41 checks). Full Docker regression evidence runner (M1-M5) added. Testing boundary documentation applied to all module READMEs, specs, and file inventories. The M13 evidence runner requires project-root `test-input/` fixtures for every OCR evidence run.

## Specification and Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M13-containerization-module-spec.md` | Created / Updated | Defines M13 goals, non-goals, what gets packaged, container structure including `stats-db`, startup orchestration order, Dockerfile build-time verification, runtime config, health check table, OCR validation requirements, testing, and acceptance criteria. Updated to require project-root `test-input/` fixtures for every OCR evidence run. |
| `docs/M13-containerization-file-inventory.md` | Created / Updated | This file. Updated to include all files touched in both the initial implementation and the architectural correction pass. |

## Container Infrastructure

| File | Change Type | Description |
| --- | --- | --- |
| `infrastructure/containers/stats/Dockerfile` | Created / Updated | Multi-stage build: Stage 1 publishes Stats Web using the .NET 9 SDK. Stage 2 builds the final runtime on `python:3.13-slim`, installs Tesseract OCR and English tessdata, installs the .NET ASP.NET Core 9 runtime, installs all Python module dependencies, runs build-time verification of Tesseract/PyMuPDF/pytesseract/Pillow, copies module source and Stats Web build output, sets OCR environment variables, and sets the startup script as the container entrypoint. All box-drawing characters replaced with plain ASCII. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Created / Updated | Startup orchestration script. Waits for `stats-db` PostgreSQL to be reachable, runs identity DB init (`init_db()`), starts Identity Access API (8013) / File Validation API (8014) / Document Parsing API (8015) in background, waits for each `/health` endpoint, then starts Stats Web in the foreground. |
| `infrastructure/containers/stats/.env.container.example` | Created / Updated | Documents all required container environment variables. Updated to use `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` for the `stats-db` service and to clarify that `DATABASE_URL` is wired automatically in the Compose file to point to `stats-db`. |
| `infrastructure/compose/stats-runtime.compose.yml` | Created / Updated | Local full-stack Compose profile. Defines `stats-db` (PostgreSQL 16, persistent `stats-db-data` volume, `pg_isready` health check) and `stats` (single Stats runtime image, `depends_on: stats-db: service_healthy`, `DATABASE_URL` pointing to `stats-db`, Stats Web port mapping, Compose-level health check against `/health`). |

## Stats Web

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/Program.cs` | Modified | Added a `MapGet("/health")` minimal endpoint returning `{"status":"healthy","service":"Stats Web"}` so the M13 Compose health check and container startup script can verify Stats Web is ready. Tagged with M13 module markers. |

## Integration Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/integration/test_m13_containerization_contract.py` | Created / Updated | Contract checks cover `stats-db` service in Compose, `stats-db-data` volume, `DATABASE_URL` pointing to `stats-db`, `depends_on`, Dockerfile build-time verification steps for Tesseract/PyMuPDF/pytesseract/Pillow, startup script database wait and `init_db`, Stats Web `/health`, and the required `test-input/` evidence runner policy. |
| `test-results/M13-Containerization/M13_containerization_terminal_check.py` | Created / Updated | Evidence runner for live container validation. It now requires `test-input/`, copies every supported local fixture into `stats-runtime`, parses each file through M5, requires image files to use `strategy: tesseract_ocr`, and forces PDFs through OCR to exercise PyMuPDF plus Tesseract. |
| `test-input/README.md` | Created | Documents the local fixture directory contract. Real source files in this folder stay local-only and are ignored by Git. |
| `.gitignore` | Updated | Ignores local source files under `test-input/` while allowing `test-input/README.md` to be committed. |
| `.dockerignore` | Updated | Excludes local `test-input/` source files from Docker build context; evidence runs copy fixtures into the running container explicitly. |

## Docker Acceptance Evidence Infrastructure

| File | Change Type | Description |
| --- | --- | --- |
| `tests/scripts/M13-Containerization/run_docker_acceptance_evidence.ps1` | Created | Main Docker acceptance evidence script. Starts the full Stats runtime stack via Compose, waits for Stats Web health, verifies all module API health endpoints via `docker exec`, checks that Document Parsing reports `ocr.enabled: true`, verifies the `users` table exists in `stats-db`, runs M5 OCR evidence against every supported file in `test-input/`, collects a container log snapshot, and writes a dated results summary. |
| `tests/scripts/config/test-script-settings.json` | Modified | Added `M13Containerization` evidence folder and script folder entries. Added `testInputDir` to `localPaths`. Added a `docker` section with `statsWebBaseUrl` pointing to port 8080, Compose file reference, service names, evidence folder, and a note that internal module ports 8013/8014/8015 are container-internal only. |
| `tests/scripts/M5-DocumentParsing/run_m5_actual_app_flow_evidence.ps1` | Modified | Added testing boundary header comment noting local runtime scope and directing capstone/assessment evidence runs to the M13 Docker acceptance script. |
| `tests/scripts/M3-M4-FileValidationIngestion/run_app_flow_evidence.ps1` | Modified | Added testing boundary header comment noting local runtime scope and directing capstone/assessment evidence runs to the M13 Docker acceptance script. |

## Module READMEs Updated

| File | Change Type | Description |
| --- | --- | --- |
| `modules/document-parsing-module/README.md` | Modified | Added Testing Boundary (M13) section with a two-tier table (unit/contract on host via pytest; acceptance/OCR evidence in Docker via M13 script). Notes that `ALLOW_OCR_FALLBACK=false` by default locally. |
| `modules/file-validation-module/README.md` | Modified | Added Testing Boundary (M13) section with a two-tier table (unit/contract on host via pytest; acceptance in Docker via M13 script). |

## Specification Updates

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M13-containerization-module-spec.md` | Modified | Added Testing Boundary section before the Testing section. Defines the two-tier split: unit/contract tests on host via pytest; acceptance/evidence in Docker via the M13 acceptance script. |
| `docs/M5-document-parsing-module-spec.md` | Modified | Added Testing Boundary (M13) section before the Testing section. Clarifies that OCR end-to-end evidence requires the M13 containerized runtime. |

## Docker Full Regression Evidence Infrastructure

| File | Change Type | Description |
| --- | --- | --- |
| `tests/scripts/regression/run_docker_full_regression_evidence.ps1` | Created | Primary M1-M5 Docker regression evidence runner. Covers: M1 DB init/login/user listing, M2 Stats Web page presence, M3 per-fixture validation, M4 per-fixture ingestion, M5 per-fixture OCR/text parsing, and cross-module validate→ingest→parse pipeline. Writes dated JSON evidence per module and a Markdown summary report. |
| `test-results/DockerRegression/` | Created | Evidence root for Docker full regression runs. |
| `test-results/DockerRegression/M1/` | Created | M1 login and user listing JSON evidence. |
| `test-results/DockerRegression/M2/` | Created | M2 Stats Web HTTP status JSON evidence. |
| `test-results/DockerRegression/M3/` | Created | M3 file validation JSON per fixture. |
| `test-results/DockerRegression/M4/` | Created | M4 ingestion record JSON per fixture. |
| `test-results/DockerRegression/M5/` | Created | M5 parse result JSON per fixture. |
| `test-results/DockerRegression/cross-module/` | Created | Cross-module pipeline summary JSON per fixture. |
| `tests/scripts/README.md` | Modified | Full rewrite to document the Docker-first testing standard. Added testing boundary table, Docker stack instructions, fixture source policy, script folder directory, and evidence output paths. |
| `tests/integration/test_m13_containerization_contract.py` | Modified | Added 10 new checks for the Docker regression runner: file existence, stats-runtime/stats-db references, test-input usage, Stats Web port, /api/v1/parses endpoint, M1-M5 coverage, .env.container reference, token truncation, and testing boundary documentation. Total: 41 checks. |

## Module READMEs Updated (Regression Pass)

| File | Change Type | Description |
| --- | --- | --- |
| `modules/identity-access-module/README.md` | Modified | Added Testing Boundary (M13) section directing acceptance evidence to the Docker regression script. |
| `apps/stats-web/README.md` | Modified | Added Testing Boundary (M13) section clarifying that capstone evidence uses port 8080 in Docker, not local port 5013. |

## Specification Updates (Regression Pass)

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M3-file-validation-module-spec.md` | Modified | Added Testing Boundary (M13) section before the Testing section. |
| `docs/M1-user-management-file-inventory.md` | Modified | Added Testing Boundary (M13) section. |
| `docs/M2-stats-web-shell-file-inventory.md` | Modified | Added Testing Boundary (M13) section. |
| `docs/M3-file-validation-file-inventory.md` | Modified | Added Testing Boundary (M13) section. |
| `docs/M5-document-parsing-file-inventory.md` | Modified | Added Testing Boundary (M13) section. |

## Architecture Documentation Updated

| File | Change Type | Description |
| --- | --- | --- |
| `docs/building-block-module-plan.md` | Modified | Updated in the same session to reflect M5 merge. |
| `docs/building-block-module-io-map.md` | Modified | Updated in the same session to reflect M5 merge. |
| `contracts/extraction/README.md` | Modified | Updated in the same session with concrete M5 contract. |

## Test Results and Evidence

| File | Change Type | Description |
| --- | --- | --- |
| `test-results/M13-Containerization/M13-containerization-contract-raw-output-2026-05-28.txt` | Created | Raw output from the M13 contract check. |
| `test-results/M13-Containerization/M13-containerization-test-results-2026-05-28.md` | Created / Updated | Summarizes the M13 validation results and documents the required `test-input/` policy for future OCR runs. |
| `test-results/M13-Containerization/M13-containerization-manual-test-checklist.md` | Updated | Updated with checklist items for `stats-db`, DB init, Stats Web `/health`, build-time verification, and required `test-input/` use. |
| `test-results/M13-Containerization/M13-containerization-screenshot-evidence-2026-05-28.md` | Created / Updated | Screenshot evidence index. Notes that the next capture should show real `test-input/` parse results. |

## Verification

The M13 contract check was verified with:

```text
pytest tests/integration/test_m13_containerization_contract.py
```

Result: **41 passed** (31 original + 10 new regression runner checks)

Live OCR and full M1-M5 regression evidence uses:

```powershell
.\tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

Fixture source: `C:\000_Capstone\test-input` (gitignored real files).

<!-- M13 End -->
