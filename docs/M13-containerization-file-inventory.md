<!-- M13 - Containerization Start -->
<!-- Documents the files created or modified for M13 Containerization. -->

# M13 Containerization File Inventory

## Summary

This document lists the files created or modified for **M13 Containerization**. M13 packages the full Stats runtime into a single container with Tesseract OCR for M5 and environment-driven database connectivity. The active cloud-dev/runtime direction in this branch is Azure SQL through `DATABASE_PROVIDER=AzureSql` and `AZURE_SQL_CONNECTIONSTRING`.

Current status: **implementation updated** for project-wide container-first testing. The Stats runtime container packages module source, test scripts, and test inputs so official module tests, acceptance, regression, OCR, database, and evidence runs execute through Docker from M13 onward. Host-side results are historical/development diagnostics only.

## Specification and Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M13-containerization-module-spec.md` | Created / Updated | Defines M13 goals, non-goals, what gets packaged, startup orchestration order, Dockerfile build-time verification, runtime config, health check table, OCR validation requirements, testing, and acceptance criteria. Updated to require project-root `tests/input/` fixtures for every OCR evidence run, to align with the Azure SQL runtime direction, and to clarify that active recognition settings live in M9 rather than mutable JSON inside the image. |
| `docs/M13-container-first-testing-policy.md` | Created | Defines the project-wide policy that official module tests and evidence run through the container after M13. |
| `docs/M13-container-first-testing-file-inventory.md` | Created | Dedicated inventory for the project-wide container-first testing correction, including affected files, validation plan, and pending evidence status before commit. |
| `docs/M13-containerization-file-inventory.md` | Created / Updated | This file. Updated to include all files touched in both the initial implementation and the architectural correction pass. |

## Container Infrastructure

| File | Change Type | Description |
| --- | --- | --- |
| `infrastructure/containers/stats/Dockerfile` | Created / Updated | Multi-stage build: publishes Stats Web, installs Tesseract OCR, English tessdata, Microsoft ODBC Driver 18, UnixODBC, Python module dependencies, copies M1/M3-M4/M5/M7/M8 module source, copies root test scripts/tests and safe documentation required by contract checks, verifies OCR and Azure SQL runtime dependencies, sets OCR/database environment variables, and sets the startup script as the container entrypoint. Real `tests/input` fixtures remain excluded from image build and are copied into the running container by evidence runners. Recognition-setting migration/seed assets may be packaged, but active labels/rules are persisted in M9 and must survive rebuild/redeploy. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Created / Updated | Startup orchestration script. Waits for Azure SQL connectivity, runs identity DB init, starts Identity Access API (8013), File Validation API (8014), Document Parsing API (8015), Transaction Extraction API (8016), and Data Validation API (8017), waits for each `/health`, then starts Stats Web in the foreground. |
| `infrastructure/containers/stats/.env.container.example` | Created / Updated | Documents all required container environment variables for the active Azure SQL runtime. Real connection strings and secrets belong only in ignored local env files, Container Apps secrets, or Key Vault. Review follow-up clarifies that local Docker Compose requires a real ignored `AZURE_SQL_CONNECTIONSTRING`. |
| `infrastructure/compose/stats-runtime.compose.yml` | Created / Updated | Full-stack Compose profile for the single `stats` runtime image. It reads `.env.container`, maps Stats Web, enables OCR, configures module ports, uses Azure SQL environment variables, and runs the Compose-level health check. Review follow-up documents why the 90-second start period is retained and makes missing `AZURE_SQL_CONNECTIONSTRING` fail fast with a clear Compose error. |

## Stats Web

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/Program.cs` | Modified | Added a `MapGet("/health")` minimal endpoint returning `{"status":"healthy","service":"Stats Web"}` so the M13 Compose health check and container startup script can verify Stats Web is ready. Tagged with M13 module markers. |

## Integration Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/integration/test_m13_containerization_contract.py` | Created / Updated | Contract checks cover `stats-db` service in Compose, `stats-db-data` volume, `DATABASE_URL` pointing to `stats-db`, `depends_on`, Dockerfile build-time verification steps for Tesseract/PyMuPDF/pytesseract/Pillow, startup script database wait and `init_db`, Stats Web `/health`, and the required `tests/input/` evidence runner policy. |
| `tests/results/M13-Containerization/M13_containerization_terminal_check.py` | Created / Updated | Evidence runner for live container validation. It now requires `tests/input/`, copies every supported local fixture into `stats-runtime`, parses each file through M5, requires image files to use `strategy: tesseract_ocr`, and forces PDFs through OCR to exercise PyMuPDF plus Tesseract. |
| `tests/input/README.md` | Created | Documents the local fixture directory contract. Real source files in this folder stay local-only and are ignored by Git. |
| `.gitignore` | Updated | Ignores local source files under `tests/input/` while allowing `tests/input/README.md` to be committed. |
| `.dockerignore` | Updated | Excludes local `tests/input/` source files from Docker build context; evidence runs copy fixtures into the running container explicitly. |

## Docker Acceptance Evidence Infrastructure

| File | Change Type | Description |
| --- | --- | --- |
| `tests/scripts/M13-Containerization/run_docker_acceptance_evidence.ps1` | Created | Main Docker acceptance evidence script. Starts the full Stats runtime stack via Compose, waits for Stats Web health, verifies all module API health endpoints via `docker exec`, checks that Document Parsing reports `ocr.enabled: true`, verifies the `users` table exists in `stats-db`, runs M5 OCR evidence against every supported file in `tests/input/`, collects a container log snapshot, and writes a dated results summary. |
| `tests/scripts/config/test-script-settings.json` | Modified | Documents container-internal module ports 8013/8014/8015/8016/8017 and keeps port 8080 as the only external Stats Web entry point for evidence runs. |
| `tests/scripts/M5-DocumentParsing/run_m5_actual_app_flow_evidence.ps1` | Modified | Historical host-oriented script now delegates to the Docker full regression runner. |
| `tests/scripts/M3-M4-FileValidationIngestion/run_app_flow_evidence.ps1` | Modified | Historical host-oriented script now delegates to the Docker full regression runner. |

## Module READMEs Updated

| File | Change Type | Description |
| --- | --- | --- |
| `modules/document-parsing-module/README.md` | Modified | Documents that official unit/contract and acceptance/OCR evidence runs through the container after M13. |
| `modules/file-validation-module/README.md` | Modified | Documents that official unit/contract and acceptance evidence runs through the container after M13. |

## Specification Updates

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M13-containerization-module-spec.md` | Modified | Defines container-first unit/contract and acceptance/evidence execution, and includes M7/M8 packaged-service requirements. |
| `docs/M5-document-parsing-module-spec.md` | Modified | Added Testing Boundary (M13) section before the Testing section. Clarifies that OCR end-to-end evidence requires the M13 containerized runtime and that active recognition settings come from M9 rather than in-image JSON. |

## Docker Full Regression Evidence Infrastructure

| File | Change Type | Description |
| --- | --- | --- |
| `tests/scripts/regression/run_docker_full_regression_evidence.ps1` | Created/Modified | Primary M1-M8 Docker regression evidence runner. Covers: M1 DB init/login/user listing, M2 Stats Web page presence, M3 validation, M4 ingestion, M5 parsing, M7 extraction, M8 validation, and cross-module validate -> ingest -> parse -> extract -> validate pipeline. Writes dated JSON evidence per module and a Markdown summary report. |
| `tests/scripts/regression/run_module_unit_tests.ps1` | Modified | Runs consolidated module unit tests inside `stats-runtime` using `docker compose` and `docker exec`, copies approved `tests/input` fixtures into the running container, and replaces host-side `pytest` as the official module unit/contract path. |
| `tests/results/DockerRegression/` | Created | Evidence root for Docker full regression runs. |
| `tests/results/DockerRegression/M1/` | Created | M1 login and user listing JSON evidence. |
| `tests/results/DockerRegression/M2/` | Created | M2 Stats Web HTTP status JSON evidence. |
| `tests/results/DockerRegression/M3/` | Created | M3 file validation JSON per fixture. |
| `tests/results/DockerRegression/M4/` | Created | M4 ingestion record JSON per fixture. |
| `tests/results/DockerRegression/M5/` | Created | M5 parse result JSON per fixture. |
| `tests/results/DockerRegression/M7/` | Created | M7 extraction JSON per fixture. |
| `tests/results/DockerRegression/M8/` | Created | M8 validation JSON per fixture. |
| `tests/results/DockerRegression/cross-module/` | Created | Cross-module pipeline summary JSON per fixture. |
| `tests/scripts/README.md` | Modified | Documents the container-first testing standard. Official module unit/contract, acceptance, OCR, DB, browser, and regression evidence must run through Docker. |
| `tests/integration/test_m13_containerization_contract.py` | Modified | Checks the Docker regression runner, M1-M8 packaged-service wiring, `.env.container` handling, LF shell scripts, and container-first testing boundary documentation. |

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
| `tests/results/M13-Containerization/M13-containerization-contract-raw-output-2026-05-28.txt` | Created | Raw output from the M13 contract check. |
| `tests/results/M13-Containerization/M13-containerization-test-results-2026-05-28.md` | Created / Updated | Summarizes the M13 validation results and documents the required `tests/input/` policy for future OCR runs. |
| `tests/results/M13-Containerization/M13-containerization-manual-test-checklist.md` | Updated | Updated with checklist items for `stats-db`, DB init, Stats Web `/health`, build-time verification, and required `tests/input/` use. |
| `tests/results/M13-Containerization/M13-containerization-screenshot-evidence-2026-05-28.md` | Created / Updated | Screenshot evidence index. Notes that the next capture should show real `tests/input/` parse results. |

## Verification

<!-- M13 - Containerization Start -->
The current official verification path is the container-first module runner:

```powershell
powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1
```

Latest recorded result:

```text
M0 Architecture Foundation: 1 passed
M1 Identity Access: 29 passed
M3/M4 File Validation and Ingestion: 17 passed
M5 Document Parsing: 20 passed
M7 Transaction Extraction: 18 passed
M8 Data Validation: 13 passed
M2 Stats Web configuration: 3 passed
M13 Container Contract: 53 passed
Result: PASSED
```

The historical standalone M13 contract check was verified with:

```text
pytest tests/integration/test_m13_containerization_contract.py
```

Result: **41 passed** (31 original + 10 new regression runner checks)

Live OCR and full M1-M8 regression evidence uses:

```powershell
.\tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

Fixture source: `STATS_APP_ROOT + tests/input` (gitignored real files).
<!-- M13 End -->

<!-- M13 End -->
