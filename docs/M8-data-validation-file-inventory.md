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
| `apps/stats-web/wwwroot/js/upload.js` | Modified | Hides raw M3/M4/M5/M7 JSON and intermediate module cards from the normal upload flow, shows one plain-language processing panel, renders the transaction check results checkpoint after M5 parsing, M7 extraction, and M8 validation, hides supporting extracted-data tables behind a toggle, omits raw M7 transaction tables from the normal user extracted-data toggle to avoid duplicate transaction display, and enables local Edit/Accept review actions with reconciliation-gated save readiness. Statement reconciliation uses M7/M8 statement-level payment credits when present instead of assuming payments are transaction rows. Ready rows remain editable before save readiness because high-confidence OCR can still be wrong; Edit remains visibly available where transaction rows are shown. Installment review items use the same local Edit/Accept review pattern while remaining separate from transaction totals. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Adds responsive result metrics, processing steps, review callout, reconciliation status, local edit/review actions, visible row edit affordance, extracted-data toggle, document summary, and transaction preview table styling for the upload checkpoint and intermediate processing state. |

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
| `modules/data-validation-module/app/models/validation.py` | Created/Modified | Defines request/result, normalized transaction record, normalized installment balance record, finding, review item, summary, and evaluation models. |
| `modules/data-validation-module/app/routes/health.py` | Created | Adds `/health` and `/` metadata endpoints. |
| `modules/data-validation-module/app/routes/validations.py` | Created | Adds `POST /api/v1/validations`. |
| `modules/data-validation-module/app/services/validation_service.py` | Created/Modified | Adds deterministic transaction normalization, installment balance normalization, validation findings, financial field normalization, same-batch duplicate detection, and guided review item generation from repaired OCR, suspicious text, duplicate, invalid, installment, and reconciliation signals. Review hardening on 2026-06-02 separates low-confidence diagnostics for fields, entities, and references, generalizes suspicious OCR description review gates, and removes a dead post-cleaning ISO date format path. |

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
| `tests/unit/data_validation_module/test_validation_service.py` | Created/Modified | Verifies normalization, warnings, invalid records, same-batch duplicate detection, duplicate detection opt-out, financial field/entity/reference quality status, richer M7 candidate groups, section-aware transaction review gating, suspicious/repaired OCR review items, installment review items, date normalization cleanup, and reconciliation review items. |

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
- It normalizes transaction and optional posted dates to ISO format where possible, cleans descriptions, uppercases currencies, and derives signed amounts from debit/credit direction.
- It flags missing dates, blank descriptions, zero amounts, unknown directions, low-confidence records, low-confidence fields, missing field values, and same-batch duplicates.
- It flags transaction candidates from non-transaction source sections so statement summaries, fees, rewards, and unknown financial blocks are held for review instead of treated as clean save-ready rows.
- It returns guided review items so the Upload page can show exceptions first instead of requiring users to inspect every extracted row.
- The Upload page local review checkpoint offers Edit and Accept actions only. It does not offer Exclude for transactions; rows must be corrected or accepted before they can join the future save set.
- Ready rows remain editable from the ready/accepted transactions table. M8 readiness is a validation state, not a user lock, because OCR digit loss can still affect high-confidence rows.
- Transaction row Edit actions remain visible. The table should not reserve an Actions column and then hide the only action behind hover.
- Low-confidence transaction amount OCR is a standalone review reason. It does not depend on reconciliation mismatch because amount-token confidence is evidence from M7/M5 itself.
- Statement-like transaction readiness remains gated by reconciliation. Edited/accepted rows are not final ready-to-save while the calculated total differs from the document summary.
- Supporting non-transaction extracted tables are hidden by default behind a toggle so the review queue stays manageable.
- Raw M7 transaction tables are not shown in the normal extracted-data toggle because the primary M8 normalized transaction table is the standard transaction output. Developer details retain raw extraction JSON for troubleshooting.
- Duplicate detection is limited to the supplied validation batch.
- It does not query the Stats database or check already persisted transactions.
- Stats Web now calls M7 then M8 after a successful parse and shows transaction check results instead of exposing raw M5/M7 JSON in the normal upload view.
- The Upload page should treat M8 as a pre-save checkpoint: users review transaction readiness before any future M9 database write.
- The visible output should use user-facing labels such as transaction check results, ready to save, needs review, and possible duplicate instead of module/debug labels.
- The normal Upload page should not show intermediate technical cards such as Accepted, Queued for processing, ingestion IDs, processing file paths, workflow names, or raw module status as the main user-facing result.
- M9 remains responsible for persistence and database duplicate checks.
- M10/M11 remain responsible for composing and displaying user-facing workflow summaries.

<!-- M8 End -->
