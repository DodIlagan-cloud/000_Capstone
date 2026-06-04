<!-- M8 - Data Validation Module Start -->
<!-- Specifies the data validation module before implementation grows. -->

# Module 8 Data Validation Module Specification

## Module Summary

Module 8 establishes the reusable **Data Validation Module** for the Stats project.

<!-- M8 - Robust Candidate Input Start -->
M8 receives transaction, financial field, section, entity, reference, and line-item candidates from M7, cleans candidate values, validates required fields, detects duplicate records within the supplied validation request, and returns normalized records with data-quality findings.
<!-- M8 - Robust Candidate Input End -->

This module does **not** extract transactions, rerun OCR, classify documents, persist records, or render dashboards. Those concerns belong to M5, M7, M9, and M11.

## Architecture Alignment

| Field | M8 Direction |
| --- | --- |
| Build order | `8` |
| Module | Data Validation Module |
| Type | Standalone reusable module |
| Main responsibility | Clean, validate, warn, and detect duplicates/incomplete transaction records |
| Reusable contract | Data-quality report contract |
| Owner folder | `modules/data-validation-module/` |
| Stats Web role | May call M8 after M7 extraction; must not implement validation rules |

## Goals

- Provide a standalone FastAPI service for validating M7 candidates.
- Accept M7-shaped transaction, financial field, section, entity, reference, and line-item candidates as JSON.
- Normalize transaction dates, descriptions, currencies, directions, and signed amounts.
- Accept optional posted/settled date text from M7 when statement-like tables provide both transaction and post dates.
- Normalize document-level financial fields such as statement dates, due dates, totals, balances, invoice totals, paid/owing amounts, taxes, payment references, and masked account/card references where supplied by M7.
- Preserve M7 source context so every validated value can be traced back to document, page, section, line, and redacted evidence snippet.
- Use M7 section context to distinguish transaction rows from statement summaries, receipt totals, invoice summaries, payment proofs, fees/interest blocks, rewards/points blocks, and unknown financial blocks.
- Flag missing date, missing description, invalid amount, unknown direction, and low confidence.
- Flag ambiguous source context, missing section context, mismatched totals, missing references, and sensitive values that were not masked before validation.
- Detect duplicate transaction records within the supplied validation batch using deterministic date, description, amount, currency, and direction keys.
- Prepare dashboard-ready quality statuses for both transaction records and document-level financial facts.
- Preserve upstream M7 extracted table groups and reconciliation status for user review. M8 may add validation status/review columns, but it must not hide non-transaction extracted data.
- Produce guided review output that prioritizes exceptions before full extracted data. M8 must create review items for repaired OCR rows, suspicious OCR text, reconciliation mismatches, duplicates, and incomplete or ambiguous records so Stats Web can show a small review queue instead of asking the user to inspect every row.
- Keep database-backed duplicate checks out of M8; M9/M10 will compare normalized records against stored transactions before persistence.
- Return summary and evaluation metadata for module evidence.
- Keep runtime behavior configurable through safe defaults, ignored local overrides, and environment variables.
- Follow the central Stats path convention if file-based fixtures or evidence paths are added: resolve logical paths from `config/stats.paths.json` and `STATS_APP_ROOT` instead of assuming a local, container, or cloud root.

## Non-Goals

- OCR, parsing, document classification, or transaction extraction.
- Stats database writes, migrations, or persistence adapters.
- Dashboard/report rendering.
- Cross-document or database-backed historical reconciliation beyond supplied candidates.
- Issuer-specific statement parsing or merchant-specific receipt parsing.
- Email retrieval or cloud deployment.

<!-- M8 - Robust Candidate Input Start -->
## Input Candidate Groups

M8 accepts the richer M7 extraction shape while keeping validation separate from extraction.

| Candidate Group | M8 Use |
| --- | --- |
| `transaction_candidates` | Normalize into transaction records, signed amounts, duplicate keys, and record-level findings. |
| `financial_field_candidates` | Normalize statement, invoice, receipt, payment proof, tax/GST, fee, balance, due-date, and amount fields. |
| `section_candidates` | Preserve and use source context so values are interpreted by origin area rather than by amount alone. |
| `entity_candidates` | Normalize institutions, merchants, providers, counterparties, payment channels, and card/payment types. |
| `reference_candidates` | Normalize invoice numbers, approval codes, confirmation numbers, document references, and masked account/card/customer references. |
| `line_item_candidates` | Validate item/service rows when supplied and compare line totals against document totals where possible. |
| `installment_candidates` | Normalize installment balance candidates from M7 and create review items using the same review-first pattern as transactions while keeping them separate from current transaction totals. |

M8 should tolerate partial candidate groups. For example, a proof-of-payment image may contain no transaction table but still contain payment amount, confirmation number, counterparty, and payment channel candidates.

`document_financial_summary` is reserved for document-level facts such as statement summaries, invoice totals, receipt totals, payment proof details, tax/GST, balances, fees, and due dates. Fields sourced from `transaction_table` stay with `normalized_records` and are intentionally excluded from `document_financial_summary` so transaction rows are not double-counted as document totals.

Installment balance candidates are reviewable records, but they are not normal transactions. M8 must validate their description, amount, currency, and term/progress evidence where supplied, then surface review items when an installment candidate is incomplete, low-confidence, or ambiguous. Installment candidates must not change transaction debit/credit totals or statement reconciliation.
<!-- M8 - Robust Candidate Input End -->

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/validations` | `POST` | Validates and normalizes transaction candidates. |

## Finding Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `MISSING_CANDIDATES` | Error | No transaction or financial field candidates were supplied. |
| `MISSING_TRANSACTION_DATE` | Warning | A transaction candidate lacks a usable date. |
| `MISSING_DESCRIPTION` | Warning | A transaction candidate lacks a usable description. |
| `INVALID_AMOUNT` | Warning | A transaction amount is zero or negative after cleaning. |
| `UNKNOWN_DIRECTION` | Warning | Debit/credit direction is missing or unknown. |
| `LOW_CONFIDENCE_RECORD` | Warning | Candidate confidence is below the configured validation threshold. |
| `LOW_CONFIDENCE_FIELD` | Warning | Financial field confidence is below the configured validation threshold. |
<!-- Review Hardening - 2026-06-02 Start -->
| `LOW_CONFIDENCE_AMOUNT` | Warning | Transaction amount OCR confidence is below the configured validation threshold. This creates a review item even when the full row otherwise validates and even when reconciliation is unavailable. |
| `LOW_CONFIDENCE_ENTITY` | Warning | Entity candidate confidence is below the configured validation threshold. |
| `LOW_CONFIDENCE_REFERENCE` | Warning | Reference candidate confidence is below the configured validation threshold. |
<!-- Review Hardening - 2026-06-02 End -->
| `MISSING_FIELD_VALUE` | Warning | A financial field has no usable value. |
| `MISSING_SECTION_CONTEXT` | Warning | A candidate lacks enough source-section context for confident interpretation. |
| `NON_TRANSACTION_SECTION` | Warning | A transaction candidate came from a section that is normally document summary, fees, rewards, or unknown financial context rather than a transaction table. |
| `AMBIGUOUS_FINANCIAL_FIELD` | Warning | A financial field could represent more than one dashboard meaning. |
| `UNMASKED_SENSITIVE_REFERENCE` | Warning | A reference candidate appears to contain sensitive account, card, customer, or patient data without masking. |
| `TOTAL_RECONCILIATION_WARNING` | Warning | Supplied line items, paid/owing amounts, or summary totals do not reconcile within tolerance. |
| `DUPLICATE_TRANSACTION` | Warning | A normalized transaction duplicates an earlier normalized record in the same validation batch. |
| `RECORD_LIMIT_APPLIED` | Warning | Only the configured maximum records were validated. |
| `OCR_REPAIR_REVIEW` | Warning | M7 repaired OCR layout text and the row should be reviewed before final save. |
| `SUSPICIOUS_OCR_TEXT` | Warning | A normalized description contains generic likely OCR damage such as empty text, a one-character leading token, or an OCR-substitution prefix that leaves the first word malformed. This must be treated as a review gate, not as an issuer- or merchant-specific correction. |
| `DOCUMENT_RECONCILIATION_REVIEW` | Warning | M7/M8 reconciliation indicates extracted totals do not match the document summary. |

## Guided Review Output

M8 returns a review-first view for Stats Web:

| Output | Description |
| --- | --- |
| `review_items` | Prioritized review queue for the Upload page. Items may point to a record, field, document-level reconciliation issue, or upstream finding. |
| `summary.review_item_count` | Total number of actionable review items. |
| `summary.document_review_status` | `ready`, `needs_review`, or `blocked`. |
| `summary.recommended_action` | Suggested next action such as `review_items_before_saving_all`, `save_ready_transactions`, or `fix_blocking_errors`. |
| `summary.reconciliation_delta` | Amount difference when the document summary and extracted transactions do not reconcile. |

Stats Web should default to the `review_items` queue when it is non-empty, then allow users to open ready transactions and all extracted data as secondary views.

<!-- M8 Review UX - 2026-06-02 Start -->
Stats Web review actions before M9 persistence are local to the current upload session:

- `Edit` allows the user to correct transaction date, posted date, description, amount, currency, and direction for any transaction row shown in the Upload checkpoint, including rows M8 initially marked `Ready`.
- `Accept` confirms that a reviewed transaction row should join the ready-to-save set for the current upload session.
- A high-confidence or `Ready` row must still remain editable because OCR can miss or alter digits even when the row passes M8 validation rules.
- The transaction-row `Edit` action must remain visible wherever transaction rows are shown. Hiding an already-reserved action column behind hover does not add user value in this checkpoint.
- Transaction rows must not offer an `Exclude` action in this iteration because every extracted transaction should either be corrected or accepted before the future database write.
- Accepting rows does not persist anything. M9/M10 will own database writes and database-backed duplicate checks.
- Statement-like documents must keep save readiness gated by reconciliation. After each edit or accept, the Upload page recalculates document totals using the supplied M7/M8 reconciliation facts. When M7 has separated statement payments into document-level `payments_and_credits`, the Upload page must use that reconciliation credit total instead of assuming all credits are transaction rows. Transactions are not final ready-to-save while the calculated total differs from the document total outside tolerance.
- Non-transaction extracted data tables such as statement summary, document summary, entities/references, line items, and findings must be hidden behind a user-controlled toggle by default. The review queue and transaction readiness state remain the primary visible checkpoint.
<!-- M8 Review UX - 2026-06-02 End -->

<!-- Fixture Robustness - 2026-06-02 Start -->
Stats Web must provide a standard Upload checkpoint across supported document types. The normal user view should show one normalized transaction/review surface from M8. Raw M7 `transactions` extracted-data tables must not be repeated in the normal extracted-data toggle because they duplicate M8 normalized transaction rows; raw transaction candidates may remain in developer details for troubleshooting. Supporting non-transaction tables such as document summary, statement summary, entities/references, line items, findings, and reconciliation details may remain available behind the toggle.
<!-- Fixture Robustness - 2026-06-02 End -->

## Runtime Configuration

| Setting | Suggested Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Data Validation Module` | API display name. |
| `APP_VERSION` | `1.0.0` | API version metadata. |
| `API_PREFIX` | `/api/v1` | Versioned route prefix. |
| `API_HOST` | `127.0.0.1` | Local host binding. |
| `API_PORT` | `8017` | Container-internal API port. |
| `DEFAULT_CURRENCY` | `PHP` | Currency assigned when M7 omitted one. |
| `MIN_RECORD_CONFIDENCE` | `0.65` | Minimum confidence before warning. |
| `DUPLICATE_MATCH_AMOUNT_TOLERANCE` | `0.01` | Duplicate amount comparison tolerance. |
| `REQUIRE_TRANSACTION_DATE` | `true` | Whether missing dates produce warnings. |
| `REQUIRE_TRANSACTION_DIRECTION` | `true` | Whether unknown direction produces warnings. |

<!-- M13 - Containerization Start -->
M13 update: `API_PORT=8017` is the container-internal Data Validation API port for official tests and runtime evidence.
<!-- M13 End -->
| `ENABLE_DUPLICATE_DETECTION` | `true` | Enables duplicate detection. |
| `MAX_RECORDS_PER_REQUEST` | `1000` | Maximum transaction candidates processed. |

Duplicate detection in M8 is intentionally request-local. It compares records in the current validation payload only and does not query the Stats database or any persistence store.

M8 has no durable file-storage responsibility. If future validation evidence or fixture locations are configured, they must use `config/stats.paths.json`, `STATS_APP_ROOT`, and the root `tests/` tree rather than module-local or machine-specific paths.

## Acceptance Criteria

- The approved spec exists before implementation grows.
- `modules/data-validation-module/` contains standalone runtime, configuration, README, and tests.
- `/health` and `/api/v1/validations` are available.
- M7-shaped extraction results can be submitted as JSON.
- Normalized records include date, description, amount, currency, direction, signed amount, source, confidence, and quality status.
- Posted/settled date is preserved when M7 supplies it, but missing posted date alone does not block save readiness.
- M7 section, entity, reference, and line-item candidates can be submitted without causing validation failures.
- Document-level financial facts retain source section context and can be returned separately from transaction records.
- Sensitive reference values are preserved only when masked/redacted or flagged for review.
- Same-batch duplicate, incomplete, invalid, and low-confidence records return explicit findings.
- Ambiguous section context, financial-field ambiguity, and total reconciliation warnings return explicit findings.
- Transaction candidates sourced from non-transaction sections are marked for review instead of being treated as clean save-ready rows.
- Evaluation metadata is present and measurable.
- Unit tests pass inside the M13 Stats runtime container through the official container runner.
- M8 remains free of Stats persistence, database duplicate checks, and dashboard logic.

## Stats Web Upload Checkpoint

Stats Web should present M8 results as a user-facing **transaction check results** checkpoint, not as raw module JSON.

The normal Upload page should show:

- Processing steps in plain language: file accepted, document uploaded, text read, transactions checked.
- A transaction summary: transactions found, ready to save, needs review, and saved count when persistence exists.
- A needs-review queue as the default result when M8 returns review items, showing only the rows or document checks that need attention.
- A concise ready-transaction table as a secondary section, not the default burden when review items exist.
- A short document summary with filename, detected document type, text-read status, and processing result.
- A collapsed extracted-data section that can be opened to review structured tables supplied by M7: document summary, statement summary, transactions, entities/references, and review findings.
- Clear next actions: edit reviewed transactions, accept reviewed transactions, save ready transactions once M9 exists, and upload another document.

The normal Upload page should not show:

- Intermediate module result cards such as `Accepted`, `Queued for processing`, raw ingestion IDs, processing file paths, or workflow names as the primary user-facing output.
- Raw M5 parse JSON.
<!-- M8 - Data Validation Module Start -->
- Raw M5/M7/M8 JSON shown as developer details only, not as the main upload result.
<!-- M8 End -->
- Internal module names as the main user-facing status.
- Parse IDs, extraction IDs, hashes, OCR engine names, confidence decimals, or source debug fields unless a developer/admin detail view is explicitly opened.

Before M9 exists, the primary save action may remain disabled or labelled as a deferred storage step. After M9/M10 exist, clicking the primary save action should send M8 normalized records to persistence, where database duplicate checks are performed.

Before M9 exists, `Save ready transactions` remains disabled even when all rows are accepted and reconciled. The Upload page should still show whether rows are ready for the future save step.

## Testing Boundary

From M13 onward, M8 official verification must run through the Stats container runtime.

| Test Type | Required Execution |
| --- | --- |
| M8 unit/API tests | Inside `stats-runtime` via `tests\scripts\regression\run_module_unit_tests.ps1` |
| Stats Web upload checkpoint verification | Against the container-exposed Stats Web entry point on `http://127.0.0.1:8080` |
| Runtime packaging checks | Through Docker build/start of `stats-runtime` |

Host-side commands are development diagnostics only and must not be recorded as M8 acceptance evidence.

<!-- M8 End -->
