<!-- M8 - Data Validation Module Start -->
<!-- Inventory of files created or changed for M8 data validation. -->

# M8 Data Validation File Inventory

## Scope

M8 creates the standalone reusable Data Validation Module.

It accepts M7-shaped transaction and financial field candidates, then returns normalized records, same-batch duplicate markers, data-quality findings, summary counts, totals, and evaluation metadata.

M8 deliberately does not extract transactions, rerun OCR, query the Stats database, persist records, or render user-facing duplicate warnings. Database duplicate checks belong to M9/M10; user-facing workflow summaries belong to M10/M11.

## Documentation and Contracts

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M8-data-validation-module-spec.md` | Created | Defines goals, non-goals, API contract, finding codes, configuration, acceptance criteria, and the M8 boundary. |
| `docs/M8-data-validation-file-inventory.md` | Created | Tracks M8 files, verification commands, and current implementation notes. |
| `contracts/transactions/README.md` | Modified | Adds the M8 data validation contract and clarifies that M8 handles same-batch duplicate detection while M9 owns database duplicate checks. |
| `modules/README.md` | Modified | Adds `data-validation-module/` to the implemented module list. |
| `apps/stats-web/Pages/Upload.cshtml` | Modified | Exposes M7 and M8 downstream endpoint configuration to the upload page. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Modified | Adds transaction extraction and data validation base URLs to the upload page model. |
| `apps/stats-web/appsettings.json` | Modified | Adds local downstream URLs and local orchestration entries for M7 and M8. |
| `apps/stats-web/Program.cs` | Modified | Adds proxy routing for `/api/v1/extractions` and `/api/v1/validations`. |
| `apps/stats-web/wwwroot/js/upload.js` | Modified | Hides raw M5/M7 JSON details from the normal upload flow and renders a user-facing transaction check results checkpoint after M5 parsing, M7 extraction, and M8 validation. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Adds responsive result metrics, processing steps, review callout, document summary, and transaction preview table styling for the upload checkpoint. |

## Runtime Files

| File | Change Type | Description |
| --- | --- | --- |
| `modules/data-validation-module/README.md` | Created | Documents module responsibility, container runtime command, test command, and configuration boundary. |
| `modules/data-validation-module/requirements.txt` | Created | Lists FastAPI runtime dependencies. |
| `modules/data-validation-module/config/defaults.env` | Created | Provides committed safe runtime defaults. |
| `modules/data-validation-module/app/__init__.py` | Created | Marks the module package. |
| `modules/data-validation-module/app/config.py` | Created | Loads defaults, local overrides, and environment values. |
| `modules/data-validation-module/app/main.py` | Created | Creates the FastAPI app and registers health/validation routes. |
| `modules/data-validation-module/app/models/common.py` | Created | Defines health/root response models. |
| `modules/data-validation-module/app/models/validation.py` | Created | Defines request/result, normalized record, finding, summary, and evaluation models. |
| `modules/data-validation-module/app/routes/health.py` | Created | Adds `/health` and `/` metadata endpoints. |
| `modules/data-validation-module/app/routes/validations.py` | Created | Adds `POST /api/v1/validations`. |
| `modules/data-validation-module/app/services/validation_service.py` | Created/Modified | Adds deterministic transaction normalization, validation findings, financial field normalization, and same-batch duplicate detection. Review follow-up removed a dead date-format entry from the month-format parser list while keeping ISO date handling explicit. |

## Container and Test Runner Wiring

| File | Change Type | Description |
| --- | --- | --- |
| `infrastructure/containers/stats/Dockerfile` | Modified | Packages M8 requirements/source plus safe M13/Stats Web contract input files into the Stats runtime image. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Modified | Starts the Data Validation API on port `8017` and waits for its health endpoint. |
| `infrastructure/compose/stats-runtime.compose.yml` | Modified | Adds `DATA_VALIDATION_PORT=8017` to the Stats runtime environment. |
| `tests/scripts/regression/run_module_unit_tests.ps1` | Modified | Adds the M8 unit suite to the consolidated container module-test runner. |
| `tests/integration/test_m13_containerization_contract.py` | Modified | Adds static contract checks for M8 container packaging, startup port wiring, Compose environment wiring, module test runner inclusion, and LF line endings for the Linux startup script. |
| `.gitattributes` | Created | Keeps shell scripts LF-normalized so Linux container entrypoints remain executable. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/unit/data_validation_module/__init__.py` | Created | Marks the M8 test package. |
| `tests/unit/data_validation_module/conftest.py` | Created | Provides isolated FastAPI test client setup and M7-shaped candidate fixtures. |
| `tests/unit/data_validation_module/test_foundation.py` | Created | Verifies app import, health/root endpoints, and settings defaults/overrides. |
| `tests/unit/data_validation_module/test_validation_api.py` | Created | Verifies the JSON validation endpoint, missing-candidate findings, and upstream finding passthrough. |
| `tests/unit/data_validation_module/test_validation_service.py` | Created | Verifies normalization, warnings, invalid records, same-batch duplicate detection, duplicate detection opt-out, and financial field quality status. |

## Verification

Official container-first module unit tests:

```powershell
powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1
```

Result:

```text
Docker image rebuilt and stats-runtime recreated.
M1 Identity Access: 29 passed
M3/M4 File Validation and Ingestion: 17 passed
M5 Document Parsing: 20 passed
M7 Transaction Extraction: 18 passed
M8 Data Validation: 13 passed
M13 Container Contract: 53 passed
Result: PASSED
```

Evidence:

```text
tests/results/M13-ContainerFirstTesting/M13-container-first-module-unit-raw-output-2026-05-29.txt
tests/results/M13-ContainerFirstTesting/M13-container-first-module-unit-summary-2026-05-29.md
```

Docker-served Upload page JavaScript verification:

```powershell
$page = (Invoke-WebRequest -Uri http://127.0.0.1:8080/Upload -UseBasicParsing).Content
$scriptUrl = ([regex]::Match($page, '/js/upload\.js\?v=[^" ]+')).Value
$script = (Invoke-WebRequest -Uri "http://127.0.0.1:8080$scriptUrl" -UseBasicParsing).Content
```

Result:

```text
Old technical labels not served:
- View M5 to M7 audit output
- View full M5 parse response
- M8 data validation output

New labels served:
- Transaction check results
- Save ready transactions
- Developer details
```

Container-first defects caught and fixed during validation:

- M8 initially pinned FastAPI/Uvicorn/Python-dotenv versions that conflicted with the shared `stats-runtime` environment. M8 requirements now align with the M7 container dependency set.
- The container startup script had Windows line endings after editing, causing Linux entrypoint execution to fail. The script is normalized to LF.
- `.gitattributes` and an M13 contract assertion now guard shell scripts against CRLF line endings.
- The official runner now includes the M13 container contract inside `stats-runtime`, and the Docker image packages the safe contract input files needed for those assertions.

Historical host-side diagnostics were run during development, but they are not M8 acceptance evidence after M13. Official M8 tests and evidence must run inside `stats-runtime` through the container-first runners.

Source label diagnostic:

```powershell
rg -n "View M5 to M7 audit output|View full M5 parse response|M8 data validation output|M8 validation needs review|View full M8 validation output|Transaction check results|Save ready transactions|Developer details" apps\stats-web\wwwroot\js\upload.js apps\stats-web\wwwroot\css\access.css apps\stats-web\Pages\Upload.cshtml
```

Result:

```text
Old technical labels not found.
Visible user labels found: Transaction check results, Save ready transactions, Developer details.
```

## Current Implementation Notes

- The validator is deterministic and rule-based for this first M8 pass.
- It accepts M7-shaped transaction and financial field candidates.
- It normalizes dates to ISO format where possible, cleans descriptions, uppercases currencies, and derives signed amounts from debit/credit direction.
- It flags missing dates, blank descriptions, zero amounts, unknown directions, low-confidence records, low-confidence fields, missing field values, and same-batch duplicates.
- Duplicate detection is limited to the supplied validation batch.
- It does not query the Stats database or check already persisted transactions.
- Stats Web now calls M7 then M8 after a successful parse and shows transaction check results instead of exposing raw M5/M7 JSON in the normal upload view.
- The Upload page should treat M8 as a pre-save checkpoint: users review transaction readiness before any future M9 database write.
- The visible output should use user-facing labels such as transaction check results, ready to save, needs review, and possible duplicate instead of module/debug labels.
- M9 remains responsible for persistence and database duplicate checks.
- M10/M11 remain responsible for composing and displaying user-facing workflow summaries.

<!-- M8 End -->
