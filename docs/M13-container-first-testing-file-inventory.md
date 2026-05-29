<!-- M13 - Containerization Start -->
<!-- Tracks the project-wide container-first testing policy and runtime wiring change. -->

# M13 Container-First Testing File Inventory

## Summary

This inventory records the project-wide change that makes the M13 Stats container the official execution path for module tests, acceptance checks, regression runs, OCR verification, database verification, browser-flow evidence, and capstone assessment evidence.

Current status: **implementation in progress; validation pending**.

The container image was updated and successfully built far enough to confirm Tesseract 5.3.0 and M5 OCR runtime dependencies inside the image. The first container module-test run exposed a runner-path issue (`pytest` not found in the container shell); the runner was corrected to call `/opt/stats/runtime/bin/pytest`. The corrected container test rerun was interrupted by the user before completion, so official validation evidence is still pending.

## Policy Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M13-container-first-testing-policy.md` | Created | Defines the project-wide container-first testing rule from M13 onward. Host-side runs are diagnostics only; official module evidence must run through the container. |
| `docs/M13-containerization-module-spec.md` | Modified | Updates the M13 testing boundary so module unit/contract checks, acceptance, and evidence execute inside the Stats runtime container. |
| `docs/M13-containerization-file-inventory.md` | Modified | Records the M13 policy correction, container module-test runner, M7 packaging, and container-first evidence expectations. |
| `docs/building-block-module-plan.md` | Modified | Updates the building-block plan so future modules require container runtime wiring before official acceptance after M13. |
| `docs/M0-foundation-module-spec.md` | Modified | Updates the foundation standard to require container-based official module evidence after M13. |

## Prior Module Documentation Updates

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M1-user-management-access-control-spec.md` | Modified | Marks M1 official testing as container-executed from M13 onward. |
| `docs/M2-stats-web-shell-spec.md` | Modified | Updates M2 build/evidence expectations to use the Stats container path after M13. |
| `docs/M3-file-validation-module-spec.md` | Modified | Replaces host `pytest` completion wording with container-executed module tests. |
| `docs/M5-document-parsing-module-spec.md` | Modified | Updates M5 testing boundary so unit/contract and OCR evidence run through the container. |
| `docs/M5-document-parsing-file-inventory.md` | Modified | Marks previous host-side M5 evidence as historical diagnostics and records container evidence as the replacement path. |
| `docs/M7-transaction-extraction-module-spec.md` | Modified | Updates M7 regression selection so M7 and affected M5 checks run inside `stats-runtime`. |
| `docs/M7-transaction-extraction-file-inventory.md` | Modified | Marks previous host-side M7 verification as historical diagnostics and records container verification as required. |

## Module README Updates

| File | Change Type | Description |
| --- | --- | --- |
| `modules/README.md` | Modified | States that official module tests and evidence run through the Stats container from M13 onward. |
| `modules/identity-access-module/README.md` | Modified | Replaces local runtime/test instructions with M13 container runtime and test runner instructions. |
| `modules/file-validation-module/README.md` | Modified | Replaces local runtime/test instructions with M13 container runtime and test runner instructions. |
| `modules/document-parsing-module/README.md` | Modified | Replaces local runtime/test instructions with M13 container runtime and Docker OCR acceptance instructions. |
| `modules/transaction-extraction-module/README.md` | Modified | Replaces local runtime/test instructions with M13 container runtime and test runner instructions. |

## Container Runtime Updates

| File | Change Type | Description |
| --- | --- | --- |
| `infrastructure/containers/stats/Dockerfile` | Modified | Adds M7 Transaction Extraction requirements/source and copies root `tests/` into the Stats runtime image so container-executed tests can run. Keeps Tesseract and OCR dependency verification in the image build. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Modified | Starts the Transaction Extraction API on port `8016` and waits for its health endpoint before starting Stats Web. |
| `infrastructure/compose/stats-runtime.compose.yml` | Modified | Adds `TRANSACTION_EXTRACTION_PORT=8016` to the Stats runtime environment. |

## Test Script Updates

| File | Change Type | Description |
| --- | --- | --- |
| `tests/scripts/README.md` | Modified | Documents the container-first testing standard, Docker stack, fixture policy, and official evidence runners. |
| `tests/scripts/regression/run_module_unit_tests.ps1` | Modified | Starts the Docker stack, copies `tests/input` into `stats-runtime`, and runs module unit suites inside the container with `/opt/stats/runtime/bin/pytest`. |
| `tests/scripts/regression/run_docker_full_regression_evidence.ps1` | Modified | Updates script header to state that official module tests and regression evidence run through Docker after M13. |
| `tests/scripts/M13-Containerization/run_docker_acceptance_evidence.ps1` | Modified | Updates header to state that official module tests and evidence run through the container after M13. |
| `tests/scripts/M5-DocumentParsing/run_m5_all_inputs_manual_unit_2026_05_28.py` | Modified | Documents intended official execution through `docker exec stats-runtime`. |
| `tests/scripts/M5-DocumentParsing/run_m5_actual_app_flow_evidence.ps1` | Modified | Marks the script as a historical local diagnostic only. |
| `tests/scripts/M3-M4-FileValidationIngestion/run_app_flow_evidence.ps1` | Modified | Marks the script as a historical local diagnostic only. |
| `tests/scripts/M3-M4-FileValidationIngestion/run_merged_file_intake_evidence.ps1` | Modified | Adds a header marking it as a historical host-side diagnostic after M13. |
| `tests/scripts/cross-module-regression/run_regression_evidence.ps1` | Modified | Adds a header directing official cross-module regression to the Docker runner. |
| `tests/scripts/M13-Containerization/capture_m13_m1_m7_screenshot_evidence_2026_05_28.py` | Planned | Captures final M13 screenshot evidence for M1-M7 against the container runtime, including browser screenshots for Stats Web flows and terminal/API evidence for M7. |

## Integration Test Updates

| File | Change Type | Description |
| --- | --- | --- |
| `tests/integration/README.md` | Modified | Removes stale merge-conflict text and documents that official integration/contract execution runs inside `stats-runtime`. |
| `tests/integration/test_m13_containerization_contract.py` | Modified | Adds checks for M7 container packaging, Transaction Extraction startup, copied test code, and the container module unit runner. |

## Evidence Artefacts

| File | Change Type | Description |
| --- | --- | --- |
| `tests/results/M13-ContainerFirstTesting/M13-container-first-module-unit-summary-YYYY-MM-DD.md` | Created | Summarizes the official container-executed module unit/contract run generated by the container runner. |
| `tests/results/M13-ContainerFirstTesting/M13-container-first-module-unit-raw-output-YYYY-MM-DD.txt` | Created | Raw Docker build/start and container-executed pytest output for M1, M3/M4, M5, M7, M8, and M13 contract checks. |
| `tests/results/M13-Containerization/M13-docker-acceptance-results-2026-05-28.txt` | Created/Modified | Raw M13 Docker acceptance evidence showing container health, Tesseract readiness, database readiness, and per-fixture M5 OCR parsing. |
| `tests/results/M13-Containerization/json-2026-05-28/` | Created/Modified | Per-fixture M5 JSON parse outputs generated inside `stats-runtime`. |
| `tests/results/DockerRegression/docker-regression-summary-YYYY-MM-DD.md` | Created/Modified | Full Docker regression summary for M1-M8 plus cross-module validate -> ingest -> parse -> extract -> validate flow. |
| `tests/results/DockerRegression/docker-regression-raw-output-2026-05-28.txt` | Created/Modified | Raw full Docker regression output showing 50 passed checks, 0 failed, and 1 skipped authenticated-flow check. |
| `tests/results/DockerRegression/M1/` | Created/Modified | M1 container regression evidence output. |
| `tests/results/DockerRegression/M2/` | Created/Modified | M2 Stats Web HTTP evidence output. |
| `tests/results/DockerRegression/M3/` | Created/Modified | M3 per-fixture validation evidence output. |
| `tests/results/DockerRegression/M4/` | Created/Modified | M4 per-fixture ingestion evidence output. |
| `tests/results/DockerRegression/M5/` | Created/Modified | M5 per-fixture OCR/parse evidence output. |
| `tests/results/DockerRegression/M7/` | Created/Modified | M7 transaction extraction evidence output. |
| `tests/results/DockerRegression/M8/` | Created/Modified | M8 data validation evidence output. |
| `tests/results/DockerRegression/cross-module/` | Created/Modified | Cross-module validate -> ingest -> parse -> extract -> validate evidence output per fixture. |

## Validation Plan

Official validation must be completed before commit:

| Check | Command | Expected Evidence |
| --- | --- | --- |
| Container module unit/contract tests | `powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1` | Raw output saved under `tests/results/M13-ContainerFirstTesting/` showing M1, M3/M4, M5, M7, M8, and M13 contract suites run inside `stats-runtime`. |
| Docker acceptance evidence | `powershell -ExecutionPolicy Bypass -File tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1` | M13 evidence showing container health, Tesseract availability, and M5 OCR over `tests/input`. |
| Docker full regression evidence | `powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_docker_full_regression_evidence.ps1` | M1-M8/cross-module evidence under `tests/results/DockerRegression/`. |
| M13 M1-M7 screenshot evidence | `python tests\scripts\M13-Containerization\capture_m13_m1_m7_screenshot_evidence_2026_05_28.py` | Windows browser and terminal screenshots under `tests/results/M13-Containerization/M13-M1-M7-screenshots-2026-05-28/`. |

## Validation Status

| Date | Check | Result | Notes |
| --- | --- | --- | --- |
| 2026-05-28 | `docker compose` build via `run_module_unit_tests.ps1` | Partial | Image built; build output confirmed `tesseract 5.3.0` and M5 OCR dependencies available. |
| 2026-05-28 | First container module unit run | Failed | `pytest` was not found in the container shell. Runner was corrected to use `/opt/stats/runtime/bin/pytest`. |
| 2026-05-28 | Corrected container module unit rerun | Pending | User interrupted before completion. Must rerun before commit. |
| 2026-05-28 | Container module unit rerun with evidence capture | Failed | M1 and M7 passed. M3/M4 failed because `/tmp/stats-pytest` did not exist before `--basetemp`; runner now creates it. M5 failed because the health test expected OCR disabled, but M13 correctly enables Tesseract in the container; test now accepts configured runtime state. |
| 2026-05-28 | Container module unit rerun with full raw evidence | Passed | Docker build/start succeeded, image verified `tesseract 5.3.0`, and container-executed suites passed: M1 `29 passed`, M3/M4 `17 passed`, M5 `19 passed`, M7 `15 passed`. |
| 2026-05-28 | M13 Docker acceptance evidence | Passed | `40 passed, 0 failed`. Container health passed, Document Parsing reported `ocr.enabled=true`, `tesseract_available=true`, `renderer_available=true`, and every supported `tests/input` fixture parsed through M5 inside `stats-runtime` with non-empty text. |
| 2026-05-28 | Full Docker regression evidence | Passed with documented gaps | `50 passed, 0 failed, 1 skipped`. M1 DB table, M2 HTTP pages, M3 validation, M4 ingestion, M5 OCR parsing, and cross-module validate -> ingest -> parse passed for all supported `tests/input` fixtures. Skipped M1 authenticated flow because `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` are not set in `.env.container`; M2 browser screenshots remain manual/visual evidence gap. |

## Commit Readiness

This change set has passing container evidence for module unit/contract tests, M13 acceptance, and full Docker regression. Commit readiness still depends on the user's acceptance of the documented gaps: M1 authenticated-flow evidence requires configured container admin credentials, and M2 browser screenshots require a manual/visual evidence run.

<!-- M13 End -->
