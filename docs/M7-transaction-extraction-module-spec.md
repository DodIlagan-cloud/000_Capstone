<!-- M7 - Transaction Extraction Module Start -->
<!-- Specifies the transaction candidate extraction module before implementation grows. -->

# Module 7 Transaction Extraction Module Specification

## Module Summary

Module 7 establishes the reusable **Transaction Extraction Module** for the Stats project.

M7 receives parsed text and document context from the M5 Document Parsing Module, identifies transaction-like records, document-level financial fields, entities, references, line items, and section context, and returns extraction candidates with source and confidence metadata.

<!-- M7 - Robust Candidate Output Start -->
M7 must remain document-agnostic. Test fixtures must be described by document structure and extraction behavior, not by issuer, bank, merchant, provider, filename, or source institution. M7 may normalize known labels into a shared vocabulary, but it must preserve original labels and source snippets so M8, M9, and M11 can make later validation, persistence, and dashboard decisions without losing evidence.
<!-- M7 - Robust Candidate Output End -->

This module does **not** validate, clean, deduplicate, persist, or report final financial records. Those concerns belong to M8 Data Validation, M9 Stats Data and Persistence, and M11 Dashboard and Reporting.

## Architecture Alignment

M7 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M5-document-parsing-module-spec.md`
- `contracts/extraction/README.md`
- `contracts/transactions/README.md`

| Field | M7 Direction |
| --- | --- |
| Build order | `7` |
| Module | Transaction Extraction Module |
| Type | Standalone reusable module |
| Main responsibility | Extract transaction and financial field candidates from parsed document text |
| Reusable contract | Transaction extraction request/result contract |
| Owner folder | `modules/transaction-extraction-module/` |
| Stats Web role | May call M7 after M5 parsing; must not implement transaction extraction rules |

## Goals

- Provide a standalone FastAPI service for transaction candidate extraction.
- Accept M5-style parsed text, document classification, document metadata, page text, and extraction options.
- Extract transaction candidates with date, description, amount, direction, source line, page, section context, confidence, and reason codes.
- Extract document-level financial field candidates such as total amount due, minimum amount due, payment due date, statement date, transfer amount, invoice total, paid amount, owing amount, tax/GST, credit limit, balances, fees, and reference amounts.
- Extract generic entity candidates such as institution, merchant, provider, counterparty, and payment channel when present.
- Extract generic reference candidates such as invoice number, approval code, confirmation number, masked account, masked card, customer reference, and document reference when present.
- Extract line-item candidates from receipts, invoices, statements, and itemized proof documents when row structure is available.
- Extract section candidates so downstream modules can tell whether a value came from a statement summary, transaction table, receipt totals block, invoice summary, payment proof block, fees/interest block, rewards/points block, or unknown financial block.
- Return explicit findings for missing text, low-confidence extraction, unsupported document type, ambiguous amount/date, no transaction candidates, and page limit application.
- Surface M5 OCR-quality findings as input-quality warnings so poor upstream OCR is measurable without M7 rerunning Tesseract.
- Return evaluation-ready metadata for downstream testing and evidence.
- Keep runtime behavior configurable through safe defaults, ignored local overrides, and environment variables.

## Non-Goals

- OCR, direct PDF text extraction, or document classification.
- File validation, upload intake, or ingestion records.
- Cleaning or normalizing records into final ledger rows.
- Duplicate detection across records or documents.
- Persisting extraction results into the Stats database.
- Rendering dashboards or reports.
- Email retrieval.
- Cloud deployment.

## Inputs

M7 accepts a JSON extraction request.

| Input | Required | Description |
| --- | --- | --- |
| `parse_id` | No | Upstream M5 parse attempt identifier. |
| `document` | No | Source filename, hash, ingestion ID, and source context. |
| `document_type` | No | M5 top-level document classification, such as `statement`, `receipt`, `invoice`, `payment_proof`, `utility_bill`, or `unknown`. Historical `bank_statement` input is treated as a statement compatibility alias only. |
| `classification_confidence` | No | M5 classification confidence. |
| `classification` | No | Full M5 classification object. M7 may derive `document_type` and `document_subtype` from this when no top-level override is supplied. |
| `text` | Yes | Full extracted text from M5. |
| `pages` | No | Per-page text blocks from M5, including optional OCR word-block layout evidence. |
| `metadata` | No | Parse/extraction metadata from M5. |
| `quality` | No | M5 parse quality metadata, including low-text and page coverage signals. |
| `findings` | No | M5 parse findings. M7 uses these as input-quality context, not as a reason to rerun OCR. |
| `options` | No | Extraction thresholds, document type overrides, page limits, and feature switches. |

## Outputs

M7 returns a **Transaction Extraction Result**.

| Output | Description |
| --- | --- |
| `extraction_id` | Unique extraction attempt identifier. |
| `status` | `completed`, `completed_with_warnings`, `failed`, or `unsupported`. |
| `parse_id` | Upstream M5 parse identifier when supplied. |
| `document` | Source document trace metadata. |
| `transaction_candidates` | Candidate transaction rows with source/confidence metadata. |
| `financial_field_candidates` | Candidate document-level fields with source/confidence metadata. |
| `section_candidates` | Candidate document sections or financial blocks that organize source context for later interpretation. |
| `entity_candidates` | Candidate institutions, merchants, providers, counterparties, and payment channels. |
| `reference_candidates` | Candidate invoice, approval, confirmation, account, card, document, or customer references, masked/redacted where sensitive. |
| `line_item_candidates` | Candidate itemized rows from receipts, invoices, statement tables, or other financial sections. |
| `quality_metadata` | OCR/parse/extraction quality signals inherited from M5 and observed by M7. |
| `summary` | Candidate counts, amount totals, reconciliation status, and coverage metadata. |
| `document_tables` | User-facing grouped extracted-data tables for document summary, statement summary, transactions, entities/references, and findings/review items. |
| `evaluation` | Measurement fields for later evaluation and reporting. |
| `findings` | Explicit warning/error codes and messages. |

M7 does not return final validated transaction records.

<!-- M7 - Robust Candidate Output Start -->
### Source Organization

Every M7 candidate must carry enough source context to explain where it came from:

| Source Field | Description |
| --- | --- |
| `document_id` / `ingestion_id` / `parse_id` | Upstream document and parse trace identifiers when available. |
| `page_number` | Page where the candidate was found. |
| `section_id` | Stable M7-generated section identifier when the candidate is associated with a detected section. |
| `section_label` | Generic section label such as `statement_summary`, `transaction_table`, `receipt_totals`, `invoice_summary`, `payment_proof`, `line_items`, `fees_or_interest`, `rewards_or_points`, or `unknown_financial_block`. |
| `line_number` | Source line where the candidate was found when available. |
| `source_text_redacted` | Short redacted source snippet suitable for evidence and review. |
| `ocr_confidence` | Upstream OCR confidence when M5 supplies it. |
| `extraction_confidence` | M7 candidate confidence. |

The same value may have different meaning depending on section context. For example, an amount in `statement_summary` may be an obligation, an amount in `payment_proof` may be evidence of payment, and an amount in `transaction_table` may be a transaction row. M7 preserves this context; M8 interprets and validates it.

### Candidate Vocabulary

M7 should normalize recognized labels into stable field names while preserving the original label:

| Candidate Type | Examples |
| --- | --- |
| Statement summary fields | `statement_date`, `payment_due_date`, `credit_limit`, `total_amount_due`, `minimum_amount_due`, `previous_balance`, `payments`, `purchases`, `installment_due`, `finance_charges`, `late_payment_fees`, `past_due_amount`, `outstanding_balance` |
| Invoice/receipt fields | `invoice_number`, `invoice_date`, `invoice_total`, `subtotal`, `tax_amount`, `gst_amount`, `paid_amount`, `owing_amount`, `receipt_total`, `card_receipt_amount` |
| Payment proof fields | `transfer_amount`, `payment_amount`, `confirmation_number`, `approval_code`, `reference_number`, `payment_method`, `payment_channel`, `masked_source_account`, `masked_destination_account`, `masked_card` |
| Entity fields | `institution_name`, `merchant_name`, `provider_name`, `counterparty_name`, `card_type` |
| Optional metadata fields | `rewards_points`, `fees_or_interest_rate`, `foreign_exchange_note`, `document_reference` |

If M7 detects a labelled value that does not map safely to the vocabulary, it should emit the original label with a generic name such as `unknown_financial_field`, `unknown_reference`, or `unknown_entity` rather than discard it.
<!-- M7 - Robust Candidate Output End -->

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/extractions` | `POST` | Extracts transaction and financial field candidates from parsed text. |

## Extraction Strategy

M7 starts with deterministic rules so results are explainable and testable:

- Split parsed text into source lines and retain line numbers.
- Detect financial amounts with configurable currency and decimal rules.
- Detect dates in common statement, receipt, invoice, and transfer formats.
- Reconstruct transaction rows from generic statement/table structure when M5 supplies page text or line-like text:
  - Detect table headers using structural labels such as date, posted date, description/details, amount, debit, and credit.
  - Treat repeated date/date/description/amount sequences as transaction rows even when PDF text extraction places each column on separate lines.
  - Infer missing transaction years from statement-level date context when the source row has month/day text only.
  - Merge multi-line descriptions inside the same row and remove duplicated date text from the normalized candidate description.
  - Stop row reconstruction at generic non-transaction sections such as balance summary, rewards, notices, advisories, statement summaries, and payment instructions.
- Use document-type hints to prioritize generic patterns without requiring issuer-specific templates:
  - Statement-like documents, including `statement / credit_card_statement` and `statement / account_statement`: statement summary, transaction table, payment due date, balances, fees/interest, rewards/points, and references.
  - `receipt`: merchant/provider, receipt totals, tax/GST, payment method, approval/reference, card payment, and line items.
  - `invoice` and `utility_bill`: invoice summary, due date, total due, paid amount, owing amount, tax/GST, invoice/reference number, and line items.
  - `transfer_proof` or proof-like documents: payment amount, confirmation/reference, source/destination account, counterparty, payment channel, and transfer date/time.
  - `unknown`: conservative candidate extraction with lower confidence and findings when uncertain.
- Return candidates rather than final records when a line has partial but plausible transaction data.
- Avoid converting whole document headers, statement summaries, advisory text, or interest-rate disclosures into transaction rows. These should become section, field, reference, or warning candidates unless row structure supports a transaction interpretation.
- Prefer reconstructed transaction-table rows over loose line-based transaction candidates when both approaches identify the same source area.
- When M5 supplies OCR word blocks, prefer layout-aware statement extraction over flattened text extraction:
  - Group words by page and row using vertical overlap / Y-position.
  - Assign words to generic columns by observed row layout: transaction date, post date, description, amount, and credit marker.
  - Detect transaction-table boundaries from observed header geometry and keep row repair inside those boundaries.
  - Repair OCR split rows by attaching nearby orphan description text above or below a transaction row only when it belongs to the transaction-table description area.
  - Exclude side-column text such as statement summaries, payment reminders, rewards, credit-limit blocks, and advisory copy from transaction descriptions.
  - Pair split credit markers such as `CR` with the nearest transaction amount when OCR separates the marker from the number.
  - Emit repair reason codes such as `OCR_LAYOUT_REPAIRED`, `DESCRIPTION_PREFIX_REPAIRED`, `DESCRIPTION_SUFFIX_REPAIRED`, `SIDE_COLUMN_TEXT_EXCLUDED`, and `CREDIT_MARKER_REPAIRED` so Upload review can explain why a row was changed.
  - Extract issuer/provider, card product, masked card, statement period, currency, and statement summary values as data candidates, not parser-control branches.
  - Reconcile statement totals where present using `previous_balance + debits - credits = total_due`; emit reconciliation status and review findings.

Future implementation may add model-assisted extraction behind configuration, but deterministic behavior is the initial acceptance boundary. Issuer-specific templates are not part of the accepted direction for M7.

## Finding Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `MISSING_TEXT` | Error | No parsed text was supplied. |
| `UNSUPPORTED_DOCUMENT_TYPE` | Warning | The supplied document type is not configured for extraction. |
| `NO_TRANSACTION_CANDIDATES` | Warning | No transaction-like rows were found. |
| `NO_FINANCIAL_FIELDS` | Warning | No document-level financial fields were found. |
| `NO_SECTION_CONTEXT` | Warning | Values were found but could not be associated with a reliable section. |
| `LOW_CONFIDENCE_EXTRACTION` | Warning | Extracted candidates are below the configured confidence threshold. |
| `AMBIGUOUS_AMOUNT` | Warning | Multiple amounts on a source line make direction or value uncertain. |
| `AMBIGUOUS_DATE` | Warning | Date text was detected but could not be normalized confidently. |
| `NON_TRANSACTION_FINANCIAL_BLOCK` | Info | A financial-looking block was detected but intentionally not treated as a transaction row. |
| `SENSITIVE_VALUE_REDACTED` | Info | A candidate source snippet or value was masked/redacted before output. |
| `PAGE_LIMIT_APPLIED` | Warning | Only configured pages were processed. |
| `TEXT_TRUNCATED` | Warning | Input text was truncated by configured processing limits. |
| `LOW_TEXT_QUALITY_INPUT` | Warning | M5 reported low extracted text quality. |
| `UPSTREAM_NO_TEXT_EXTRACTED` | Warning | M5 reported no usable extracted text. |
| `UPSTREAM_OCR_DISABLED` | Warning | M5 reported OCR was needed but disabled. |
| `UPSTREAM_OCR_FAILURE` | Warning | M5 reported Tesseract, renderer, or OCR processing failure. |
| `UPSTREAM_OCR_QUALITY_WEAK` | Warning | M5 reported low OCR confidence or noisy OCR text. |

Repair reason codes may appear on transaction candidates when OCR layout reconstruction changes or protects a row:

| Reason Code | Meaning |
| --- | --- |
| `OCR_LAYOUT_REPAIRED` | M7 repaired a row using nearby OCR layout context. |
| `DESCRIPTION_PREFIX_REPAIRED` | M7 attached a nearby preceding description fragment inside the transaction table. |
| `DESCRIPTION_SUFFIX_REPAIRED` | M7 attached a nearby following description fragment inside the transaction table. |
| `SIDE_COLUMN_TEXT_EXCLUDED` | M7 excluded side-column or advisory text while reconstructing the row. |
| `CREDIT_MARKER_REPAIRED` | M7 paired a split `CR` marker with the transaction amount. |

## Runtime Configuration

Configuration must load from committed safe defaults, optional ignored `.env`, and environment variables.

| Setting | Suggested Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Transaction Extraction Module` | API display name. |
| `APP_VERSION` | `1.0.0` | API version metadata. |
| `API_PREFIX` | `/api/v1` | Versioned route prefix. |
| `API_HOST` | `127.0.0.1` | Local host binding. |
| `API_PORT` | `8016` | Container-internal API port. |
| `CORS_ALLOWED_ORIGINS` | Stats Web local origins | Browser caller origins. |
| `SUPPORTED_DOCUMENT_TYPES` | `statement,receipt,invoice,payment_proof,utility_bill,unknown` | Supported M5 top-level classifications. `bank_statement` is a backward-compatibility alias, not the current M5 contract. |
| `DEFAULT_CURRENCY` | `PHP` | Currency assigned when text does not identify one. |
| `MIN_TRANSACTION_CONFIDENCE` | `0.55` | Minimum candidate confidence before warning. |
| `MAX_TEXT_CHARS` | `100000` | Maximum text processed in one request. |
| `MAX_PAGE_COUNT` | `25` | Maximum page blocks processed. |

<!-- M13 - Containerization Start -->
M13 update: `API_PORT=8016` is the container-internal Transaction Extraction API port for official tests and runtime evidence.
<!-- M13 End -->
| `ENABLE_FIELD_EXTRACTION` | `true` | Enables document-level field candidate extraction. |
| `ENABLE_TRANSACTION_ROWS` | `true` | Enables row-level transaction candidate extraction. |
| `ENABLE_LINE_ITEMS` | `true` | Enables item/service row candidate extraction from receipt, invoice, and itemized financial sections. |

Hardcoded environment-dependent runtime values allowed in source: none.

## Testing

Module-local automated tests must cover:

- App import and metadata.
- `/health` and `/` endpoints.
- Runtime defaults and environment overrides.
- Missing text behavior.
- Generic statement/table transaction candidate extraction.
- Statement/table row reconstruction with two date columns, right-side amount columns, multi-line descriptions, and inferred year context.
- Receipt/proof-of-payment field extraction.
- Invoice/bill due date and total field extraction.
- Generic section detection for statement summary, transaction table, receipt totals, invoice summary, payment proof, line items, fees/interest, rewards/points, and unknown financial blocks.
- Entity, reference, and line-item candidate extraction without issuer-specific parsing or issuer-named fixtures.
- Long statement headers, advisory text, and rate disclosures not being misclassified as transaction rows.
- Unknown document handling.
- Ambiguous amount/date findings.
- M5-shaped input with `classification`, `quality`, `metadata`, `pages`, and parse `findings`.
- M5-shaped classification subtype handling, including `statement / credit_card_statement` transaction extraction.
- M5-shaped OCR word-block layout input using real `tests/input` fixtures, including the HSBC scanned credit-card statement.
- OCR layout repair for generic split statement rows, including orphan description prefixes/suffixes, side-column exclusion, and split `CR` marker repair.
<!-- Review Hardening - 2026-06-02 Start -->
- Regression coverage for stale orphan-description prefixes so a prefix from one transaction row cannot leak into the next reconstructed row.
- Regression coverage for side-column summary amounts so statement summary values cannot overwrite the transaction-table amount.
- Regression coverage for split credit-marker rows so separated `CR` markers are paired with the intended row without relying on issuer-specific labels.
<!-- Review Hardening - 2026-06-02 End -->
- Extracted table groups for Upload page display: document summary, statement summary, transactions, entities/references, and findings.
- M5 low-text/OCR findings converted into M7 input-quality findings.
- M5 OCR-quality findings, including low confidence and noisy text, converted into M7 input-quality findings.
- Evaluation metadata fields.
- Multipart-free JSON `/api/v1/extractions` endpoint.

Regression test selection:

| Condition | Regression Scope |
| --- | --- |
| M7 code/config/contract changes only | Run M7 tests inside `stats-runtime` plus affected container contract checks. |
| M5 parse result shape changes | Run M5 and M7 contract tests inside `stats-runtime`. |
| Stats Web orchestration changes | Run Stats Web orchestration/build checks inside `stats-runtime` plus affected container app-flow evidence. |
| M13 runtime changes | Run M13 containerization contract and Docker acceptance checks. |

## Acceptance Criteria

M7 is complete when:

- The approved spec exists before implementation grows.
- `modules/transaction-extraction-module/` contains standalone runtime, configuration, README, and tests.
- `/health` and `/api/v1/extractions` are available.
- M5-style parsed text can be submitted as JSON.
- M5 classification and quality fields are accepted directly without rerunning OCR.
- M5 low/no-text and OCR readiness findings are surfaced as M7 input-quality findings.
- Transaction candidates include date/description/amount/source/confidence metadata where available.
- Financial field candidates include field name/value/source/confidence metadata where available.
- Section, entity, reference, and line-item candidates are included when present and supported by source evidence.
- Extracted document tables are returned so Stats Web can display all extracted data in tabular form without owning extraction logic.
- Reconciliation metadata is returned for statement documents when enough summary fields are present.
- Every candidate preserves source organization through document/page/section/line/redacted snippet context where available.
- Original labels are preserved even when M7 also emits normalized field names.
- Sensitive identifiers are masked or redacted by default before downstream output.
- Missing/ambiguous/unsupported cases return explicit findings.
- Evaluation metadata is present and measurable.
<!-- M13 - Containerization Start -->
- Unit tests pass inside the `stats-runtime` container through `tests\scripts\regression\run_module_unit_tests.ps1`.
<!-- M13 End -->
- M7 remains free of Stats persistence, dashboard, and M8 validation logic.

## Deferred Items

- Record normalization, cleaning, duplicate checks, and validation belong to M8.
- Database persistence belongs to M9.
- Full workflow orchestration belongs to M10.
- Dashboard/reporting belongs to M11.
- Email attachment retrieval belongs to M12.
- Container and cloud deployment updates belong to M13/M14.

<!-- M7 End -->
