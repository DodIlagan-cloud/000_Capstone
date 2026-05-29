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
| `modules/transaction-extraction-module/README.md` | Created | Documents module responsibility and the M13 container-first runtime/test boundary. |
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
| `modules/transaction-extraction-module/app/services/extraction_service.py` | Created/Modified | Adds deterministic transaction and financial field candidate extraction, M5 input-quality handling, weak-OCR handling, and OCR-tolerant receipt/invoice field rules. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/unit/transaction_extraction_module/__init__.py` | Created | Marks the M7 test package. |
| `tests/unit/transaction_extraction_module/conftest.py` | Created/Modified | Provides isolated FastAPI test client setup and focused OCR-style text fixtures for the M7 module. |
| `tests/unit/transaction_extraction_module/test_foundation.py` | Created | Verifies app import, health/root endpoints, and settings defaults/overrides. |
| `tests/unit/transaction_extraction_module/test_extraction_service.py` | Created/Modified | Verifies missing text, bank statement extraction, proof-of-payment extraction, single-line OCR receipt/invoice extraction, unknown document confidence handling, M5 quality/finding handoff, weak-OCR handoff, and no-candidate findings. |
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

Official container-first M7 unit/contract tests:

```powershell
powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1
```

Official full regression/evidence command:

```powershell
powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

Historical host-side results from earlier development are retained only as development history. From M13 onward, official M7 acceptance and regression evidence must run inside `stats-runtime` through the container-first runners above.

M7 evidence against saved M5 outputs:

```powershell
python tests\results\M7-TransactionExtraction\M7_evidence_from_m5_outputs_2026_05_28.py
```

Result:

```text
Files processed: 6
JPEG/Tesseract inputs: 4 / 6
Transaction candidates: 6
Financial field candidates: 14
M7 status counts: {'completed': 6}
Result: PASSED
```

From M13 onward, official M7 verification must run inside `stats-runtime` through `tests\scripts\regression\run_module_unit_tests.ps1` or the Docker regression evidence runner. Host-side results are retained as historical diagnostics only.

## Current Implementation Notes

- The extractor is deterministic and rule-based for this first M7 pass.
- It detects common amount/date patterns, transaction words, transfer/receipt fields, receipt totals, GST fields, invoice/reference identifiers, card receipt amounts, and statement-level amount/date fields.
- It accepts M5-shaped payloads, including classification, quality, metadata, page text, and parse findings.
- It converts M5 low-text/OCR-disabled/OCR-failure/weak-OCR signals into M7 input-quality findings.
- It does not rerun OCR or call Tesseract.
- It returns candidates and confidence metadata only.
- Current M5-output evidence shows all six saved OCR-backed M5 outputs complete in M7. The four JPEG OCR outputs now each return one transaction candidate and at least one financial field candidate.
- M8 remains responsible for cleaning, normalizing, validating, and deduplicating records.
- M9 remains responsible for Stats persistence.

<!-- M7 End -->
