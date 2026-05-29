# Transaction Contracts

<!-- M0 Foundation: target folder for transaction and data-quality contracts. -->

This folder will hold transaction and data-quality contracts such as:

- transaction candidate
- financial field candidate
- normalized record
- data-quality report

These contracts should support Transaction Extraction, Data Validation, Stats workflow integration, and Stats persistence without blending their internals.

<!-- M7 - Transaction Extraction Module Start -->

## M7 Transaction Extraction Contract

M7 consumes the M5 Document Parsing Result and produces candidate records for M8 Data Validation.

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
- `transaction_candidates` with candidate date, description, amount, currency, direction, source page/line/text, confidence, and reason codes.
- `financial_field_candidates` with field name, value, normalized value when available, source page/line/text, confidence, and reason codes.
- `summary` with counts, amount totals, pages processed, text length, and low-confidence counts.
- `evaluation` metadata for later testing and reporting.
- `findings` for missing text, low-quality M5 input, upstream OCR-disabled/failure/weak-quality conditions, unsupported document types, no candidates, ambiguous values, low confidence, page limits, or truncation.

M7 returns candidates only. M8 owns cleaning, validation, duplicate detection, and quality decisions. M9 owns Stats persistence.
M7 must not rerun OCR or call Tesseract. If M5 quality/findings show unusable text, low OCR confidence, or noisy OCR output, M7 reports input-quality findings so the workflow can decide whether M5 should be rerun with different OCR settings.

<!-- M7 End -->
