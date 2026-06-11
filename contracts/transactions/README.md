# Transaction Contracts

<!-- M0 Foundation: target folder for transaction and data-quality contracts. -->

This folder will hold transaction and data-quality contracts such as:

- transaction candidate
- transaction type classification
- spending category classification
- financial field candidate
- section candidate
- entity candidate
- reference candidate
- line item candidate
- normalized record
- data-quality report

These contracts should support Transaction Extraction, Data Validation, Stats workflow integration, and Stats persistence without blending their internals.

<!-- M7 - Transaction Extraction Module Start -->

## M7 Transaction Extraction Contract

M7 consumes the M5 Document Parsing Result and produces evidence-preserving candidate records for M8 Data Validation.

<!-- M7 - Robust Candidate Output Start -->
M7 must be document-agnostic. It may use document-type hints and shared financial vocabulary, but it must not depend on issuer-specific templates, issuer-named fixtures, filenames, source institutions, merchants, providers, or a single known statement layout. Original labels and redacted source snippets must be preserved so later modules can improve interpretation without losing evidence.
<!-- M7 - Robust Candidate Output End -->

Primary request:

- Optional `parse_id` from M5.
- Optional document trace metadata such as filename, ingestion ID, source, and SHA-256.
- M5 document type and classification confidence.
- Optional full M5 `classification`, `quality`, `metadata`, page text, and parse `findings`.
- Full extracted `text`.
- Optional page-level text blocks.
- Optional extraction settings such as confidence threshold, page limit, and enabled extraction modes.

Primary result:

- `extraction_id` and `status`.
- Upstream `parse_id`.
- Document trace metadata.
- `transaction_candidates` with candidate transaction date, optional posted/settled date, description, amount, currency, direction, source page/line/text, confidence, and reason codes.
- Candidate transaction type and spending category suggestions, each with label, subtype, confidence, status, reason codes, diagnostic scores, and classification source.
- `financial_field_candidates` with field name, value, normalized value when available, source page/line/text, confidence, and reason codes.
<!-- M7 - Robust Candidate Output Start -->
- `section_candidates` with generic section labels such as `statement_summary`, `transaction_table`, `receipt_totals`, `invoice_summary`, `payment_proof`, `line_items`, `fees_or_interest`, `rewards_or_points`, or `unknown_financial_block`.
- `entity_candidates` with institutions, merchants, providers, counterparties, card/payment types, and payment channels when present.
- `reference_candidates` with invoice numbers, approval codes, confirmation numbers, document references, and masked account/card/customer references when present.
- `line_item_candidates` with item/service rows from receipts, invoices, statement tables, or other itemized sections when available.
- Candidate source context with document/page/section/line/redacted snippet metadata so M8 can interpret where each value came from.
<!-- M7 - Robust Candidate Output End -->
- `summary` with counts, amount totals, pages processed, text length, and low-confidence counts.
- `evaluation` metadata for later testing and reporting.
- `findings` for missing text, low-quality M5 input, upstream OCR-disabled/failure/weak-quality conditions, unsupported document types, no candidates, ambiguous values, low confidence, page limits, or truncation.

M7 returns candidates only. M8 owns cleaning, validation, duplicate detection, and quality decisions. M9 owns Stats persistence.
M7 must not rerun OCR or call Tesseract. If M5 quality/findings show unusable text, low OCR confidence, or noisy OCR output, M7 reports input-quality findings so the workflow can decide whether M5 should be rerun with different OCR settings.

<!-- M7 - Transaction Classification Start -->
M7 owns transaction type and spending category classification. It follows the M5 classification pattern: shared committed vocabulary/rules are the primary path, and optional AI-assisted classification is a configured fallback for weak, ambiguous, or unknown rule results. Transaction type must remain separate from spending category:

- `transaction_type` / `transaction_subtype` describe the financial movement mechanics, such as purchase, payment, transfer, refund, fee, interest, installment, adjustment, tax, or unknown.
- `spending_category` / `spending_subcategory` describe the MVP reporting bucket, such as medical, pharmacy, groceries, utilities, transport, banking fees, interest, transfers, shopping, food/dining, income, tax, or uncategorized.

AI-assisted classification must use minimal redacted candidate context and must not send raw full OCR text, full account/card/customer/patient identifiers, secrets, connection strings, or whole source documents. M7 must preserve rule scores and AI contribution metadata so M8/M9/M11 can distinguish `rules`, `ai`, `rules_ai_merged`, and later `user_override` outcomes.
<!-- M7 - Transaction Classification End -->

<!-- M7 - Robust Candidate Output Start -->
M7 should avoid treating statement headers, summary blocks, advisory text, or interest-rate disclosures as transaction rows unless a transaction-table row shape is present. These values should be emitted as section, field, reference, or finding candidates with source context.
<!-- M7 - Robust Candidate Output End -->

<!-- M7 End -->

<!-- M8 - Data Validation Module Start -->

## M8 Data Validation Contract

M8 consumes M7 transaction, financial field, section, entity, reference, and line-item candidates and produces normalized records plus data-quality findings for M9 persistence.

Primary request:

- Optional `extraction_id` and `parse_id` from upstream M7/M5.
- Optional document trace metadata.
- M7 `document_type`.
- M7 `transaction_candidates` with date text, optional posted/settled date text, description, amount, currency, direction, source, confidence, and reason codes.
- M7 transaction type and spending category suggestion fields on each transaction candidate.
- M7 `financial_field_candidates` with field name, values, source, confidence, and reason codes.
<!-- M8 - Robust Candidate Input Start -->
- Optional M7 `section_candidates`, `entity_candidates`, `reference_candidates`, and `line_item_candidates` used as source context, metadata, reconciliation inputs, and review evidence.
<!-- M8 - Robust Candidate Input End -->
- Optional validation settings such as confidence threshold, same-batch duplicate detection, and required field switches.

Primary result:

- `validation_id` and `status`.
- Upstream `extraction_id` and `parse_id`.
- Document trace metadata.
- `normalized_records` with normalized transaction date, optional posted/settled date, title-cased description, currency, direction, signed amount, quality status, duplicate marker, and source candidate ID.
- Preserved transaction type, transaction subtype, spending category, spending subcategory, classification confidence, category confidence, classification source, and review flags on normalized records.
- `financial_fields` with normalized field names and values.
<!-- M8 - Robust Candidate Input Start -->
- `validated_entities`, `validated_references`, and `validated_line_items` when supplied by M7 and useful to downstream modules.
- `document_financial_summary` when M7 supplied statement, invoice, receipt, payment-proof, fee/interest, or rewards/points fields that are not transaction rows.
<!-- M8 - Robust Candidate Input End -->
- `summary` with valid, warning, invalid, same-batch duplicate, debit, credit, and net totals.
- `evaluation` metadata for later testing and reporting.
- `findings` for missing candidates, incomplete records, invalid amounts, low confidence, unknown direction, same-batch duplicate transactions, and record limits.
- `findings` for unknown, ambiguous, or low-confidence transaction type and spending category classifications.

M8 returns validation-ready records only. M9 owns database persistence, database duplicate checks against already stored records, and Stats-specific storage schema decisions.
<!-- M8 - Robust Candidate Input Start -->
M8 must preserve source context from M7 so M11 can show evidence-backed dashboards where each amount can be traced to a source document, page, section, and redacted snippet.
`document_financial_summary` excludes fields sourced from `transaction_table`; those values belong to normalized transaction records and must not be double-counted as document-level totals.
Transaction candidates sourced from non-transaction sections must be marked for review rather than treated as clean save-ready records.
<!-- M8 - Robust Candidate Input End -->

<!-- M8 End -->
