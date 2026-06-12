<!-- M7 - Transaction Extraction Test Flow Start -->
<!-- Defines the targeted M7 acceptance test flow for future Docker-based evidence runs. -->

# M7 Transaction Extraction Test Flow

## Purpose

This flow defines the targeted acceptance path for **M7 - Transaction Extraction**. It is a test-flow specification only; do not treat this document as evidence that the flow has been run.

M7 evidence must prove that transaction extraction works as the handoff between M5 parsing/OCR/classification and M8 validation:

- M7 consumes M5 parsed text, page/source context, document classification, quality metadata, and parse findings.
- M7 does not rerun Tesseract when M5 already supplied usable text or OCR output.
- M7 returns transaction candidates, document-level financial fields, section/source metadata, entities, references, line items, reconciliation metadata, confidence, and finding codes.
- M7 classifies transaction type and spending category using the same layered recognition pattern as M5: approved settings/rules first, optional AI-assisted fallback only when deterministic classification is weak, ambiguous, or unknown.
- Stats Web shows M7 output as part of the upload processing flow and passes candidates into M8 validation/review.

Acceptance evidence for M7 must be captured through an actual run of the Stats app using the normal browser workflow a user would follow. API, database, and terminal outputs are supporting evidence only; they must not replace the visible user-flow proof unless the user-facing flow is blocked and the blocker is documented.

## Runtime Target

Official M7 evidence after M13 must use the Docker runtime where practical:

```text
http://127.0.0.1:8080
```

M7 runs inside the `stats-runtime` container on internal port `8016`. Host-side `pytest`, direct Uvicorn runs, or local sibling-service orchestration may be used only as diagnostics and must be labelled as non-acceptance evidence.

## Evidence Folder Pattern

Use a dated root evidence folder:

```text
tests/results/M7-TransactionExtraction-DockerAcceptance-YYYY-MM-DD/
```

Expected files:

- `M7-TransactionExtraction-test-results-YYYY-MM-DD.md`
- `M7-TransactionExtraction-test-raw-output-YYYY-MM-DD.txt`
- `M7-TransactionExtraction-manual-test-checklist.md`
- `M7-TransactionExtraction-screenshot-evidence-YYYY-MM-DD.md`
- `M7-TransactionExtraction-reviewer-walkthrough-YYYY-MM-DD.md`
- `M7-TransactionExtraction-windows-terminal-test-YYYY-MM-DD.png`
- actual visible Windows Edge screenshots for every route/state listed in this flow

The screenshot evidence set is the primary evidence set. Raw output files explain and support what happened behind the UI, but a raw API or terminal-only run is not a completed M7 user-flow acceptance pass.

## Credential And Privacy Rules

- Do not print passwords, bearer tokens, connection strings, tenant IDs, subscription IDs, or secret values in chat, raw output, screenshots, or Markdown evidence.
- Do not paste full raw OCR text, full raw module JSON, full account identifiers, or unmasked reference numbers into Markdown evidence.
- Use redacted previews, counts, status fields, finding codes, quality metadata, confidence values, and reviewer-safe snippets.
- Admin credentials may be used only if they are already configured through the runtime environment, container secrets, Key Vault, or an approved test seed.
- If login credentials are missing, record a blocker and continue only with clearly labelled container/API proof.

## Required Chat Progress Updates During A Run

When this flow is executed through Codex or another assistant, post concise progress updates after each major state:

1. Docker runtime health verified or failed.
2. Login page verified.
3. Upload page verified.
4. Real transaction-bearing fixture selected from `tests/input`.
5. Upload accepted by M3/M4 or blocker recorded.
6. M5 parse/OCR completion state recorded.
7. M5-to-M7 handoff context recorded without exposing full OCR text.
8. M7 extraction completion state recorded.
9. Transaction candidates, financial fields, source/section metadata, confidence, and findings inspected.
10. Transaction type and spending category classification inspected.
11. No-transaction, ambiguous, unknown, or low-confidence scenario inspected or fixture gap recorded.
12. M8 validation/review handoff inspected.
13. Terminal/API/raw-output supporting evidence captured.
14. Evidence index and reviewer walkthrough with embedded screenshots written.
15. Cleanup completed or cleanup gap recorded.

## Automated Checks

Run or record the current equivalent Docker/container checks during an evidence run:

```powershell
docker ps
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health
.\tests\scripts\regression\run_module_unit_tests.ps1
pytest tests\integration\test_stats_web_orchestration_config.py
```

At minimum, M7 targeted evidence must include supporting raw output for:

- Docker runtime status.
- `GET /health` returning HTTP `200`.
- M7 unit/API checks running through `stats-runtime`.
- Upload orchestration configuration checks when the browser checkpoint is part of the assertion.
- Any direct M7 API call used to explain a no-transaction, ambiguous, low-confidence, unknown, or AI-assisted classification state that was also visible in the app or blocked from becoming visible.

## Browser Flow

Use actual visible Windows Edge screenshots with the address bar visible. Do not use rendered-response screenshots as browser evidence.

This browser flow is the acceptance flow. A run does not pass M7 acceptance unless the reviewer can follow what the user did in the live Stats app and see transaction extraction results in the app or a clearly documented UI blocker with supporting container/API proof.

| Step | Route / State | Expected Result | Required Screenshot |
| --- | --- | --- | --- |
| 1 | `/health` | Stats Web health returns healthy status from `http://127.0.0.1:8080/health`. | `M7-TransactionExtraction-windows-browser-health-YYYY-MM-DD.png` |
| 2 | `/Login` | Login page renders as unauthenticated entry point. | `M7-TransactionExtraction-windows-browser-login-YYYY-MM-DD.png` |
| 3 | Authenticated `/Upload` | Upload documents route renders for an authenticated user. | `M7-TransactionExtraction-windows-browser-upload-empty-YYYY-MM-DD.png` |
| 4 | Real fixture selected | A transaction-bearing fixture from `tests/input` is selected. | `M7-TransactionExtraction-windows-browser-upload-selected-YYYY-MM-DD.png` |
| 5 | Processing state | Plain-language upload steps show file accepted, document uploaded, text read/OCR completed by M5, and transaction extraction started or completed. | `M7-TransactionExtraction-windows-browser-processing-YYYY-MM-DD.png` |
| 6 | M5 handoff state | Output or supporting evidence shows M7 consumed M5 parse text, classification, quality metadata, page/source context, and findings. | `M7-TransactionExtraction-windows-browser-m5-handoff-YYYY-MM-DD.png` or supporting output |
| 7 | Transaction extraction results | M7 output shows transaction candidates with date when available, description, amount, currency when available, direction or transaction type, source/section context, confidence, and findings. | `M7-TransactionExtraction-windows-browser-transactions-YYYY-MM-DD.png` |
| 8 | Required MVP labels | Document type, transaction type, and spending category are present or marked review-required when missing, unknown, ambiguous, or low-confidence. | `M7-TransactionExtraction-windows-browser-classification-YYYY-MM-DD.png` |
| 9 | Supporting extracted data | Document-level financial fields, sections, entities, references, line items, reconciliation metadata, and redacted snippets are available when present in the fixture. | `M7-TransactionExtraction-windows-browser-extracted-data-YYYY-MM-DD.png` |
| 10 | Negative or needs-review fixture | A no-transaction, ambiguous, low-confidence, or unknown fixture produces visible findings and does not create ready-to-save transaction rows without required fields. | `M7-TransactionExtraction-windows-browser-needs-review-YYYY-MM-DD.png` or fixture-gap note |
| 11 | M8 handoff | M8 validation/review state consumes M7 candidates and shows normalized rows, review blockers, or precise not-ready behavior. | `M7-TransactionExtraction-windows-browser-m8-handoff-YYYY-MM-DD.png` |

## M5 Handoff Checks

M7 must use M5 output as the input boundary. During evidence execution, confirm:

- M5 selected direct text extraction, OCR, or another parse method before M7 ran.
- M7 received M5 text or page blocks, not the original binary file as its primary input.
- M7 preserved M5 quality signals such as low text, OCR disabled, OCR failure, weak OCR, noisy text, or low token confidence as input-quality findings.
- M7 did not invoke Tesseract again for a normal M5 OCR result.
- Full raw OCR text is not copied into reviewer Markdown; use counts, snippets, page numbers, section names, and finding codes instead.

## Required Field Gate

For MVP reporting, the flow must treat these as required before a transaction can be saved:

- M5 document type.
- M7 transaction type.
- M7 spending category.

If any required field is missing, unknown, unsupported, ambiguous, or below the configured confidence threshold, the transaction should be visible as review-required before M9 persistence. M7 should keep the candidate and evidence intact, while M8/M9 prevent an unreviewed save according to their module responsibilities.

## Supporting M7 API Flow

When UI fixtures do not naturally trigger every M7 extraction state, include direct container/API output as supporting evidence only. It can explain M7 internals, but it cannot by itself satisfy the user-flow acceptance requirement.

```text
POST http://127.0.0.1:8016/api/v1/extractions
```

The request should be derived from a real M5 fixture flow or a minimal M5-shaped controlled payload. Evidence must show only redacted or summary-safe output for:

- `extraction_id`
- `status`
- transaction candidate count
- financial field candidate count
- section/entity/reference/line-item counts
- transaction type and spending category status counts
- confidence range or low-confidence count
- finding codes
- source section/page/line identifiers
- M8 handoff payload shape

## Reviewer Walkthrough Requirements

Create `M7-TransactionExtraction-reviewer-walkthrough-YYYY-MM-DD.md` with this structure:

```markdown
# M7 Transaction Extraction Reviewer Walkthrough - YYYY-MM-DD

## Runtime
- Base URL:
- Container:
- Evidence folder:

## Flow Result
- Overall result:
- Gaps/blockers:
- Cleanup status:

## Step-by-Step Review
| Step | User State | Route/API | Screenshot/Output | Reviewer Check |
| --- | --- | --- | --- | --- |

## Embedded Screenshots
### Step name
![Step name](screenshot-file-YYYY-MM-DD.png)

- Reviewer check:
- Result / comment:
```

The `Embedded Screenshots` section is required. Embed every browser and terminal screenshot inline with Markdown image syntax so the reviewer can inspect the evidence without opening each image separately.

Every embedded screenshot must be visually checked before the walkthrough is marked passed. The expected result for that step must be readable in the screenshot itself, such as M5 parse completion, transaction extraction results, transaction rows, document-level extracted fields, review-gated labels, M8 handoff, or terminal `Result: PASSED`. If the expected result is not visible, retake the screenshot or add a dedicated result screenshot.

Each reviewer check should say exactly what to look for, for example:

- address bar shows `http://127.0.0.1:8080/Upload`
- upload result reaches transaction extraction after M5 parse/OCR
- M7 output has transaction rows and document-level extracted fields
- source organization shows page, section, line, or redacted snippet context
- document type, transaction type, and spending category are present or review-gated
- ambiguous/no-transaction output produces findings instead of silent success
- M8 review state consumes M7 candidates

## Pass / Fail Criteria

Pass only when:

- Docker runtime health is verified.
- The Upload page reaches M7 extraction for a real transaction-bearing fixture.
- M7 demonstrably consumes M5 parse/OCR output and does not rerun OCR for normal M5 OCR results.
- UI or documented supporting output shows transaction candidates with required amount/description/source metadata and date when available.
- UI or documented supporting output shows document-level financial fields, source/section metadata, confidence, and findings.
- Document type, transaction type, and spending category are present or review-gated when missing, unknown, ambiguous, unsupported, or low-confidence.
- A no-transaction, ambiguous, unknown, or low-confidence scenario is exercised, or the missing fixture is recorded as a gap with supporting controlled API proof.
- M8 handoff is visible or blocked with a precise documented reason.
- Raw output, terminal screenshot, screenshot evidence index, and reviewer walkthrough with embedded screenshots and visible-result checks are created.
- Temporary uploaded documents/records are cleaned up where practical.

Fail when:

- `stats-runtime` is unavailable.
- `/health` does not return HTTP `200`.
- Upload cannot reach M7 extraction for a valid fixture.
- M7 reruns OCR instead of using normal M5 OCR output.
- M7 output omits required source organization or confidence/finding metadata.
- Required document type, transaction type, or spending category gaps are allowed to proceed as save-ready without review.
- A no-transaction or ambiguous case silently succeeds without findings.
- M8 handoff is absent and not documented as a blocker.
- Evidence screenshots do not show actual visible browser windows with the address bar.
- Evidence screenshots do not visibly show the expected extraction or handoff result for their step.
- The run relies on API, database, or terminal output as the primary acceptance evidence instead of the normal Stats app user flow.
- Secrets, full raw OCR text, or unredacted sensitive identifiers appear in output or evidence.

## Cleanup

- Remove temporary uploaded documents, processing records, recognition suggestions, review records, and saved transactions through the app/API where supported.
- Record any retained documents, transactions, processing jobs, blobs, local files, or recognition suggestions that could not be cleaned up.
- Do not stop a Docker stack that was already running before the test unless the user asked for that cleanup.
- Record whether the Docker stack was reused, started, or left running.

<!-- M7 End -->
