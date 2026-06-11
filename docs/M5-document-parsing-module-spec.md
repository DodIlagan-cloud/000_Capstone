<!-- M5 - Document Parsing Module Start -->
<!-- Specifies the merged OCR/text extraction and document classification module before implementation. -->

# Module 5 Document Parsing Module Specification

## Module Summary

Module 5 establishes the reusable **Document Parsing Module** for the Stats project. It combines the former OCR/text extraction and document classification responsibilities into one measurable parse step.

M5 receives a validation-accepted document from the File Validation and Ingestion Module, extracts usable text using the correct strategy for the file, classifies the document type, and returns parse quality, OCR readiness, redacted evidence, findings, and evaluation metadata.

This module does **not** extract final transaction rows, clean financial data, write Stats database records, render dashboards, fetch email, or own Stats Web presentation. Those concerns belong to later modules.

Implementation must not proceed until this specification is reviewed and accepted.

## Architecture Alignment

M5 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M2-stats-web-shell-spec.md`
- `docs/M3-file-validation-module-spec.md`

The corrected module boundary is:

| Field | M5 Direction |
| --- | --- |
| Build order | `5` |
| Module | Document Parsing Module |
| Type | Standalone reusable module |
| Main responsibility | Extract text from PDFs/images/scans, classify document type, and expose measurable parse metadata |
| Reusable contract | Document parsing request/result contract |
| Owner folder | `modules/document-parsing-module/` |
| Stats Web role | Calls M5 after validation/ingestion succeeds; does not implement OCR or classification logic |

## Roadmap Alignment Note

The current roadmap may still show M5 as OCR Extraction and M6 as Document Classification. That split is superseded by this spec. After this M5 spec is approved, the roadmap should be updated so:

- M5 covers Document Parsing: OCR/text extraction plus document classification.
- Former M6 classification work is merged into M5.
- Later transaction/data-quality work moves to the next module group.
- M13 starts early only as a portable runtime/tooling dependency for M5 OCR, not as full cloud deployment.

## Goals

- Provide a standalone FastAPI service for document parsing.
- Accept PDF, PNG, JPG, and JPEG documents from upload/intake workflows.
- Choose direct PDF text extraction when a PDF contains usable embedded text.
- Use Tesseract OCR when configured for image files or scanned/no-text PDFs.
- Normalize image orientation from EXIF metadata when present, then retry likely rotations when OCR quality is weak or orientation metadata is absent/unreliable.
- Preprocess image OCR inputs with grayscale/contrast/upscale variants so JPEG screenshots and camera captures have a better chance of producing usable text.
- Add a conservative document-crop OCR variant for camera photos when a bright document/receipt region can be separated from darker background clutter without relying on merchant-specific templates.
- For receipt and payment-terminal photos, include preprocessing attempts that improve faint thermal-printer text and terminal/customer-copy rows, such as autocontrast, sharpened contrast, and thresholded variants, without relying on merchant-specific templates.
- Score OCR attempts using mean confidence, text volume, character quality, and financial keywords so the module can pick the best Tesseract output instead of accepting the first pass blindly.
- OCR attempt scoring for receipt-like documents should favor preservation of transaction-critical evidence, including date/time tokens, terminal/EFTPOS/payment terms, approval/reference signals, and amount/currency tokens, so a longer or smoother OCR attempt does not win if it loses visible transaction details.
- For image OCR, stop early when a candidate already has strong extraction evidence: sufficient text, acceptable quality/confidence, clean labelled amount evidence, and document-shape signals such as receipt/tax invoice, total, EFTPOS/payment, GST/tax, date, or time. Continue through the broader orientation/variant/PSM search when amount evidence is weak, damaged, split, or conflicting, even if the text is clearly receipt-like.
- Use adaptive OCR effort so cloud-dev remains lightweight: scanned PDFs should run a small fast OCR profile first and escalate to the broader orientation/preprocessing/PSM retry matrix only for pages whose first pass does not meet configured quality, text-volume, confidence, or transaction-signal thresholds. Image/photo uploads may still use the broader retry matrix because a single camera image often needs orientation and preprocessing repair.
- Use a PDF rendering dependency, preferably PyMuPDF, to render scanned PDF pages before OCR.
- Classify parsed documents using the shared document-classification vocabulary after text extraction completes, regardless of whether text came from direct PDF extraction, scanned-PDF OCR, or image OCR.
- Keep document classification rule-first and deterministic by default, with an optional AI-assisted fallback that is disabled unless explicitly configured. The fallback may run only for unknown, ambiguous, low-confidence, or new-shape classifications and must receive redacted/truncated text only.
<!-- M5 Recognition Resilience Update Start - 2026-06-12 -->
- When M5 loads active recognition settings from M9, it must use a still-available in-memory cache from a successful prior M9 load during a temporary M9/API outage. M5 may return recognition-settings-unavailable only when no active M9 settings cache exists. This does not permit falling back to deprecated committed JSON configuration files in the container image.
<!-- M5 Recognition Resilience Update End - 2026-06-12 -->
<!-- M5 Document Suggestion Approval Start - 2026-06-11 -->
- When AI identifies a plausible document type that is not currently active in M9 recognition settings, M5 must not activate or return that label as the approved document type. It must return the safest approved current value, normally `unknown`, plus pending suggestion metadata containing the proposed document type/subtype, confidence, source, reason codes, and redacted evidence reference for M9/admin review.
<!-- M5 Document Suggestion Approval End - 2026-06-11 -->
- Return both `document_type` and optional `document_subtype` when the shared vocabulary and rule signals support a subtype.
- Treat Stats Web `/Admin/Classifications` as the administrator recognition settings surface for approved document recognition configuration, pending recognition suggestions, and approval workflows. M5 remains the owner of document classification behavior, but M9 is the database source of truth for approved labels, rules, suggestions, audit history, and synchronization.
- Return strategy metadata explaining whether the module used PDF text extraction, OCR, disabled OCR handling, or failure handling.
- Return quality metadata such as text length, page count, pages processed, empty-page count, and low-text status.
- Return explicit findings for unsupported media, unreadable files, OCR disabled, Tesseract unavailable, renderer unavailable, OCR failure, no text, low text quality, and uncertain classification.
- Return evaluation-ready fields for measuring extraction reliability, OCR fallback rate, classification confidence, processing time, and redaction compliance.
- Return an extraction handoff audit that proves whether OCR/Tesseract ran, whether parse text is present, whether transaction-like signals exist, and whether the parse output is ready for downstream transaction extraction.
- Support upload workflow observability by exposing safe parse/OCR timing metadata that Stats Web can log and M9 can persist as the M5 processing-step summary.
- Redact personal information, account numbers, card numbers, and other sensitive values from evidence previews.
- Use real approved project TestData for automated/evidence checks.
- Keep runtime behavior configurable through defaults, ignored local overrides, environment variables, and later M13 container settings.

## Non-Goals

- Validating upload file type, size, extension, or signatures. That belongs to M3/M4.
- Creating ingestion records or storage handoff records. That belongs to M3/M4.
- Handling storage-provider failures for accepted uploads. That belongs to M3/M4, and those failures must return controlled ingestion rejection details rather than an unhandled 500 before M5 is invoked.
- Extracting structured transaction rows or financial fields. That belongs to Transaction Processing.
- Cleaning, categorising, deduplicating, or validating transaction records.
- Persisting parsed results into the Stats database.
- Owning dashboard/reporting views.
- Owning Stats Web UI layout beyond defining what information the caller may display.
- Creating full cloud deployment. M13/M14 own deployment packaging and cloud readiness.

## Inputs

M5 accepts document content or an allowed document reference from the workflow layer.

| Input | Required | Description |
| --- | --- | --- |
| `file` | Yes for upload endpoint | Multipart PDF/image content. |
| `ingestion_id` | No | Upstream ingestion identifier from M3/M4. |
| `source_type` | No | Source such as `manual_upload` or future `email_attachment`. |
| `source_id` | No | Caller-provided source identifier. |
| `sha256` | No | Upstream file hash for traceability. |
| `allow_direct_text` | No | Request-level override for direct PDF extraction. |
| `allow_ocr_fallback` | No | Request-level override for OCR fallback. |
| `language` | No | OCR language hint such as `eng`. |
| `page_limit` | No | Maximum pages to parse/OCR. |
| `classification_threshold` | No | Minimum confidence for non-unknown classification. |

## Outputs

M5 returns a **Document Parsing Result**.

| Output | Description |
| --- | --- |
| `parse_id` | Unique parse attempt identifier. |
| `status` | `completed`, `completed_with_warnings`, `failed`, or `unsupported`. |
| `document` | Source filename, normalized filename, size, media type, ingestion ID, source, and hash. |
| `text` | Extracted text for downstream processing. |
| `pages` | Per-page/per-image text, length, empty-page flag, and optional OCR word-block layout evidence. |
| `metadata` | Extraction method, OCR engine, page counts, elapsed time, language, and page limit. |
| `strategy` | Selected strategy and decision reason. |
| `classification` | Document type, confidence, classification status, and reason codes. |
| `quality` | Text length, page coverage, empty-page count, and low-text flag. |
| `evaluation` | Measurement fields for later evaluation and reporting. |
| `evidence` | Redacted text preview and redaction counts. |
| `extraction_handoff` | Safe audit object for checking M5 execution and downstream extraction readiness without storing full sensitive text. |
| `findings` | Explicit warning/error codes and messages. |

M5 does not return final transaction records.

### Extraction Handoff Audit

The `extraction_handoff` object is the preferred local/debug view for confirming that M5 executed correctly before downstream transaction extraction runs.

It is part of the API response for developer diagnostics, regression evidence, and downstream readiness checks. It is not intended to be the main user-facing Upload page result; Stats Web should keep raw handoff/audit payloads behind a developer detail view and present plain-language parse and transaction-check summaries to ordinary users.

| Field | Description |
| --- | --- |
| `parse_id` | Parse attempt identifier that downstream extraction can reference. |
| `document_id` | Upstream ingestion ID when available, otherwise derived document hash. |
| `filename` | Normalized document filename. |
| `strategy` | Selected parse strategy, such as `pdf_text`, `tesseract_ocr`, or `ocr_disabled`. |
| `extraction_method` | Actual extraction method, such as `direct_pdf_text` or `ocr`. |
| `ocr_engine` | `tesseract` when Tesseract OCR was selected; otherwise null. |
| `ocr_attempted` | Whether OCR was attempted. |
| `tesseract_available` | Whether Tesseract was available to the M5 runtime. |
| `status` | Parse status. |
| `confidence` | Classification confidence. |
| `text_length` | Extracted text length. |
| `page_count` / `pages_processed` | Page coverage metadata. |
| `warnings` | Warning finding codes that may affect downstream extraction quality. |
| `extraction_ready` | True only when parse status, text length, and transaction signals are sufficient for downstream extraction. |
| `extraction_readiness_reason_codes` | Reason codes when the parse output is not extraction-ready. |
| `transaction_signal_count` | Lightweight count of transaction-related keywords, amount-like values, and date-like values. |
| `redacted_preview` | Redacted preview of extracted text for human inspection. |
| `redaction_summary` | Count of sensitive values masked in the preview. |
| `redaction_applied` | Whether the preview redaction matched sensitive values. |

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service and OCR readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/parses` | `POST` | Parses a multipart document and returns the Document Parsing Result. |

M5 remains a synchronous module API. Cloud-facing upload flows must not expose that synchronous runtime directly to the browser for OCR-heavy files because Azure Container Apps ingress can cancel long-running HTTP requests. Stats Web should call M5 from a background upload-processing workflow and report progress through an M9 processing-job status record. Once this async workflow is used, Stats Web must not force the earlier cloud-timeout workaround of `page_limit=1`; statement and multi-page documents need the M5 default page coverage so M7 can see the transaction pages.

## Processing Step Timing

M5 participates in the cross-module upload timing contract. The M5 response must continue to expose safe parse timing and OCR metadata such as elapsed milliseconds, page count, pages processed, OCR attempted, OCR engine, OCR attempt count where available, selected strategy, and finding count.

For receipt-like image OCR, M5 must also expose amount-coherence metadata so downstream modules and evidence reviewers can see why a fast OCR path stopped or continued. This includes `amount_coherence_score`, `amount_coherence_status`, and `amount_conflict_reasons`, with statuses such as clean, weak, or conflicting.

Stats Web owns the orchestration timer around the M5 `/api/v1/parses` call. M9 owns durable persistence of that step as `module = M5`, `step_name = document_parsing`, `status`, `started_at_utc`, `completed_at_utc`, `duration_ms`, and safe metadata. M5 must not write M9 database rows directly.

Stats Web may present an administrator-only recognition settings page that reads approved vocabulary, rules, and pending suggestions from M9. Runtime edits must not be implemented as direct browser writes to committed files. The backend must validate proposed labels/rules, write approved changes to M9 inside an audited database operation, and coordinate M9 synchronization when persisted records need rename, merge, or apply behavior.

## Strategy Rules

| Condition | Expected Strategy |
| --- | --- |
| PDF has usable embedded text and direct text is enabled | `pdf_text` |
| PDF has insufficient/no embedded text and OCR fallback is enabled | `tesseract_ocr` after page rendering |
| PNG/JPG/JPEG and OCR fallback is enabled | `tesseract_ocr` with EXIF orientation handling, preprocessing, and orientation/PSM retry |
| OCR is needed but disabled | `ocr_disabled` with explicit finding |
| OCR is enabled but Tesseract is unavailable | `tesseract_ocr` attempted with `TESSERACT_UNAVAILABLE` |
| Scanned PDF OCR needs rendering but renderer is unavailable | `PDF_RENDERER_UNAVAILABLE` |
| Unsupported media type | `unsupported` |

<!-- M5 Recognition Settings DB Source Start - 2026-06-10 -->
## Classification Vocabulary and Rules

M5 owns applying document classification, but the allowed classification labels and matching signals are shared project configuration rather than module-private constants.

Active recognition settings must be database-backed:

| Source | Purpose |
| --- | --- |
| M9 recognition settings tables | Source of truth for approved document types, subtypes, rule signals, pending suggestions, approvals, audit history, and synchronization state. |
| M9 recognition settings API | Runtime read/write boundary used by M5, M7, and Stats Web. |
| `contracts/document-classification/README.md` | Human-readable ownership, lifecycle, and downstream contract. |
| Historical root `config/*.json` recognition files | Deprecated for runtime use. They may be retained temporarily only as migration seed/reference material until the M9 seed is complete. |

M5 must load active approved document vocabulary and rules from M9 through the configured recognition settings API. It must not use committed JSON files as a silent runtime fallback because stale files inside an image would make cloud behavior drift from approved administrator changes. If M9 or the recognition settings API is unavailable, M5 must fail the classification step clearly with a controlled finding such as `RECOGNITION_SETTINGS_UNAVAILABLE`, keep parsing/OCR metadata intact, and return an `unknown / unknown` classification that requires review. This failure mode must be visible to Stats Web and evidence runs.

The initial vocabulary should support generic document types:

- `statement`
- `receipt`
- `invoice`
- `payment_proof`
- `utility_bill`
- `unknown`

The initial subtype vocabulary should distinguish common financial shapes without relying on issuer, bank, merchant, provider, filename, or source institution names. Examples include:

- `statement / credit_card_statement`
- `statement / account_statement`
- `statement / loan_statement`
- `receipt / sales_receipt`
- `receipt / tax_receipt`
- `receipt / payment_terminal_receipt`
- `invoice / service_invoice`
- `invoice / medical_invoice`
- `payment_proof / bank_transfer_proof`
- `payment_proof / card_payment_proof`
- `unknown / unknown`

M5 classification must use the extracted text and quality metadata produced by the selected parsing strategy:

- Direct PDF text extraction.
- Scanned-PDF rendering plus Tesseract OCR.
- Image Tesseract OCR.

The classification rules must run after extraction and should not care which extraction path produced the text. OCR quality findings may lower classification confidence or add reason codes, but they must not cause M5 to use a separate OCR-only classification vocabulary.

Classification signals must be generic. For example, `statement / credit_card_statement` may be inferred from signals such as `credit card`, `card type`, `credit limit`, `minimum amount due`, `payment due date`, `finance charge`, `previous balance`, `unbilled installment`, and `total outstanding balance`. `statement / account_statement` may be inferred from signals such as `account number`, `opening balance`, `closing balance`, `available balance`, `deposits`, `withdrawals`, `running balance`, and `transaction history`. `receipt / payment_terminal_receipt` may be inferred from EFTPOS/card terminal signals such as terminal, merchant copy, approved, purchase, RRN, AID, TVR, TSI, card, and total. `invoice / medical_invoice` may be inferred from invoice signals plus healthcare/lab context such as patient identifiers, date of birth, lab, test names, service fee, payment history, paid, owing, and GST.

For OCR images of retail receipts, labels such as `tax invoice`, `GST`, `EFTPOS`, `purchase`, `approved`, `total`, `subtotal`, `tax`, `receipt`, and terminal/card references are receipt signals even when the word `invoice` is present. M5 must not classify these common sales/tax receipt shapes as `unknown` merely because invoice and receipt signals overlap; the labelled receipt/payment/total evidence should support `receipt / tax_receipt` or `receipt / payment_terminal_receipt`.

### AI-Assisted Classification Fallback

M5 owns the AI-assisted document classification component. It is an optional fallback over the M5 classification result, not a replacement for the shared vocabulary/rules.

The default behavior is:

- `CLASSIFICATION_AI_ENABLED=false`.
- `CLASSIFICATION_AI_PROVIDER=gemini`.
- `CLASSIFICATION_AI_MODEL=gemini-2.5-flash`.
- `CLASSIFICATION_AI_API_KEY_ENV=GEMINI_API_KEY`.
- M5 does not call an external AI provider.
- Classification remains fully deterministic and testable through shared rules.

When explicitly enabled and configured, the AI-assisted classifier may run only when the rule result is `unknown`, `ambiguous`, below `CLASSIFICATION_AI_TRIGGER_THRESHOLD`, or flagged with `POSSIBLE_NEW_DOCUMENT_SHAPE`. The first supported provider for capstone/dev use is Gemini through Google AI Studio / Gemini API `generateContent`.

Before calling the AI provider, M5 must:

- Redact personal information, card numbers, account numbers, email addresses, and similar sensitive values.
- Truncate the prompt text to `CLASSIFICATION_AI_MAX_CHARS`.
- Send only the supported document vocabulary, the rule result, and redacted extracted text.
- Avoid sending raw uploaded file bytes or unredacted evidence.

The provider response must map back to the M5 vocabulary and include document type, subtype, confidence, reason codes, model name/version, and review requirement. M5 accepts the AI suggestion only when confidence is at or above `CLASSIFICATION_AI_MIN_CONFIDENCE`. If the deterministic rule result is already classified and the AI result conflicts, M5 preserves the rule result, marks the classification as requiring review, and records conflict reason codes.

### Classification Output

The `classification` object should include:

| Field | Description |
| --- | --- |
| `document_type` | Top-level type from the shared vocabulary. |
| `document_subtype` | Optional subtype from the shared vocabulary, or `unknown`. |
| `confidence` | Confidence score after rule matching and text-quality adjustment. |
| `status` | `classified`, `ambiguous`, `unknown`, or `unsupported`. |
| `reason_codes` | Generic rule/evidence codes that explain the classification. |
| `scores` | Optional per-type or per-subtype scores for diagnostics. |
| `classification_source` | Source of the final decision, such as `rules`, `ai_assist`, `rules_ai_agreement`, `rules_ai_low_confidence`, or `rules_ai_conflict`. |
| `ai_model_name` | AI model/deployment name when AI assistance was attempted and returned a parseable result. |
| `ai_model_version` | AI model version or deployment label when available. |
| `ai_confidence` | Raw AI confidence score when available. |
| `requires_review` | Whether the classification needs human/developer review before rules are trusted. |
| `review_reason_codes` | Review reason codes such as low AI confidence or rule/AI conflict. |

### Admin-Approved Recognition Configuration Lifecycle

Document classification vocabulary and matching rules are controlled database configuration. Runtime uploads must not silently add, remove, or mutate approved document types/subtypes.

The accepted lifecycle is:

1. M5 classifies with approved vocabulary/rules first.
2. If the document is unknown, ambiguous, or appears to be a new shape, M5 returns review findings such as `POSSIBLE_NEW_DOCUMENT_SHAPE` with redacted evidence.
3. If AI assistance is enabled, M5 may create a pending suggestion that maps to an approved label or proposes a new document label/rule candidate. The suggestion must include redacted evidence, reason codes, source document context, and confidence metadata.
4. If deterministic content evidence strongly matches a supported document shape whose approved label is not currently active, M5 must keep the active document type as `unknown` and emit a pending non-AI document suggestion with redacted evidence metadata. This allows administrator approval to restore a known document type without requiring an external AI call.
5. The upload user may continue the workflow using the safest current approved label, usually `unknown / unknown`, when a new label is not yet approved.
6. An administrator reviews pending suggestions in Stats Web. The administrator may approve, edit before approving, reject, or merge the suggestion into an existing approved label.
7. Only an approved admin action may update the active M9 recognition settings.
8. Approved configuration changes must be audited in M9 and must update affected persisted records through M9 when the admin chooses rename, merge, or apply behavior.
9. A rejected suggestion stays as historical review evidence and must not change active settings or existing records.
10. A pending suggestion may be linked to uploaded documents or candidate transactions, but those records must keep the safest approved active value, usually `unknown` or `uncategorized`, until approval.

This workflow preserves explainability while allowing non-admin uploads and AI-assisted recognition to improve the system over time.

Admin review and evidence failures must be plain-language. If a document recognition suggestion can no longer be approved because it was already reviewed, removed, or created by a stale test run, Stats Web must show a message such as `This review item is no longer available. Refresh the items to review and try again.` It must not show raw HTTP status text, raw API JSON, stack traces, or secret-bearing diagnostics to the user.
<!-- M5 Recognition Settings DB Source End - 2026-06-10 -->

## Finding Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `MISSING_DOCUMENT` | Error | No content was supplied. |
| `DOCUMENT_TOO_LARGE` | Error | Document exceeds configured maximum size. |
| `UNSUPPORTED_MEDIA_TYPE` | Error | Media type is not supported. |
| `UNREADABLE_DOCUMENT` | Error | PDF could not be opened or parsed. |
| `DIRECT_TEXT_DISABLED` | Warning | Direct PDF text extraction is disabled. |
| `OCR_FALLBACK_DISABLED` | Warning/Error | OCR was needed but disabled. |
| `TESSERACT_UNAVAILABLE` | Error | OCR was needed but Tesseract is unavailable. |
| `PDF_RENDERER_UNAVAILABLE` | Error | Scanned PDF OCR needs rendering but renderer is unavailable. |
| `OCR_FAILED` | Error | OCR engine failed while processing the document. |
| `OCR_TIMEOUT` | Error | OCR exceeded the configured timeout. |
| `OCR_ORIENTATION_RETRIED` | Info | OCR attempted more than one orientation or page segmentation mode before selecting the best result. |
| `LOW_OCR_CONFIDENCE` | Warning | Tesseract returned text with mean confidence below the configured threshold. |
| `OCR_TEXT_NOISY` | Warning | OCR text quality score or alphanumeric ratio is below the configured threshold. |
| `PAGE_LIMIT_APPLIED` | Warning | Only configured maximum pages were processed. |
| `LOW_TEXT_QUALITY` | Warning | Extracted text is below the configured threshold. |
| `NO_TEXT_EXTRACTED` | Warning | Parsing completed without usable text. |
| `CLASSIFICATION_UNKNOWN` | Warning | Classification confidence was below threshold. |
| `CLASSIFICATION_AMBIGUOUS` | Warning | Multiple classes were plausible. |
| `UNSUPPORTED_DOCUMENT_CLASS` | Error | No supported classes are configured. |

## Runtime Configuration

Configuration must load from committed safe defaults, optional ignored `.env`, and environment variables.

Expected settings:

| Setting | Suggested Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Document Parsing Module` | API display name. |
| `APP_VERSION` | `1.0.0` | API version metadata. |
| `API_PREFIX` | `/api/v1` | Versioned route prefix. |
| `API_HOST` | `127.0.0.1` | Local host binding. |
| `API_PORT` | `8015` | Local API port. |
| `CORS_ALLOWED_ORIGINS` | Stats Web local origins | Browser caller origins. |
| `SUPPORTED_MIME_TYPES` | `application/pdf,image/png,image/jpeg` | Supported input media. |
| `MAX_DOCUMENT_SIZE_BYTES` | `10485760` | Maximum accepted parse input size. |
| `ALLOW_DIRECT_TEXT` | `true` | Enables direct PDF text extraction. |
| `ALLOW_OCR_FALLBACK` | `false` locally until OCR runtime is configured | Enables Tesseract fallback. |
| `OCR_ENGINE` | `none` locally, `tesseract` in packaged runtime | OCR engine identifier. |
| `TESSERACT_CMD` | empty locally unless needed | Path to Tesseract executable. |
| `TESSDATA_PREFIX` | empty locally unless needed | Path to OCR language data. |
| `OCR_LANGUAGES` | `eng` | OCR language hint. |
| `OCR_PSM_VALUES` | `6,11,4` | Tesseract page segmentation modes tried for OCR. |
| `OCR_RETRY_ORIENTATIONS` | `true` | Enables 0/90/180/270 orientation retry after EXIF normalization. |
| `OCR_PDF_FAST_PSM_VALUES` | `6,4` | Smaller first-pass PSM set for scanned PDF pages before heavier OCR repair is attempted. |
| `OCR_IMAGE_FAST_PSM_VALUES` | `6,11` | Prioritized PSM values tried first for image OCR before broader repair attempts. |
| `OCR_FAST_MIN_QUALITY_SCORE` | `0.55` | Minimum OCR quality score that allows a scanned PDF page to skip heavier OCR repair. |
| `OCR_FAST_MIN_TEXT_LENGTH` | `120` | Minimum first-pass OCR text length that allows a scanned PDF page to skip heavier OCR repair. |
| `OCR_IMAGE_FAST_MIN_QUALITY_SCORE` | `0.62` | Minimum image OCR quality score for early stop. |
| `OCR_IMAGE_FAST_MIN_TEXT_LENGTH` | `80` | Minimum useful image OCR text length for early stop. |
| `OCR_IMAGE_FAST_MIN_CONFIDENCE` | `50` | Minimum mean Tesseract confidence for image OCR early stop when confidence is available. |
| `OCR_PDF_RENDER_SCALE` | `2.0` | PDF page render scale used before Tesseract OCR. |
| `OCR_MIN_CONFIDENCE` | `35` | Minimum acceptable mean OCR confidence before a warning is raised. |
| `OCR_MIN_QUALITY_SCORE` | `0.35` | Minimum OCR quality score before noisy-text warning is raised. |
| `OCR_MIN_ALNUM_RATIO` | `0.35` | Minimum alphanumeric ratio before noisy-text warning is raised. |
| `SUPPORTED_DOCUMENT_TYPES` | `statement,receipt,invoice,payment_proof,utility_bill,unknown` | Top-level classification classes. |
| `RECOGNITION_SETTINGS_URL` | M9 recognition settings API URL | Source of approved document vocabulary/rules and pending-suggestion write boundary. |
| `RECOGNITION_SETTINGS_CACHE_SECONDS` | `300` | Short cache for approved settings so one upload does not repeatedly call M9. |
| `DOCUMENT_CLASSIFICATION_VOCABULARY_PATH` | deprecated | Historical local JSON path. Must not be used as runtime fallback after M9 recognition settings are enabled. |
| `DOCUMENT_CLASSIFICATION_RULES_PATH` | deprecated | Historical local JSON path. Must not be used as runtime fallback after M9 recognition settings are enabled. |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.70` | Minimum non-unknown confidence. |
| `CLASSIFICATION_AI_ENABLED` | `false` | Enables optional AI-assisted classification fallback for weak rule results. |
| `CLASSIFICATION_AI_PROVIDER` | `gemini` | AI provider selector. Supported values are `gemini`, `openai`, and `openai_compatible`. |
| `CLASSIFICATION_AI_ENDPOINT` | empty | Optional endpoint override. Gemini defaults to Google `generateContent` for the configured model when empty. |
| `CLASSIFICATION_AI_API_KEY_ENV` | `GEMINI_API_KEY` | Name of the secret-backed environment variable containing the provider key. |
| `CLASSIFICATION_AI_MODEL` | `gemini-2.5-flash` | AI model/deployment name. |
| `CLASSIFICATION_AI_MODEL_VERSION` | `gemini-2.5-flash` | AI model version or deployment label for audit metadata. |
| `CLASSIFICATION_AI_MIN_CONFIDENCE` | `0.76` | Minimum AI confidence before accepting an AI-assisted classification. |
| `CLASSIFICATION_AI_TRIGGER_THRESHOLD` | `0.70` | Rule-confidence threshold below which AI assistance may be attempted. |
| `CLASSIFICATION_AI_MAX_CHARS` | `3000` | Maximum redacted extracted-text characters sent to the AI provider. |
| `EXTRACTION_TIMEOUT_SECONDS` | `30` | Processing timeout. |
| `MAX_PAGE_COUNT` | `25` | Page processing limit. |
| `MIN_TEXT_LENGTH` | `20` | Low/no-text threshold. |
| `REDACT_EVIDENCE_OUTPUT` | `true` | Enables redacted preview output. |
| `REDACTION_PREVIEW_CHARS` | `500` | Maximum preview length. |

Hardcoded environment-dependent runtime values allowed in source: none.

## M13 Runtime Alignment

M5 needs Tesseract and PDF rendering support, but it must not assume those tools are manually installed on a developer laptop or cloud VM.

M13 owns the single top-level Stats runtime container that will package:

- Stats Web.
- Current module APIs.
- Python runtime/dependencies.
- Tesseract executable.
- Required OCR language data, at minimum `eng`.
- PyMuPDF or equivalent PDF renderer.
- Startup orchestration and health checks.

M5 owns OCR behavior. M13 owns portable runtime packaging.

## Stats Web Flow

The normal user flow should be seamless:

```text
drag/drop document -> validate -> ingest -> parse -> display parse result
```

Stats Web should not require a separate “parse contents” button for the normal path. After validation succeeds and ingestion returns a queued or duplicate handoff, Stats Web or the workflow coordinator should call M5 automatically.

Stats Web may display:

- parse status
- document type and subtype when M5 classifies a subtype, using plain user-facing labels such as `Credit card statement` or `Payment terminal receipt`
- confidence
- strategy
- text length
- findings
<!-- M8 - Data Validation Module Start -->
- user-facing transaction check results after M7/M8 processing
- developer details collapsed behind a separate developer detail view when raw parse/extraction/validation data is needed
<!-- M8 End -->

Stats Web must not implement OCR, PDF parsing, redaction, or classification rules.

## Ethical Data Handling

M5 processes financial documents and must follow ethical data handling expectations:

- Tests and evidence must use the approved TestData directory, not ad hoc synthetic substitutes, unless the user explicitly approves a narrow isolated unit fixture.
- Evidence summaries must not copy full raw extracted text from personal financial documents.
- Evidence previews must redact personal information, card numbers, account numbers, email addresses, and similar sensitive identifiers.
- Raw API responses may be viewable locally for development/evaluation, but assessment summaries should retain only metadata and redacted previews.
- Redaction counts should be included so evaluation can measure privacy controls.

## Testing Boundary (M13)

M13 establishes the required container-first test path for M5:

| Tier | What runs | Where | Tool |
| --- | --- | --- | --- |
| Unit / contract | Module-level checks, parse logic, OCR disabled/unavailable states | Stats runtime container | `tests\scripts\regression\run_module_unit_tests.ps1` |
| Acceptance / evidence (OCR end-to-end) | Real fixture files through containerized Tesseract OCR | Docker stack | `tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1` |

Host-side runs are development diagnostics only after M13. Evidence that confirms `strategy: tesseract_ocr` for image files and `method: ocr` for scanned PDFs must be produced by the M13 containerized runtime.

## Testing

M5 tests must be efficient and scoped to touched behavior.

Before a fresh M5/M6 evidence run, update the planned flow in `docs/module-test-flow-playbook.md`. This planning update is separate from running tests. Do not start Docker/browser/terminal evidence capture unless the user explicitly requests an evidence run.

Module-local automated tests must cover:

- App import and metadata.
- `/health` and `/` endpoints.
- OCR readiness metadata.
- Runtime defaults and environment overrides.
- Direct PDF text extraction.
- Real configured TestData PDF parsing.
- Image OCR path when OCR is enabled.
- Scanned/no-text PDF OCR path when OCR is enabled.
- OCR disabled behavior.
- Tesseract unavailable behavior.
- PDF renderer unavailable behavior.
- Unsupported media type behavior.
- Classification for supported document types.
- Classification for supported document types/subtypes from shared vocabulary and rules.
- Classification rule behavior for both direct PDF text and Tesseract OCR-produced text.
- Classification rule/vocabulary loading from M9 active recognition settings.
- Controlled unavailable-settings behavior when the M9 recognition settings API is unavailable, with no stale JSON fallback.
- Unknown/low-confidence classification.
- Unknown document shape behavior with `POSSIBLE_NEW_DOCUMENT_SHAPE` and no runtime vocabulary mutation.
- AI-assisted classification disabled-by-default behavior.
- AI-assisted classification acceptance for weak rule results when enabled, redacted, vocabulary-compliant, and above confidence threshold.
- AI-assisted classification conflict handling so deterministic rule results are preserved and review reason codes are emitted.
- Redaction of sensitive evidence values.
- Evaluation metadata fields.
- Multipart `/api/v1/parses` endpoint.

Actual app evidence should cover:

- User signs in.
- Upload page accepts drag/drop or selected file.
- File validates through M3/M4.
- Accepted file is ingested.
- M5 parse runs automatically.
- At least one text-layer PDF fixture from `tests/input` proves direct PDF text extraction or normal PDF parsing.
- At least one OCR-required image or scanned-PDF fixture from `tests/input` proves Tesseract fallback, OCR metadata, and quality/finding behavior.
- Document classification is visible in UI output, API output, or redacted terminal evidence through `document_type`, `document_subtype`, confidence/status, and reason codes.
- Unknown, unsupported, low-quality, ambiguous, or pending-suggestion behavior is included when a suitable fixture or controlled request exists.
<!-- M8 - Data Validation Module Start -->
- UI shows parse summary and user-facing M8 transaction check results, with raw M5/M7/M8 details hidden behind a developer detail view.
<!-- M8 End -->
- Evidence uses approved TestData.
- Cleanup expectations are stated before the run; temporary uploads, records, or recognition suggestions are removed where practical, and retained artefacts are documented.

OCR-specific regression must use real approved files from `tests/input` inside the `stats-runtime` container. Tests that verify OCR behavior, OCR classification, OCR orientation retry, or OCR quality must not use generated PDFs/images, fake image bytes, monkeypatched OCR output, or synthetic OCR text as acceptance evidence. Mocks remain acceptable only for dependency-state/error-path checks that do not claim OCR extraction quality, such as simulating unavailable Tesseract or an unavailable PDF renderer.

<!-- Review Hardening - 2026-06-02 Start -->
When a real-file parsing test is run outside the official container path and no approved fixture directory is configured, the test may skip with an explicit message so developer diagnostics do not fail for a missing local setup. When `STATS_PARSING_TESTDATA_DIR` or `STATS_TESTDATA_DIR` is configured, missing directories or required files must fail fast. Inside `stats-runtime`, the official runner sets those variables to `/app/tests/input`, so missing real fixtures remain a hard failure for acceptance evidence.
<!-- Review Hardening - 2026-06-02 End -->

OCR-specific regression should cover:

- EXIF orientation correction for JPEG inputs when EXIF metadata is present.
- 0/90/180/270 retry when EXIF metadata is absent, wrong, or insufficient.
- Multiple Tesseract PSM attempts for image layouts that are not normal paragraphs.
- Selection of the strongest OCR attempt using confidence and text-quality scoring.
- Early-stop behavior for image OCR when a candidate already has strong amount, date/time, and document-shape evidence, with continued retry for weak, damaged, or conflicting labelled-amount results.
- Real receipt-photo OCR regression for low-contrast thermal receipt rows, including terminal date/time and payment amount evidence.
- Propagation of OCR quality metadata and findings for downstream M7 evaluation.
- OCR word block output for scanned PDFs and images, including text, confidence, page number, and bounding boxes. M5 owns producing layout evidence; M7 owns interpreting it as tables.

Regression test selection:

| Condition | Regression Scope |
| --- | --- |
| M5 code/config/contract changes only | Run M5 tests inside `stats-runtime` plus affected container evidence. |
| Stats Web upload/orchestration changes | Run targeted Stats Web orchestration/build checks inside `stats-runtime` plus container app-flow evidence. |
| M13 runtime dependency changes | Run M13 containerization contract and Docker acceptance checks. |
| Unrelated module unchanged | Do not rerun unrelated module tests. |
| Explicit end-to-end regression requested | Run full cross-module workflow evidence. |

## Acceptance Criteria

M5 is complete when:

- The approved spec exists before implementation.
- `modules/document-parsing-module/` contains the standalone runtime, configuration, README, and tests.
- `/health` exposes OCR readiness.
- `/api/v1/parses` returns the documented Document Parsing Result.
- Direct PDF text extraction works for text-layer PDFs.
- Tesseract OCR works for image inputs and scanned/no-text PDFs when configured.
- JPEG/image OCR handles EXIF orientation, retries alternate rotations, and records OCR quality metadata.
- JPEG/image OCR avoids unnecessary full-matrix retries when a strong candidate is found, and records selected variant, early-stop status, early-stop reason, amount-coherence status, amount-coherence score, and amount-conflict reasons.
- JPEG/image OCR includes a conservative document-crop variant for photos where receipt/page boundaries are visible against background clutter.
- OCR-disabled and OCR-unavailable states return explicit findings.
- Classification output is included in the parse result.
- Classification output includes `document_type`, `document_subtype`, confidence, status, reason codes, and diagnostic scores where available.
- M5 uses M9 active recognition settings and does not mutate committed JSON files or in-image configuration at runtime.
- Evaluation metadata is present and measurable.
- Evidence previews are redacted.
<!-- M8 - Data Validation Module Start -->
- Stats Web can automatically validate, ingest, parse, extract, validate, and display the user-facing M8 transaction check results.
<!-- M8 End -->
- Tests use the approved TestData directory.
- M13 runtime alignment is documented for portable Tesseract/OCR support.

## Deferred Items

- Transaction extraction and financial field structuring belong to the next transaction processing module.
- Database persistence of parse results belongs to Stats Data and Persistence.
- Full production/cloud deployment belongs to M13/M14.
- Evaluation reports and ground-truth scoring belong to M15.

<!-- M5/M6 End -->
