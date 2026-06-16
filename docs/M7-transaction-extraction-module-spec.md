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
- Own transaction classification behavior for extracted transaction candidates, including transaction type, transaction subtype, spending category, spending subcategory, confidence, reason codes, source, and review triggers.
- Use the same classification architecture as M5 with an added Stats learning layer: M9-approved learned merchant profiles first when safe, M9-approved vocabulary/rules next, optional AI-assisted classification fallback when deterministic signals are weak, ambiguous, or unknown, and no dashboard-side classification logic.
- Return explicit findings for missing text, low-confidence extraction, unsupported document type, ambiguous amount/date, no transaction candidates, and page limit application.
- Surface M5 OCR-quality findings as input-quality warnings so poor upstream OCR is measurable without M7 rerunning Tesseract.
- Return evaluation-ready metadata for downstream testing and evidence.
- Support upload workflow observability by returning safe extraction identifiers, status, counts, reconciliation status, and finding metadata that Stats Web can log and M9 can persist as the M7 processing-step summary.
- Keep runtime behavior configurable through safe defaults, ignored local overrides, and environment variables.

## Non-Goals

- OCR, direct PDF text extraction, or document classification.
- File validation, upload intake, or ingestion records.
- Cleaning or normalizing records into final ledger rows.
- Duplicate detection across records or documents.
- Persisting extraction results into the Stats database.
- Rendering dashboards or reports.
- Reporting classification metrics; M11 owns reporting over persisted classification outcomes.
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
| `installment_candidates` | Candidate credit-card installment purchase/balance rows that are reviewable like transactions but kept separate from current billing transaction candidates. |
| `quality_metadata` | OCR/parse/extraction quality signals inherited from M5 and observed by M7. |
| `summary` | Candidate counts, amount totals, reconciliation status, and coverage metadata. |
| `document_tables` | User-facing grouped extracted-data tables for document summary, statement summary, transactions, entities/references, and findings/review items. |
| `evaluation` | Measurement fields for later evaluation and reporting. |
| `findings` | Explicit warning/error codes and messages. |

M7 does not return final validated transaction records.

M7 owns transaction type and spending category classification behavior. Stats Web `/Admin/Classifications` may show and manage approved transaction/spending label configuration through controlled backend handlers, but it must not implement M7 extraction/classification rules or mutate configuration directly from the browser. M9 is the source of truth for approved labels, rules, pending suggestions, audit history, and synchronization state.

<!-- M7 Recognition Settings DB Source Start - 2026-06-10 -->
<!-- M7 - Transaction Classification Start -->
## Transaction Type And Spending Category Classification

M7 must classify extracted transaction candidates using the same layered pattern as M5 document classification, extended with M9 learned merchant classifications:

1. Load active approved vocabulary from M9 recognition settings.
2. Load active approved deterministic rules from M9 recognition settings.
3. Normalize the merchant/counterparty description and query M9 for an exact learned merchant classification profile.
4. If M9 returns a non-conflicted learned profile whose subtype/subcategory values map to active parent-child vocabulary and fit the candidate direction/document context, apply it as the classification result and do not call AI.
5. If no safe learned profile applies, score generic signals from candidate description, amount, direction, document type/subtype, section context, entity/reference candidates, payment method, source text, and reason codes.
6. Return a structured classification result with label, subtype, confidence, status, reason codes, and diagnostic scores.
7. When deterministic rules are weak, ambiguous, or unknown, optionally call an AI-assisted classifier behind configuration.
8. Merge rule-based and AI-assisted results conservatively, preserving classification source, model/provider metadata where safe, confidence, and review triggers.

M7 must keep **transaction type** separate from **spending category**:

| Classification | Meaning | Examples |
| --- | --- | --- |
| `transaction_type` | Financial movement mechanics: what happened to money | `purchase`, `payment`, `transfer`, `refund`, `fee`, `interest`, `cash_advance`, `installment_amortization`, `adjustment`, `tax`, `unknown` |
| `transaction_subtype` | More specific mechanics | `eftpos_payment`, `card_purchase`, `bank_transfer`, `credit_card_payment`, `invoice_payment`, `finance_charge`, `late_payment_fee`, `statement_credit`, `reversal`, `unknown` |
| `spending_category` | Reporting bucket: what the spend/payment is for | `medical`, `pharmacy`, `groceries`, `utilities`, `transport`, `housing`, `insurance`, `banking_fees`, `interest`, `transfers`, `shopping`, `food_dining`, `income`, `tax`, `uncategorized` |
| `spending_subcategory` | Optional finer reporting bucket | `lab_tests`, `prescriptions`, `public_transport`, `electricity`, `card_repayment`, `unknown` |

### Controlled Classification Choices

MVP review must use child-first controlled choices so users make fewer, more consistent classification decisions:

1. `transaction_subtype` is the only visible movement-classification dropdown in the Upload transaction review flow. M7 still returns `transaction_type`, but it must be derived from the selected or suggested subtype through the active M9 parent-child mapping.
2. `spending_subcategory` is the only visible spending-classification dropdown in the Upload transaction review flow. M7 still returns `spending_category`, but it must be derived from the selected or suggested subcategory through the active M9 parent-child mapping.
3. Parent fields remain required in M7/M8/M9 payloads because M11 reporting groups by parent category/type. They are system-derived fields, not separately chosen user fields in the normal review UI.
4. When deterministic rules or AI can identify only a parent but no reliable child, M7 must return the configured `unknown` child under that parent when available, lower confidence, and mark the row for review.
5. When deterministic rules or AI propose a new child value outside active M9 vocabulary, M7 must preserve the proposed child value, include the proposed or inferred parent, and mark the row for Upload review/save confirmation. The parent must also be reviewed if no active parent can be inferred safely.
6. AI prompts must prefer active subtype/subcategory choices and treat parent type/category as derived context. AI may return parent fields for explanation, but M7 must verify or recompute them from the child mapping before handing candidates to M8.

Suggested candidate-level fields:

| Field | Purpose |
| --- | --- |
| `transaction_type` | Derived parent financial movement type for reporting and persistence. |
| `transaction_subtype` | Primary controlled movement choice selected by rules, AI, or user review. |
| `transaction_type_confidence` | Confidence for movement classification. |
| `transaction_type_status` | `classified`, `ambiguous`, `unknown`, or `unsupported`. |
| `transaction_type_reason_codes` | Rule/AI reason codes. |
| `transaction_type_scores` | Diagnostic scores by type/subtype. |
| `spending_category` | Derived parent MVP reporting category for reporting and persistence. |
| `spending_subcategory` | Primary controlled spending choice selected by rules, AI, or user review. |
| `spending_category_confidence` | Confidence for spending-category classification. |
| `spending_category_status` | `classified`, `ambiguous`, `unknown`, or `unsupported`. |
| `spending_category_reason_codes` | Rule/AI reason codes. |
| `spending_category_scores` | Diagnostic scores by category/subcategory. |
| `classification_source` | `prior_merchant_human_confirmed`, `rules`, `ai`, `rules_ai_merged`, `user_override`, or `unknown`. |

Historical shared config files may exist from the earlier implementation pattern:

```text
config/transaction-classification.vocabulary.json
config/transaction-classification.rules.json
config/spending-category.vocabulary.json
config/spending-category.rules.json
```

Those files are deprecated for runtime use. They may be retained temporarily as migration seed/reference material, but M7 must not silently fall back to them inside the container or cloud image. If the M9 recognition settings API is unavailable and no in-memory M9 settings cache from a successful prior load exists, M7 must fail classification clearly with a controlled finding such as `RECOGNITION_SETTINGS_UNAVAILABLE`, keep extraction candidates and source evidence intact, and mark transaction type or spending category as `unknown` / `uncategorized` for review. If a successful prior M9 settings cache exists, M7 must use that stale in-memory cache during the temporary outage rather than flooding review queues with avoidable unknown classifications.

AI assistance must be optional and environment-driven. It must not send raw unredacted OCR text, account/card/customer/patient identifiers, full document text, connection strings, or secrets. The AI request should use the smallest redacted candidate context needed: candidate description, redacted source snippet, document type/subtype, section label, direction, amount band or amount when required, entity/reference types, and existing rule scores. AI prompt size limiting must preserve valid JSON by trimming large source fields before serialization rather than slicing an already-serialized JSON payload.

M7 remains the owner of these classification suggestions. M8 validates and flags them, M9 persists them or activates human-confirmed labels after save, and M11 reports over persisted outcomes.

### Learned Merchant Classification Reuse

M7 must use M9 learned merchant profiles to reduce repeat review and AI cost after a user has already confirmed a merchant classification.

Required behavior:

1. M7 computes or requests a normalized merchant key from the candidate description and optional merchant/counterparty entity evidence.
2. M7 calls the M9 internal learned merchant lookup before AI-assisted classification.
3. M7 applies a learned profile only when all of these are true:
   - the match type is exact normalized merchant match;
   - the profile was created from human-confirmed saved transactions;
   - the profile is active and not conflicted;
   - `transaction_subtype` and `spending_subcategory` are present and not `unknown`;
   - the child values map to active M9 parent values;
   - the profile is compatible with the candidate direction, document type/subtype, and row context.
4. A safe learned match must set:
   - `classification_source = prior_merchant_human_confirmed`
   - `classification_review_required = false`
   - `recognition_suggestion_status = none`
   - `classification_vocabulary_status = active_vocabulary_match`
   - reason code `PRIOR_MERCHANT_CLASSIFICATION_REUSED`
5. A safe learned match must not call AI and must not create an admin pending suggestion.
6. If M9 returns a conflicted or inactive learned profile, M7 must not silently apply it. The candidate remains review-required with controlled reason codes such as:
   - `PRIOR_MERCHANT_CLASSIFICATION_CONFLICT`
   - `PRIOR_MERCHANT_CLASSIFICATION_INACTIVE`
   - `PRIOR_MERCHANT_CLASSIFICATION_PARENT_CHILD_MISMATCH`

MVP merchant matching is exact normalized matching only. Fuzzy merchant matching is deferred and must later use a distinct source such as `prior_merchant_fuzzy_human_confirmed`, a high similarity threshold, ambiguity detection, and review gating for unsafe matches.

### Recognition Label Lifecycle

Transaction and spending labels use approved configuration plus two human-confirmation paths:

1. M7 classifies each candidate with approved transaction and spending vocabulary/rules first.
2. If deterministic rules and optional AI assistance detect a plausible new label outside the current active vocabulary, M7 marks the candidate for review and preserves the proposed transaction type, transaction subtype, spending category, and spending subcategory as the active candidate values for the upload review flow.
3. The Upload transaction review/accept/save flow is a human-confirmation path. If the user reviews and accepts the transaction before saving, the saved transaction keeps the accepted AI-suggested classification, the classification is marked human-confirmed, and M9 adds the new label or subtype to active recognition vocabulary as part of the save workflow.
4. This transaction-review confirmation path bypasses the separate `/Admin/Classifications` pending-suggestion approval path for that reviewed transaction. No separate administrator approval is required when the user has reviewed and accepted the transaction before saving.
5. The admin pending-suggestions workflow remains available for post-MVP email ingestion, automated workflows, background suggestions, batch governance, cleanup, merge/rename decisions, or suggestions that should not be activated by a single user save.
6. If deterministic rule evidence points to a label/subtype that is not currently active in M9, M7 must keep source evidence and may emit a pending non-AI suggestion for admin governance unless the user explicitly edits/accepts the classification in the upload review flow.
7. Recognition approval and save failures must show a user-actionable reason. The UI must distinguish stale admin review items, save-time vocabulary activation failures, and general save failures without showing raw HTTP status text, raw API JSON, stack traces, or secret-bearing diagnostics.
8. Administrators may still approve, edit then approve, reject, rename, or merge suggestions that were not completed through the upload transaction-review save path.
9. Approved admin changes and user-confirmed save-time vocabulary activations both update active M9 recognition settings through controlled audited database operations.
10. When an admin edit renames, merges, or applies a label, M9 must synchronize affected persisted transaction records according to the admin's selected policy. Save-time user confirmation applies only to the transactions included in that save and to activation of the accepted new labels/subtypes.

AI may propose labels and rules while running, but AI must not silently become the final authority. Either upload transaction review/save or admin governance must provide the human confirmation before new active database settings or persisted reporting rows rely on a new label.

Admin review and evidence failures must be plain-language. If a transaction or spending recognition suggestion can no longer be approved because it was already reviewed, removed, or created by a stale test run, Stats Web must show a message such as `This review item is no longer available. Refresh the items to review and try again.` It must not show raw HTTP status text, raw API JSON, stack traces, or secret-bearing diagnostics to the user.
<!-- M7 - Transaction Classification End -->
<!-- M7 Recognition Settings DB Source End - 2026-06-10 -->

<!-- M7 AI Suggestion Governance Start - 2026-06-11 -->
### AI Suggestion Governance Handoff

When AI-assisted transaction or spending classification proposes a label or subtype that is not currently present in M9 active recognition settings, M7 must keep the proposed value on the transaction candidate for the Upload review flow and mark the row as review-required. The proposed value is not yet globally approved, but it is the candidate value the user can inspect, edit, accept, and save. M7 should include review/confirmation metadata so M8, Stats Web, and M9 can distinguish user-confirmable AI suggestions from already-active vocabulary:

- `recognition_suggestion_id`
- `suggested_transaction_type`
- `suggested_transaction_subtype`
- `suggested_spending_category`
- `suggested_spending_subcategory`
- `suggestion_confidence`
- `suggestion_reason_codes`
- `suggestion_source`
- `suggestion_evidence_ref`
- `classification_review_required = true`
- `classification_confirmation_mode = transaction_review_save`
- `classification_human_confirmed = false`

M7 may still use an approved AI-assisted value immediately when the AI result maps to active M9 vocabulary. Proposed labels outside active settings must be confirmed by the manual Upload transaction review/save path before they become persisted reporting labels or active vocabulary in the MVP flow. If the transaction comes from post-MVP email ingestion, automated workflow, or another path where no user reviews it before save, the suggestion remains eligible for the admin pending-suggestion workflow.
<!-- M7 AI Suggestion Governance End - 2026-06-11 -->

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
| Statement summary fields | `statement_date`, `payment_due_date`, `credit_limit`, `total_amount_due`, `minimum_amount_due`, `previous_balance`, `payments`, `payments_and_credits`, `purchases`, `installment_due`, `finance_charges`, `late_payment_fees`, `past_due_amount`, `outstanding_balance` |
| Invoice/receipt fields | `invoice_number`, `invoice_date`, `invoice_total`, `subtotal`, `tax_amount`, `gst_amount`, `paid_amount`, `owing_amount`, `receipt_total`, `card_receipt_amount` |
| Payment proof fields | `transfer_amount`, `payment_amount`, `confirmation_number`, `approval_code`, `reference_number`, `payment_method`, `payment_channel`, `masked_source_account`, `masked_destination_account`, `masked_card` |
| Entity fields | `institution_name`, `merchant_name`, `provider_name`, `counterparty_name`, `card_type` |
| Optional metadata fields | `rewards_points`, `fees_or_interest_rate`, `foreign_exchange_note`, `document_reference` |

If M7 detects a labelled value that does not map safely to the vocabulary, it should emit the original label with a generic name such as `unknown_financial_field`, `unknown_reference`, or `unknown_entity` rather than discard it.

### Credit-Card Payments And Installments

Credit-card statement payment rows and installment balances must preserve financial meaning without inflating current transaction totals:

- Statement payment credit rows such as `Payment - Thank You`, `Paid thru`, or similar negative payment rows are document-level payment/credit evidence. M7 must emit them as financial field candidates, not normal transaction candidates.
- If OCR flattens a statement payment row so it cannot be reconstructed as a transaction row, M7 should still emit a `payments_and_credits` financial field when the payment/paid label, amount, and credit marker are present in the source text.
- When a labelled statement-summary `payments_and_credits` total and row-derived payment evidence are both present, reconciliation must prefer the labelled statement-summary total because it can include cashback, reversals, and other credit rows in addition to payments.
- Installment purchase/principal rows are installment balance candidates. They are reviewable extracted data and future persistence inputs, but they are not current transaction candidates for reconciliation.
- Installment amortization rows remain current transaction candidates because they affect the current statement amount due. When possible, M7 should keep enough description and term evidence for a future link to the related installment candidate.
- M7 reconciliation must use statement-summary payment and purchase fields when available, and must not depend on statement payment rows being included as transaction candidates.
<!-- M7 - Robust Candidate Output End -->

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/extractions` | `POST` | Extracts transaction and financial field candidates from parsed text. |

## Processing Step Timing

M7 remains a synchronous reusable extraction API. It does not persist timing rows itself. Stats Web owns the orchestration timer around `POST /api/v1/extractions`, logs the structured step event, and asks M9 to persist it as `module = M7`, `step_name = transaction_extraction`, with safe metadata such as extraction ID, candidate counts, field counts, status, reconciliation status, and finding count.

## Extraction Strategy

M7 starts with deterministic rules so results are explainable and testable:

- Split parsed text into source lines and retain line numbers.
- Detect financial amounts with configurable currency and decimal rules.
- For statement transaction rows that contain both an original foreign-currency amount and a billing-currency amount, use the billing-currency amount as the transaction candidate amount because it is the value that reconciles to the statement totals. Preserve source text and reason codes so the original amount remains reviewable evidence.
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
  - `unknown`: conservative candidate extraction with lower confidence and findings when uncertain. If OCR text is receipt-like because it has a retail/tax invoice header plus total, GST/tax, EFTPOS/card, purchase, approved, or terminal evidence, M7 should still derive reviewable receipt totals and a debit transaction candidate rather than returning no transaction candidates solely because M5 classification was ambiguous.
- Receipt/invoice total-derived transactions should carry the best available document-level transaction date. When the selected amount source line has no date, M7 should scan nearby receipt OCR text for generic labels such as `Date`, `Issued`, `Printed`, and terminal timestamps. If OCR splits a receipt date into a day/month token and a nearby terminal month/year token, M7 may combine those generic date fragments into a reviewable date candidate rather than leaving the transaction date blank. Labelled date matching must stay local to the label so noisy later IDs or unrelated ISO-looking fragments do not override better terminal timestamp evidence.
- Receipt OCR amount parsing should tolerate common thermal-printer and Tesseract damage around payment-method labels, such as currency symbols read as punctuation, `Bank Card` read as `flank Card`, or spacing between currency and amount tokens. These repairs must stay generic, preserve source text, and return reviewable candidates rather than silently correcting merchant-specific layouts.
- Receipt OCR amount parsing should also tolerate labels and amounts split across nearby lines, such as `TOTAL:` followed by an amount line, `TOTAL: $34 33`, or `EFTPOS:` followed by an amount line. This repair must be a fallback after stronger purchase/card/payment-method evidence, must prefer final-total labels over item-like `sale` amounts when they conflict, and must avoid tax/GST-only labels.
- Receipt total extraction must not treat GST/tax-only lines as the transaction amount when subtotal, total, sale, purchase, card, EFTPOS, or due amount evidence is also available. Tax/GST values should remain document-level tax fields and should not drive the derived debit transaction.
- Receipt-derived transaction descriptions should prefer generic sale, service, product, fare, top-up, reload, payment, merchant, store, or station/location labels over terminal/reference prefixes. Terminal metadata such as RRN, authorisation, reference, card, EFTPOS, approval, and customer-copy text should remain source evidence but should not become the primary transaction description when a clearer sale/service description is present.
<!-- M7 Statement Fallback Guard Start - 2026-06-15 -->
- M7 must treat M5 `document_type` and `document_subtype` as the primary routing hint, but it must still inspect extracted text, financial fields, sections, and OCR word-block layout for strong statement-shape evidence before running receipt/invoice total-derived transaction fallback.
- Strong statement-shape evidence includes generic labels or normalized field names such as `statement date`, `payment due date`, `credit limit`, `previous balance`, `payments and credits`, `purchases and debits`, `total account balance`, `total amount due`, and `minimum amount due`.
- When statement-shape evidence is present, M7 must suppress receipt-style total-derived single-transaction fallback. It should attempt statement/table extraction first, then return explicit statement-needs-review or no-candidate findings if rows cannot be reconstructed. It must not create a bogus receipt transaction from a statement summary total.
- Amount parsing must be defensive for malformed OCR tokens, including values with multiple decimal separators such as `3.225.00`. Malformed tokens should be skipped, split/repair attempted only when structurally safe, or reported as ambiguous with a finding. They must not raise an unhandled exception or turn the extraction request into a 500 response.
<!-- M7 Statement Fallback Guard End - 2026-06-15 -->
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
  - Prefer the billing-currency amount column over an original foreign-currency amount token when both appear on a statement transaction row.
  - Emit repair reason codes such as `OCR_LAYOUT_REPAIRED`, `DESCRIPTION_PREFIX_REPAIRED`, `DESCRIPTION_SUFFIX_REPAIRED`, `SIDE_COLUMN_TEXT_EXCLUDED`, and `CREDIT_MARKER_REPAIRED` so Upload review can explain why a row was changed.
  - Extract issuer/provider, card product, masked card, statement period, currency, and statement summary values as data candidates, not parser-control branches.
  - Reconcile statement totals where present using `previous_balance + debits - credits = total_due`; emit reconciliation status and review findings.
<!-- M7 Scanned Statement Layout Extraction Start - 2026-06-15 -->
- For scanned/image-backed statement PDFs where M5 supplies OCR word blocks, M7 must attempt a layout-region extraction pass before flattened text and loose statement-row fallbacks.
- The layout-region pass must detect generic statement-page regions from geometry and labels, not issuer names:
  - A transaction-table region with headers such as `post date`, `tran date`, `transaction date`, `description`, and `amount`.
  - A right-side or side-panel summary region with labels such as `account summary`, `payment summary`, `rewards summary`, `credit limit`, `available credit`, `payment due date`, and `minimum payment`.
  - A lower detachable payment slip or remittance region that repeats due-date and amount values but is not a transaction table.
- When these regions are detected, M7 must reconstruct transaction rows only from the transaction-table region. It must exclude side-panel summary values, rewards/points text, advisory paragraphs, and detachable payment-slip values from transaction candidates.
- Column inference must come from observed x-position bands inside the transaction table: post date, transaction date, description, amount, and nearby credit marker. Row grouping must use y-position/vertical overlap and may merge continuation description lines only when they remain inside the transaction-table description band.
- The layout-region pass must preserve the previous hardening behavior as fallbacks. If region detection fails or a row cannot be reconstructed safely, existing flattened statement parsing, split-row repair, side-column exclusion, split `CR` repair, malformed amount handling, and receipt-fallback suppression still apply.
- This feature must remain institution-agnostic. HSBC-style scanned statements are regression examples, but code branches and tests must refer to layout structure, generic labels, and table geometry rather than issuer or filename.
<!-- M7 Scanned Statement Layout Extraction End - 2026-06-15 -->

Future implementation may add model-assisted extraction behind configuration, but deterministic behavior is the initial acceptance boundary. Issuer-specific templates are not part of the accepted direction for M7.

Transaction type and spending category classification follow M5's classification direction: deterministic vocabulary/rules are the primary path; AI-assisted classification is a configured fallback for weak, ambiguous, or unknown cases. AI assistance must improve coverage without replacing traceable rule outputs or hiding review-needed classifications.

Before M7 sends any transaction or spending candidate to an AI-assisted classifier, it must load the current active recognition context from M9 and include only that bounded context in the prompt: approved transaction subtype-to-type mappings, approved spending subcategory-to-category mappings, enabled aliases/rules, deprecation or merge hints, the deterministic rule result, and minimal redacted transaction evidence. The AI prompt must prefer existing active subtype/subcategory choices whenever they fit and may propose a new transaction/spending child label only when the candidate cannot be safely mapped to the active vocabulary. The response must state whether each suggested value matched active vocabulary or is a proposed new value that requires review/confirmation. Parent type/category values returned by AI are advisory and must be verified or recomputed from the accepted child mapping.

## Finding Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `MISSING_TEXT` | Error | No parsed text was supplied. |
| `UNSUPPORTED_DOCUMENT_TYPE` | Warning | The supplied document type is not configured for extraction. |
| `NO_TRANSACTION_CANDIDATES` | Warning | No transaction-like rows were found. |
| `NO_FINANCIAL_FIELDS` | Warning | No document-level financial fields were found. |
| `NO_SECTION_CONTEXT` | Warning | Values were found but could not be associated with a reliable section. |
| `LOW_CONFIDENCE_EXTRACTION` | Warning | Extracted candidates are below the configured confidence threshold. |
| `LOW_CONFIDENCE_AMOUNT_TOKEN` | Warning | OCR supplied a transaction amount token below the configured confidence threshold; M7 must preserve that token confidence for M8 review gating. |
| `OCR_RECEIPT_TOTAL_FALLBACK` | Info/Reason code | Receipt-like or invoice-like OCR produced usable totals but no explicit transaction row; M7 derived a reviewable debit transaction from a receipt purchase/total amount or a computed invoice line-item total. |
<!-- M7 Statement Fallback Guard Start - 2026-06-15 -->
| `STATEMENT_SHAPE_RECEIPT_FALLBACK_SUPPRESSED` | Warning/Reason code | Statement-like labels, fields, sections, or layout evidence were present, so M7 suppressed receipt-style total fallback and required statement extraction or review instead. |
| `MALFORMED_AMOUNT_TOKEN` | Warning | OCR or source text produced an amount-like token that could not be safely parsed, such as multiple decimal separators. |
<!-- M7 Statement Fallback Guard End - 2026-06-15 -->
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
| `UNKNOWN_TRANSACTION_TYPE` | Warning | M7 could not classify the transaction movement type with enough confidence. |
| `LOW_CONFIDENCE_TRANSACTION_TYPE` | Warning | Transaction type confidence is below the configured threshold. |
| `AMBIGUOUS_TRANSACTION_TYPE` | Warning | Multiple transaction type rules or AI/rule outputs are close enough to require review. |
| `UNKNOWN_SPENDING_CATEGORY` | Warning | M7 could not assign an MVP reporting category with enough confidence. |
| `LOW_CONFIDENCE_SPENDING_CATEGORY` | Warning | Spending category confidence is below the configured threshold. |
| `AMBIGUOUS_SPENDING_CATEGORY` | Warning | Multiple spending categories are close enough to require review. |
| `AI_TRANSACTION_CLASSIFICATION_USED` | Info | Optional AI-assisted transaction classification contributed to the result. |
| `PRIOR_MERCHANT_CLASSIFICATION_REUSED` | Info/Reason code | M7 reused an exact learned merchant profile created from a prior human-confirmed saved transaction. |
| `PRIOR_MERCHANT_CLASSIFICATION_CONFLICT` | Warning | M9 found conflicting human-confirmed classifications for the normalized merchant, so the row requires review. |
| `PRIOR_MERCHANT_CLASSIFICATION_INACTIVE` | Warning | M9 found a learned merchant profile that is inactive or points to inactive recognition labels. |
| `PRIOR_MERCHANT_CLASSIFICATION_PARENT_CHILD_MISMATCH` | Warning | A learned profile's subtype or subcategory no longer maps cleanly to active parent vocabulary. |

Repair reason codes may appear on transaction candidates when OCR layout reconstruction changes or protects a row:

| Reason Code | Meaning |
| --- | --- |
| `OCR_LAYOUT_REPAIRED` | M7 repaired a row using nearby OCR layout context. |
<!-- M7 Scanned Statement Layout Extraction Start - 2026-06-15 -->
| `OCR_STATEMENT_REGION_DETECTED` | M7 detected transaction-table, side-summary, and/or payment-slip regions from OCR word-block geometry. |
| `OCR_STATEMENT_REGION_EXCLUDED` | M7 excluded side-summary, advisory, rewards, credit-limit, or payment-slip text from transaction row reconstruction. |
<!-- M7 Scanned Statement Layout Extraction End - 2026-06-15 -->
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
| `ENABLE_TRANSACTION_CLASSIFICATION` | `true` | Enables transaction type and spending category classification on extracted transaction candidates. |
| `RECOGNITION_SETTINGS_URL` | M9 recognition settings API URL | Source of approved transaction/spending vocabulary/rules and pending-suggestion write boundary. |
| `RECOGNITION_SETTINGS_CACHE_SECONDS` | `300` | Short cache for approved settings so one extraction request does not repeatedly call M9. |
| `TRANSACTION_CLASSIFICATION_VOCABULARY_PATH` | deprecated | Historical local JSON path. Must not be used as runtime fallback after M9 recognition settings are enabled. |
| `TRANSACTION_CLASSIFICATION_RULES_PATH` | deprecated | Historical local JSON path. Must not be used as runtime fallback after M9 recognition settings are enabled. |
| `SPENDING_CATEGORY_VOCABULARY_PATH` | deprecated | Historical local JSON path. Must not be used as runtime fallback after M9 recognition settings are enabled. |
| `SPENDING_CATEGORY_RULES_PATH` | deprecated | Historical local JSON path. Must not be used as runtime fallback after M9 recognition settings are enabled. |
| `TRANSACTION_CLASSIFICATION_THRESHOLD` | `0.35` | Minimum confidence for transaction type classification before review. |
| `SPENDING_CATEGORY_THRESHOLD` | `0.35` | Minimum confidence for spending category classification before review. |
| `TRANSACTION_CLASSIFICATION_AI_ENABLED` | `false` | Enables optional AI-assisted fallback for weak, ambiguous, or unknown transaction/category classification. |
| `TRANSACTION_CLASSIFICATION_AI_PROVIDER` | unset | Provider identifier for optional AI-assisted classification; no secret values are committed. |
| `TRANSACTION_CLASSIFICATION_AI_MODEL` | unset | Model identifier for optional AI-assisted classification; model choice remains configuration. |

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
- Receipt OCR amount and date repair from generic payment-method or terminal lines, including damaged bank/card/EFTPOS amount evidence and terminal timestamp evidence.
- Receipt OCR labelled-total repair where `TOTAL` or `EFTPOS` labels and amounts are split across nearby lines or split decimal tokens, while preserving precedence over tax/GST-only values, item-like sale values, and invoice item-total computation.
- Receipt total precedence where tax/GST-only amounts are separated from the transaction total.
- Receipt-derived description precedence where sale/service/location labels are available and terminal/reference metadata is noisy.
- Invoice/bill due date and total field extraction.
- Generic section detection for statement summary, transaction table, receipt totals, invoice summary, payment proof, line items, fees/interest, rewards/points, and unknown financial blocks.
- Entity, reference, and line-item candidate extraction without issuer-specific parsing or issuer-named fixtures.
- Transaction type classification using shared vocabulary/rules for purchase, payment, transfer, refund, fee, interest, cash advance, installment, adjustment, tax, and unknown cases.
- Spending category classification using shared vocabulary/rules for MVP reporting buckets such as medical, pharmacy, groceries, utilities, transport, banking fees, interest, transfers, shopping, food/dining, income, tax, and uncategorized.
- Classification loading from M9 active recognition settings, with controlled unavailable-settings findings and no stale JSON fallback.
- Exact learned merchant classification lookup against M9 before AI, including safe reuse, inactive profile review gating, and conflict review gating.
- Learned classifications with `classification_source = prior_merchant_human_confirmed` skip AI and are not marked review-required when the learned values are active, complete, and compatible.
- Optional AI-assisted transaction/category classification fallback is called only when configured and when deterministic rules are weak, ambiguous, or unknown.
- AI-assisted classification tests use redacted/minimal candidate context and must not require real secrets or network access.
- AI-assisted outside-vocabulary transaction/spending labels remain visible on the candidate for Upload review, require user confirmation before save, and carry metadata that lets M9 activate the accepted labels during the save workflow without requiring separate admin approval.
- Long statement headers, advisory text, and rate disclosures not being misclassified as transaction rows.
- Unknown document handling.
- Ambiguous amount/date findings.
- M5-shaped input with `classification`, `quality`, `metadata`, `pages`, and parse `findings`.
- M5-shaped classification subtype handling, including `statement / credit_card_statement` transaction extraction.
- M5-shaped OCR word-block layout input using real `tests/input` fixtures, including the HSBC scanned credit-card statement.
- OCR layout repair for generic split statement rows, including orphan description prefixes/suffixes, side-column exclusion, and split `CR` marker repair.
<!-- M7 Scanned Statement Layout Extraction Start - 2026-06-15 -->
- Scanned two-column statement layout where OCR word blocks contain a left transaction table, right summary panels, and a lower payment slip. Tests must prove M7 extracts table-region rows, excludes side-summary/payment-slip amounts from transactions, preserves credit markers, and keeps prior OCR repair paths as fallback behavior.
- Regression coverage for older scanned statement PDFs whose visual table is readable but flattened OCR text has too few reliable date+amount lines. The expected result should be based on visible table-region rows and privacy-safe candidate counts/fields, not full raw financial text.
<!-- M7 Scanned Statement Layout Extraction End - 2026-06-15 -->
<!-- M7 Statement Fallback Guard Start - 2026-06-15 -->
- Statement-shaped inputs that were misclassified upstream, where M7 detects statement evidence, suppresses receipt total fallback, and returns statement extraction candidates or review findings instead of one bogus receipt transaction.
- Malformed OCR amount-token handling, including tokens such as `3.225.00`, so extraction returns controlled findings rather than an unhandled exception.
<!-- M7 Statement Fallback Guard End - 2026-06-15 -->
<!-- Review Hardening - 2026-06-02 Start -->
- Regression coverage for stale orphan-description prefixes so a prefix from one transaction row cannot leak into the next reconstructed row.
- Regression coverage for side-column summary amounts so statement summary values cannot overwrite the transaction-table amount.
- Regression coverage for split credit-marker rows so separated `CR` markers are paired with the intended row without relying on issuer-specific labels.
<!-- Review Hardening - 2026-06-02 End -->
<!-- Fixture Robustness - 2026-06-02 Start -->
- Regression coverage for vertically split OCR table rows where date/description tokens and the amount-column token are on nearby but not identical baselines. The parser must attach the nearby amount token to the transaction row using generic table geometry rather than issuer-specific templates.
- Real BPI/HSBC fixtures are regression examples only. Tests and parser branches must describe document structure, row geometry, field vocabulary, reconciliation behavior, and quality gates instead of issuer or bank names.
<!-- Fixture Robustness - 2026-06-02 End -->
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

The planned browser acceptance flow for M7 lives in `tests/scripts/M7-TransactionExtraction/M7-TransactionExtraction-test-flow.md` and is summarized in `docs/module-test-flow-playbook.md`. Updating those flow documents does not mean evidence has been run; completed evidence must be captured separately under root `tests/results/` with screenshots, raw output, a reviewer walkthrough, gaps, and cleanup status.

## Acceptance Criteria

M7 is complete when:

- The approved spec exists before implementation grows.
- `modules/transaction-extraction-module/` contains standalone runtime, configuration, README, and tests.
- `/health` and `/api/v1/extractions` are available.
- M5-style parsed text can be submitted as JSON.
- M5 classification and quality fields are accepted directly without rerunning OCR.
- M5 low/no-text and OCR readiness findings are surfaced as M7 input-quality findings.
- Transaction candidates include date/description/amount/source/confidence metadata where available.
<!-- M7 Scanned Statement Layout Extraction Start - 2026-06-15 -->
- Scanned statement OCR word-block inputs with visible transaction tables are reconstructed from the transaction-table region before flattened text fallbacks are used.
- Side-summary, rewards, advisory, credit-limit, and detachable payment-slip regions are preserved as fields/sections or ignored as non-transaction context, and are not emitted as transaction rows.
<!-- M7 Scanned Statement Layout Extraction End - 2026-06-15 -->
<!-- M7 Statement Fallback Guard Start - 2026-06-15 -->
- Statement-shape evidence suppresses receipt-style total fallback, so statement PDFs cannot become one bogus receipt transaction when summary fields are present but transaction rows need review.
- Malformed OCR amount tokens return controlled findings and do not produce unhandled extraction failures.
<!-- M7 Statement Fallback Guard End - 2026-06-15 -->
- Transaction candidates include transaction type and spending category suggestions with confidence, status, reason codes, and source when classification is enabled.
- Exact learned merchant classifications from M9 are reused before AI, marked with `classification_source = prior_merchant_human_confirmed`, and handed to M8 as ready when active, complete, and non-conflicted.
- If AI suggests a transaction type, transaction subtype, spending category, or spending subcategory outside the current active vocabulary, M7 flags the transaction candidate for user review before save.
- AI-suggested transaction/spending labels outside active vocabulary are preserved as reviewable candidate labels and are not silently replaced by `unknown` or `uncategorized` when the Upload review/save flow can provide human confirmation.
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
- Fuzzy merchant matching for learned classifications belongs to a post-MVP enhancement after exact normalized matching is proven safe.
- Full workflow orchestration belongs to M10.
- Dashboard/reporting belongs to M11.
- Email attachment retrieval belongs to M12.
- Container and cloud deployment updates belong to M13/M14.

<!-- M7 End -->
