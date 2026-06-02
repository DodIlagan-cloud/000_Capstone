# Extraction Contracts

<!-- M0 Foundation: target folder for extraction and classification contracts. -->

This folder holds extraction-oriented contracts such as:

- document parsing result
- text extraction result
- OCR/parse metadata
- document classification result
- extraction findings

## M5 Document Parsing Result

M5 merges direct text extraction, OCR fallback, and document classification into one reusable contract.

Primary request:

- Multipart document file.
- Optional ingestion/source identifiers.
- Optional SHA-256 from file intake.
- Optional direct-text, OCR fallback, language, page-limit, and classification-threshold settings.

Primary result:

- `parse_id` and `status`.
- `document` trace metadata.
- `text` and per-page text results.
- `metadata` for extraction method, OCR engine, page counts, elapsed time, language, page limit, OCR quality score, OCR mean confidence, selected orientation, selected PSM, and OCR attempt count.
- `strategy` decision showing the selected parse strategy and fallback readiness.
- `classification` with document type, document subtype, confidence, status, reason codes, and scores from the shared classification vocabulary/rules.
- `quality` and `evaluation` fields for measurable project outcomes.
- `evidence` preview with personal information, card numbers, and account numbers redacted.
- `findings` for unsupported files, OCR dependency gaps, OCR retry/quality signals, low text, or ambiguous classification.

Downstream transaction extraction consumes the M5 result rather than calling a separate OCR module and classification module.
