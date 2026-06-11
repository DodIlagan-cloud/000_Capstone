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
- Preserve and validate M7 transaction type and spending category suggestions without performing classification itself.
- Preserve recognition-label suggestion metadata from M7 so M9/Admin workflows can review possible new labels without requiring the upload user to be an administrator.
- Accept optional posted/settled date text from M7 when statement-like tables provide both transaction and post dates.
- Normalize document-level financial fields such as statement dates, due dates, totals, balances, invoice totals, paid/owing amounts, taxes, payment references, and masked account/card references where supplied by M7.
- Preserve M7 source context so every validated value can be traced back to document, page, section, line, and redacted evidence snippet.
- Use M7 section context to distinguish transaction rows from statement summaries, receipt totals, invoice summaries, payment proofs, fees/interest blocks, rewards/points blocks, and unknown financial blocks.
- Flag missing date, missing description, invalid amount, unknown direction, and low confidence.
- Flag ambiguous source context, missing section context, mismatched totals, missing references, and sensitive values that were not masked before validation.
- Detect duplicate transaction records within the supplied validation batch using deterministic date, description, amount, currency, and direction keys.
- Prepare dashboard-ready quality statuses for both transaction records and document-level financial facts.
- Prepare MVP reporting fields by preserving transaction type, transaction subtype, spending category, spending subcategory, classification confidence, category confidence, classification source, and review-required state from M7.
- Preserve pending suggestion identifiers, proposed label values, suggestion confidence, redacted evidence references, and review reason codes when M7 supplies them.
- Preserve upstream M7 extracted table groups and reconciliation status for user review. M8 may add validation status/review columns, but it must not hide non-transaction extracted data.
- Produce guided review output that prioritizes exceptions before full extracted data. M8 must create review items for repaired OCR rows, suspicious OCR text, reconciliation mismatches, duplicates, and incomplete or ambiguous records so Stats Web can show a small review queue instead of asking the user to inspect every row.
- Keep database-backed duplicate checks out of M8; M9/M10 compare normalized records against stored documents and transactions through the M9 pre-save duplicate-check endpoint before persistence.
- Return summary and evaluation metadata for module evidence.
- Support upload workflow observability by returning validation identifiers, status, review counts, and summary metadata that Stats Web can log and M9 can persist as the M8 processing-step summary.
- Keep runtime behavior configurable through safe defaults, ignored local overrides, and environment variables.
- Follow the central Stats path convention if file-based fixtures or evidence paths are added: resolve logical paths from `config/stats.paths.json` and `STATS_APP_ROOT` instead of assuming a local, container, or cloud root.

## Non-Goals

- OCR, parsing, document classification, or transaction extraction.
- Transaction type or spending category classification. M7 owns both, including optional AI-assisted fallback.
- Approving, rejecting, renaming, merging, or persisting recognition-label suggestions. M9 and the admin recognition settings workflow own durable suggestion state, JSON updates, audit, and database synchronization.
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
| Transaction classification fields | Preserve transaction type/subtype and spending category/subcategory suggestions, confidence, source, and reason codes from M7. |
| Recognition-label suggestion fields | Preserve pending suggestion IDs, proposed transaction/spending labels, suggestion source, confidence, redacted evidence references, and approval status hints from M7 without approving or mutating configuration. |

M8 should tolerate partial candidate groups. For example, a proof-of-payment image may contain no transaction table but still contain payment amount, confirmation number, counterparty, and payment channel candidates.

`document_financial_summary` is reserved for document-level facts such as statement summaries, invoice totals, receipt totals, payment proof details, tax/GST, balances, fees, and due dates. Fields sourced from `transaction_table` stay with `normalized_records` and are intentionally excluded from `document_financial_summary` so transaction rows are not double-counted as document totals.

Installment balance candidates are reviewable records, but they are not normal transactions. M8 must validate their description, amount, currency, and term/progress evidence where supplied, then surface review items when an installment candidate is incomplete, low-confidence, or ambiguous. Installment candidates must not change transaction debit/credit totals or statement reconciliation.
<!-- M8 - Robust Candidate Input End -->

## Recognition Label Validation And Suggestion Handoff

M8 is the quality gate between M7 extraction/classification and M9 persistence. It must not classify transactions itself, but it must make classification quality visible and preserve enough metadata for the admin recognition workflow.

Required behavior:

1. Preserve M7-approved label fields on each normalized transaction record:
   - `transaction_type`
   - `transaction_subtype`
   - `spending_category`
   - `spending_subcategory`
   - `classification_source`
   - `classification_review_required`
   - `classification_review_reason_codes`
2. Preserve M7 suggestion handoff fields when present:
   - `recognition_suggestion_id`
   - `recognition_suggestion_status`
   - `suggested_transaction_type`
   - `suggested_transaction_subtype`
   - `suggested_spending_category`
   - `suggested_spending_subcategory`
   - `suggestion_confidence`
   - `suggestion_reason_codes`
   - `suggestion_source`
   - `suggestion_evidence_ref`
<!-- M8 Document Suggestion Handoff Start - 2026-06-11 -->
3. Preserve M5 document-label suggestion fields at the validation-result level when present:
   - `document_recognition_suggestion_id`
   - `document_recognition_suggestion_status`
   - `suggested_document_type`
   - `suggested_document_subtype`
   - `document_suggestion_confidence`
   - `document_suggestion_reason_codes`
   - `document_suggestion_source`
   - `document_suggestion_evidence_ref`
<!-- M8 Document Suggestion Handoff End - 2026-06-11 -->
4. Validate current labels against the approved vocabulary when the vocabulary is available to M8 through configuration or request metadata.
5. Mark records for review when labels are missing, unknown, uncategorized, outside approved vocabulary, pending approval, rejected, ambiguous, or below the configured confidence threshold.
6. Allow the upload workflow to continue when a suggestion is pending. The saved record should keep the safest approved current value, such as `unknown` or `uncategorized`, while M9 stores the suggestion for later admin review.
7. Never write JSON configuration and never approve/reject suggestions. M8 only validates, flags, and passes data forward.

M8 output to M9 must make the distinction clear:

| Output Field Group | Meaning |
| --- | --- |
| Approved/current labels | The labels that may be saved on the transaction now. |
| Suggested labels | Proposed future labels requiring admin approval. |
| Review flags | Why the row needs user/admin review before reporting trust improves. |
| Evidence references | Redacted context that helps an admin decide without exposing full OCR text. |

This allows non-admin uploads to benefit from AI-assisted recognition while preserving admin governance over approved JSON and historical database synchronization.

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/validations` | `POST` | Validates and normalizes transaction candidates. |

## Processing Step Timing

M8 remains a synchronous reusable validation API. It does not write M9 timing records directly. Stats Web owns the orchestration timer around `POST /api/v1/validations`, logs the structured step event, and asks M9 to persist it as `module = M8`, `step_name = data_validation`, with safe metadata such as validation ID, validation status, normalized record count, review item count, document review status, and finding count.

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
| `SUSPICIOUS_OCR_TEXT` | Warning | A normalized description contains generic likely OCR damage such as empty text, a one-character leading token, or an OCR-substitution prefix that leaves the first word malformed. This must be treated as a review gate, not as an issuer- or merchant-specific correction, and must avoid flagging legitimate short alphanumeric merchant names such as `3M` or `4G` solely because the leading token is short. |
| `DOCUMENT_RECONCILIATION_REVIEW` | Warning | M7/M8 reconciliation indicates extracted totals do not match the document summary. |
| `UNKNOWN_TRANSACTION_TYPE` | Warning | M7 supplied no usable transaction movement type. |
| `LOW_CONFIDENCE_TRANSACTION_TYPE` | Warning | M7 transaction type confidence is below the validation threshold. |
| `AMBIGUOUS_TRANSACTION_TYPE` | Warning | M7 transaction type status or scores require review. |
| `UNKNOWN_SPENDING_CATEGORY` | Warning | M7 supplied no usable MVP reporting category. |
| `LOW_CONFIDENCE_SPENDING_CATEGORY` | Warning | M7 spending category confidence is below the validation threshold. |
| `AMBIGUOUS_SPENDING_CATEGORY` | Warning | M7 spending category status or scores require review. |
| `PENDING_RECOGNITION_LABEL_SUGGESTION` | Warning | M7 supplied a proposed transaction or spending label that has not been approved by an administrator. |
| `UNAPPROVED_RECOGNITION_LABEL` | Warning | A transaction or spending label is outside the approved vocabulary known to M8. |
| `REJECTED_RECOGNITION_LABEL_SUGGESTION` | Warning | A supplied label suggestion was already rejected or marked unusable upstream. |

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
- `Edit` allows the user to correct transaction type, transaction subtype, spending category, and spending subcategory using approved dropdown values. User edits in the upload session are current-row corrections, not approval of new global labels.
- `Accept` confirms that a reviewed transaction row should join the ready-to-save set for the current upload session.
- A high-confidence or `Ready` row must still remain editable because OCR can miss or alter digits even when the row passes M8 validation rules.
- The transaction-row `Edit` action must remain visible wherever transaction rows are shown. Hiding an already-reserved action column behind hover does not add user value in this checkpoint.
- Transaction rows must not offer an `Exclude` action in this iteration because every extracted transaction should either be corrected or accepted before the future database write.
- Accepting rows does not persist anything. M9/M10 own database writes and the pre-save database-backed duplicate check.
- Statement-like documents must keep save readiness gated by reconciliation. After each edit or accept, the Upload page recalculates document totals using the supplied M7/M8 reconciliation facts. When M7 has separated statement payments into document-level `payments_and_credits`, the Upload page must use the statement-level credit total only when it is explicitly present in the M7 reconciliation payload; an explicit zero credit total must not be replaced by the sum of normalized credit rows. Transactions are not final ready-to-save while the calculated total differs from the document total outside tolerance.
- Non-transaction extracted data tables such as statement summary, document summary, entities/references, line items, and findings must be hidden behind a user-controlled toggle by default. The review queue and transaction readiness state remain the primary visible checkpoint.
<!-- M8 Review UX - 2026-06-02 End -->

<!-- Fixture Robustness - 2026-06-02 Start -->
Stats Web must provide a standard Upload checkpoint across supported document types. The normal user view should show one normalized transaction/review surface from M8. Raw M7 `transactions` extracted-data tables must not be repeated in the normal extracted-data toggle because they duplicate M8 normalized transaction rows; raw transaction candidates may remain in developer details for troubleshooting. Supporting non-transaction tables such as document summary, statement summary, entities/references, line items, findings, and reconciliation details may remain available behind the toggle.

For cloud-dev and later production-style runtime, Stats Web must not hold a single browser request open while waiting for M5/M7/M8 to finish. Long-running OCR/parsing workflows should be started as an M9-tracked processing job, then polled by the Upload page until the final M8 validation payload is ready. M8 remains a synchronous validation API internally; the async behavior belongs to the Upload/M9 orchestration boundary.
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
- Normalized records preserve M7 transaction type, transaction subtype, spending category, spending subcategory, classification source, confidence, and category confidence.
- Normalized records preserve M7 pending recognition-label suggestion metadata when supplied, while keeping approved/current labels separate from proposed labels.
- Posted/settled date is preserved when M7 supplies it, but missing posted date alone does not block save readiness.
- M7 section, entity, reference, and line-item candidates can be submitted without causing validation failures.
- Document-level financial facts retain source section context and can be returned separately from transaction records.
- Sensitive reference values are preserved only when masked/redacted or flagged for review.
- Same-batch duplicate, incomplete, invalid, and low-confidence records return explicit findings.
- Ambiguous section context, financial-field ambiguity, and total reconciliation warnings return explicit findings.
- Transaction candidates sourced from non-transaction sections are marked for review instead of being treated as clean save-ready rows.
- Unknown, ambiguous, or low-confidence transaction type and spending category suggestions are marked for review instead of being silently treated as clean MVP reporting categories.
- Pending, rejected, or outside-vocabulary recognition-label suggestions are marked for review and passed through to M9 for admin governance.
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

Before M9 exists, the primary save action may remain disabled or labelled as a deferred storage step. After M9/M10 exist, clicking the primary save action should first send M8 normalized records to the M9 duplicate-check endpoint. Only after duplicate results are reviewed should the accepted payload be sent to the M9 save endpoint.

Before M9 exists, `Save ready transactions` remains disabled even when all rows are accepted and reconciled. The Upload page should still show whether rows are ready for the future save step.

## Testing Boundary

From M13 onward, M8 official verification must run through the Stats container runtime.

| Test Type | Required Execution |
| --- | --- |
| M8 unit/API tests | Inside `stats-runtime` via `tests\scripts\regression\run_module_unit_tests.ps1` |
| Stats Web upload checkpoint verification | Against the container-exposed Stats Web entry point on `http://127.0.0.1:8080` |
| Runtime packaging checks | Through Docker build/start of `stats-runtime` |

Host-side commands are development diagnostics only and must not be recorded as M8 acceptance evidence.

M8 tests should include:

- Approved transaction/spending labels pass through without suggestion review.
- Unknown or uncategorized labels create review items.
- Pending suggestion metadata is preserved separately from approved/current labels.
- Outside-vocabulary labels produce `UNAPPROVED_RECOGNITION_LABEL`.
- Pending suggestions produce `PENDING_RECOGNITION_LABEL_SUGGESTION`.
- M8 does not mutate JSON configuration or mark suggestions approved.
- M9 save payloads include both current labels and suggestion metadata when present.

<!-- M8 Test Flow Update - 2026-06-12 Start -->
## Acceptance Test Flow Definition

The current M8 acceptance test flow is defined in:

```text
tests/scripts/M8-DataValidation/M8-DataValidation-test-flow.md
```

That file is a planning and reviewer checklist only. Updating it does not mean the flow has been executed.

All M8 acceptance evidence must be captured through an actual run of the Stats app using the normal browser workflow a user would follow. API, database, and terminal outputs are supporting evidence only; they may explain the result or document a blocker, but they must not be presented as a completed M8 user-flow pass on their own.

The M8 flow must prove the full visible checkpoint from Upload through validation review before M9 persistence:

- container runtime and `/health`
- Login and authenticated `/Upload`
- real `tests/input` transaction-bearing fixture
- M5 parse/OCR and M7 extraction handoff reaching M8
- M8 normalized transaction rows with date, posted date when supplied, description, amount, currency, direction, signed amount behavior, status, findings, and review items
- review edit/accept behavior where supported by the UI
- duplicate proof through the app's M9 pre-save flow when save is in scope, with M8 same-batch API output used only as supporting evidence or a documented blocker
- `Save ready transactions` success, duplicate block, or precise not-ready message
- `/Documents` and `/Reports` outcome only when saved records are expected
- cleanup status for uploaded documents, saved records, processing jobs, blobs, and temporary files

Official results still require an explicit evidence run through `stats-runtime`; host-only diagnostics do not satisfy M8 acceptance.
<!-- M8 Test Flow Update - 2026-06-12 End -->

<!-- M8 End -->
