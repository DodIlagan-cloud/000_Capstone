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
| `modules/transaction-extraction-module/app/models/extraction.py` | Created/Modified | Defines request/result, classification subtype, OCR word-block input, transaction/field/section/entity/reference/line-item/installment candidates, finding, summary, reconciliation, extracted table groups, and evaluation models. |
| `modules/transaction-extraction-module/app/routes/health.py` | Created | Adds `/health` and `/` metadata endpoints. |
| `modules/transaction-extraction-module/app/routes/extractions.py` | Created | Adds `POST /api/v1/extractions`. |
| `modules/transaction-extraction-module/app/services/extraction_service.py` | Created/Modified | Adds deterministic transaction and financial field candidate extraction, M5 document type/subtype alignment, generic statement/table row reconstruction, OCR layout-aware row extraction, OCR layout repair for orphan description fragments and split credit markers, side-column exclusion, OCR-token statement row fallback, receipt/invoice total-derived transaction fallback, receipt-like unknown OCR total fallback, statement metadata/entity extraction, reconciliation, extracted table output, M5 input-quality handling, weak-OCR handling, and OCR-tolerant receipt/invoice field rules. Review hardening on 2026-06-02 makes the orphan-prefix retention behavior explicit so stale prefix fragments do not leak between rows. Fixture robustness on 2026-06-02 adds generic handling for vertically split OCR amount rows, preserves transaction amount-token OCR confidence for M8 review gating, prevents statement footers or side-column `CREDIT LIMIT` text from being treated as transaction amounts or credit markers, keeps statement payments as document-level payment evidence, reconstructs flattened statement payment evidence from paid/payment labels with credit markers, prefers labelled statement-summary payment/credit totals over row-derived payment evidence for reconciliation, prefers billing-currency statement amounts when original foreign-currency amounts also appear, extracts installment purchase/principal rows as reviewable installment candidates, derives receipt transaction dates from generic document-level receipt/OCR date evidence when the amount source line has no date, repairs generic receipt payment-method amount lines when OCR damages currency symbols or labels, prefers nearby terminal timestamp evidence over noisy later date-like fragments, prevents tax/GST-only values from being selected as receipt transaction totals when stronger total/payment evidence exists, and prefers sale/service/location labels over terminal/reference noise for receipt-derived transaction descriptions. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/unit/transaction_extraction_module/__init__.py` | Created | Marks the M7 test package. |
| `tests/unit/transaction_extraction_module/conftest.py` | Created/Modified | Provides isolated FastAPI test client setup and focused OCR-style text fixtures for the M7 module. |
| `tests/unit/transaction_extraction_module/test_foundation.py` | Created | Verifies app import, health/root endpoints, and settings defaults/overrides. |
| `tests/unit/transaction_extraction_module/test_extraction_service.py` | Created/Modified | Verifies missing text, generic statement/table extraction, OCR layout repair, proof-of-payment extraction, single-line OCR receipt/invoice extraction, receipt/invoice total-derived transaction fallback, receipt-like unknown OCR fallback, receipt date fallback from document-level OCR text, OCR-damaged payment-method amount/date repair, receipt total precedence over tax/GST-only amounts, receipt description precedence over terminal/reference noise, unknown document confidence handling, M5 quality/finding handoff, weak-OCR handoff, section-aware non-transaction handling, and no-candidate findings. Review hardening on 2026-06-02 adds targeted generic layout regressions for stale prefixes, side-column amount exclusion, and split credit markers. Fixture robustness on 2026-06-02 adds generic regressions for vertically split amount rows, amount-token OCR confidence preservation, footer amount exclusion, side-column credit-word exclusion, flattened statement-payment evidence, summary payment/credit total precedence over row payment evidence, billing-currency amount selection on foreign-currency statement rows, statement-payment exclusion from transaction candidates, and reviewable installment balance extraction. |
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
- It detects common amount/date patterns, transaction words, transfer/receipt fields, receipt totals, GST fields, invoice/reference identifiers, card receipt amounts, and generic statement/table amount/date fields.
- It reconstructs generic statement/table rows from repeated date/date/description/amount structures, including multi-line descriptions, OCR-flattened statement rows, and month/day dates that need statement-year context.
- It repairs generic OCR layout rows by using transaction-table row context to attach nearby orphan description text, exclude side-column/advisory text, and pair split `CR` markers with the transaction amount.
- It accepts the current M5 `statement` top-level type and uses `document_subtype` such as `credit_card_statement` as a prioritization hint. Historical `bank_statement` is kept only as a compatibility alias.
- It treats issuer/provider names as extracted metadata and reporting dimensions, not issuer-specific parser control logic.
- It returns grouped extracted-data tables so the Upload page can display all extracted data, not only transaction rows.
- M7 tests and fixtures are structure-based. They must not depend on issuer names, bank names, merchant names, source filenames, or institution-specific parser branches.
- It accepts M5-shaped payloads, including classification, quality, metadata, page text, and parse findings.
- It converts M5 low-text/OCR-disabled/OCR-failure/weak-OCR signals into M7 input-quality findings.
- It does not rerun OCR or call Tesseract.
- It returns candidates and confidence metadata only.
- Current M5-output evidence shows all six saved OCR-backed M5 outputs complete in M7. The four JPEG OCR outputs now each return one transaction candidate and at least one financial field candidate.
- M8 remains responsible for cleaning, normalizing, validating, and deduplicating records.
- M9 remains responsible for Stats persistence.

<!-- M7 End -->
