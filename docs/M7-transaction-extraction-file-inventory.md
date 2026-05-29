<!-- M7 - Transaction Extraction Module Start -->
<!-- Inventory of files created or changed for M7 transaction extraction. -->

# M7 Transaction Extraction File Inventory

## Scope

M7 creates the first standalone reusable Transaction Extraction Module.

It accepts M5-style parsed text and document context, then returns candidate transactions, financial field candidates, source metadata, confidence values, findings, summary counts, and evaluation metadata.

M7 deliberately does not clean, validate, deduplicate, persist, or report final transaction records.

## Documentation and Contracts

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M7-transaction-extraction-module-spec.md` | Created/Modified | Defines goals, non-goals, inputs, outputs, API contract, extraction strategy, finding codes, OCR-quality input handling, configuration, tests, acceptance criteria, and deferred items. |
| `docs/M7-transaction-extraction-file-inventory.md` | Created | Tracks M7 files, verification commands, and current implementation notes. |
| `contracts/transactions/README.md` | Modified | Adds the M7 transaction extraction contract and clarifies that M7 returns candidates for M8 validation and M9 persistence, while surfacing weak M5 OCR quality as input-quality findings. |

## Runtime Files

| File | Change Type | Description |
| --- | --- | --- |
| `modules/transaction-extraction-module/README.md` | Created | Documents module responsibility, local run command, local test command, and configuration boundary. |
| `modules/transaction-extraction-module/requirements.txt` | Created | Lists FastAPI runtime dependencies. |
| `modules/transaction-extraction-module/.env.example` | Created | Provides safe local override examples. |
| `modules/transaction-extraction-module/config/defaults.env` | Created | Provides committed safe runtime defaults. |
| `modules/transaction-extraction-module/app/__init__.py` | Created | Marks the module package. |
| `modules/transaction-extraction-module/app/config.py` | Created | Loads defaults, local overrides, and environment values. |
| `modules/transaction-extraction-module/app/main.py` | Created | Creates the FastAPI app and registers health/extraction routes. |
| `modules/transaction-extraction-module/app/models/common.py` | Created | Defines health/root response models. |
| `modules/transaction-extraction-module/app/models/extraction.py` | Created | Defines request/result, candidate, finding, summary, and evaluation models. |
| `modules/transaction-extraction-module/app/routes/health.py` | Created | Adds `/health` and `/` metadata endpoints. |
| `modules/transaction-extraction-module/app/routes/extractions.py` | Created | Adds `POST /api/v1/extractions`. |
| `modules/transaction-extraction-module/app/services/extraction_service.py` | Created/Modified | Adds deterministic first-pass transaction and financial field candidate extraction plus M5 input-quality and weak-OCR handling. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/unit/transaction_extraction_module/__init__.py` | Created | Marks the M7 test package. |
| `tests/unit/transaction_extraction_module/conftest.py` | Created | Provides isolated FastAPI test client setup for the M7 module. |
| `tests/unit/transaction_extraction_module/test_foundation.py` | Created | Verifies app import, health/root endpoints, and settings defaults/overrides. |
| `tests/unit/transaction_extraction_module/test_extraction_service.py` | Created/Modified | Verifies missing text, bank statement extraction, proof-of-payment extraction, unknown document confidence handling, M5 quality/finding handoff, weak-OCR handoff, and no-candidate findings. |
| `tests/unit/transaction_extraction_module/test_extraction_api.py` | Created | Verifies the JSON extraction endpoint returns candidates, explicit missing-text findings, and accepts M5-shaped parse results. |

## Evidence Artefacts

All M7 test artefacts are stored under root `tests/` paths.

| File | Change Type | Description |
| --- | --- | --- |
| `tests/results/M7-TransactionExtraction/M7_evidence_from_m5_outputs_2026_05_28.py` | Created | Repeatable evidence runner that feeds saved M5 Docker regression outputs into M7. |
| `tests/results/M7-TransactionExtraction/M7-evidence-from-M5-outputs-raw-output-2026-05-28.txt` | Created | Raw terminal-style output from the M7 evidence run. |
| `tests/results/M7-TransactionExtraction/M7-evidence-from-M5-outputs-summary-2026-05-28.json` | Created | Privacy-safe structured evidence summary. |
| `tests/results/M7-TransactionExtraction/M7-evidence-from-M5-outputs-results-2026-05-28.md` | Created | Assessment-friendly evidence summary. |

## Verification

Historical host-side diagnostic M7 unit tests:

```powershell
pytest tests\unit\transaction_extraction_module --basetemp tests\results\pytest-tmp\transaction-extraction-m7
```

Result:

```text
15 passed, 1 cache warning
```

Historical host-side adjacent M5 diagnostic:

```powershell
$env:STATS_TESTDATA_DIR='C:\000_Capstone\tests\input'
$env:STATS_PARSING_TESTDATA_DIR='C:\000_Capstone\tests\input'
pytest tests\unit\document_parsing_module --basetemp tests\results\pytest-tmp\document-parsing-after-m7
```

Result:

```text
18 passed, 1 cache warning
```

Historical host-side integration contract/orchestration diagnostic:

```powershell
pytest tests\integration\test_m13_containerization_contract.py tests\integration\test_stats_web_orchestration_config.py --basetemp tests\results\pytest-tmp\integration-after-m7
```

Result:

```text
47 passed, 1 cache warning
```

M7 evidence against saved M5 outputs:

```powershell
python tests\results\M7-TransactionExtraction\M7_evidence_from_m5_outputs_2026_05_28.py
```

Result:

```text
Files processed: 6
JPEG/Tesseract inputs: 4 / 6
Transaction candidates: 6
Financial field candidates: 7
M7 status counts: {'completed': 2, 'completed_with_warnings': 4}
Result: PASSED
```

From M13 onward, official M7 verification must run inside `stats-runtime` through `tests\scripts\regression\run_module_unit_tests.ps1` or the Docker regression evidence runner. Host-side results are retained as historical diagnostics only.

## Current Implementation Notes

- The extractor is deterministic and rule-based for this first M7 pass.
- It detects common amount/date patterns, transaction words, transfer/receipt fields, and statement-level amount/date fields.
- It accepts M5-shaped payloads, including classification, quality, metadata, page text, and parse findings.
- It converts M5 low-text/OCR-disabled/OCR-failure/weak-OCR signals into M7 input-quality findings.
- It does not rerun OCR or call Tesseract.
- It returns candidates and confidence metadata only.
- Current M5-output evidence shows the first-pass rules extract candidates from the two OCR-backed PDF results, while three JPEG OCR outputs return no transaction or field candidates and one JPEG returns only a financial field candidate. Those JPEG layouts should drive the next extraction-rule refinement.
- M8 remains responsible for cleaning, normalizing, validating, and deduplicating records.
- M9 remains responsible for Stats persistence.

<!-- M7 End -->
