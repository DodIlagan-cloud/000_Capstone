<!-- M8 - Data Validation Test Flow Start -->
<!-- Defines the targeted M8 acceptance test flow for future Docker-based evidence runs. -->

# M8 Data Validation Test Flow

## Purpose

This flow defines the targeted acceptance path for **M8 - Data Validation**. It is a test-flow specification only; do not treat this document as evidence that the flow has been run.

M8 evidence must prove that the validation checkpoint works as the quality gate between M7 extraction and M9 persistence:

- M8 accepts M7-shaped transaction, financial-field, section, entity, reference, line-item, and reconciliation candidates.
- M8 returns normalized records, validation findings, review items, document review status, and recommended action.
- Stats Web shows M8 output as a user-facing transaction check checkpoint, not raw JSON.
- Database duplicate checks and final save behavior remain M9 responsibilities, with M8 output supplied as the pre-save payload.

Acceptance evidence for M8 must be captured through an actual run of the Stats app using the normal browser workflow a user would follow. API, database, and terminal outputs are supporting evidence only; they must not replace the visible user-flow proof unless the user-facing flow is blocked and the blocker is documented.

## Runtime Target

Official M8 evidence after M13 must use the Docker runtime where practical:

```text
http://127.0.0.1:8080
```

Host-side `pytest`, direct Uvicorn runs, or local sibling-service orchestration may be used only as diagnostics and must be labelled as non-acceptance evidence.

## Evidence Folder Pattern

Use a dated root evidence folder:

```text
tests/results/M8-DataValidation-DockerAcceptance-YYYY-MM-DD/
```

Expected files:

- `M8-DataValidation-test-results-YYYY-MM-DD.md`
- `M8-DataValidation-test-raw-output-YYYY-MM-DD.txt`
- `M8-DataValidation-manual-test-checklist.md`
- `M8-DataValidation-screenshot-evidence-YYYY-MM-DD.md`
- `M8-DataValidation-reviewer-walkthrough-YYYY-MM-DD.md`
- `M8-DataValidation-windows-terminal-test-YYYY-MM-DD.png`
- actual visible Windows Edge screenshots for every route/state listed in this flow

The screenshot evidence set is the primary evidence set. Raw output files explain and support what happened behind the UI, but a raw API or terminal-only run is not a completed M8 user-flow acceptance pass.

## Credential And Privacy Rules

- Do not print passwords, bearer tokens, connection strings, tenant IDs, subscription IDs, or secret values in chat, raw output, screenshots, or Markdown evidence.
- Do not paste full raw OCR text or full raw module JSON into Markdown evidence.
- Use redacted previews, counts, status fields, finding codes, and reviewer-safe snippets.
- Admin credentials may be used only if they are already configured through the runtime environment, container secrets, Key Vault, or an approved test seed.
- If login credentials are missing, record a blocker and continue only with clearly labelled container/API proof.

## Required Chat Progress Updates During A Run

When this flow is executed through Codex or another assistant, post concise progress updates after each major state:

1. Docker runtime health verified or failed.
2. Login page verified.
3. Upload page verified.
4. Real fixture selected from `tests/input`.
5. Upload accepted by M3/M4 or blocker recorded.
6. M5 parse/OCR completion state recorded.
7. M7 extraction completion state recorded.
8. M8 transaction validation checkpoint visible.
9. Review queue, ready rows, and reconciliation state inspected.
10. Duplicate scenario inspected through the app UI where available, with API/database proof used only as supporting detail or a documented blocker.
11. Review edit/accept behavior inspected or blocker recorded.
12. Save-ready or duplicate-blocked final state inspected.
13. Documents/Reports result inspected when saved data is expected.
14. Terminal/API/raw-output supporting evidence captured.
15. Evidence index and reviewer walkthrough with embedded screenshots written.
16. Cleanup completed or cleanup gap recorded.

## Automated Checks

Run or record the current equivalent Docker/container checks during an evidence run:

```powershell
docker ps
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health
.\tests\scripts\regression\run_module_unit_tests.ps1
pytest tests\integration\test_stats_web_orchestration_config.py
```

At minimum, M8 targeted evidence must include supporting raw output for:

- Docker runtime status.
- `GET /health` returning HTTP `200`.
- M8 unit/API checks running through `stats-runtime`.
- Upload orchestration configuration checks when the browser checkpoint is part of the assertion.
- Any direct M8 API call used to explain duplicate, low-confidence, or review-item behavior that was also visible in the app or blocked from becoming visible.

## Browser Flow

Use actual visible Windows Edge screenshots with the address bar visible. Do not use rendered-response screenshots as browser evidence.

This browser flow is the acceptance flow. A run does not pass M8 acceptance unless the reviewer can follow what the user did in the live Stats app and see the validation result in the app.

| Step | Route / State | Expected Result | Required Screenshot |
| --- | --- | --- | --- |
| 1 | `/health` | Stats Web health returns healthy status from `http://127.0.0.1:8080/health`. | `M8-DataValidation-windows-browser-health-YYYY-MM-DD.png` |
| 2 | `/Login` | Login page renders as unauthenticated entry point. | `M8-DataValidation-windows-browser-login-YYYY-MM-DD.png` |
| 3 | Authenticated `/Upload` | Upload documents route renders for an authenticated user. | `M8-DataValidation-windows-browser-upload-empty-YYYY-MM-DD.png` |
| 4 | Real fixture selected | A transaction-bearing fixture from `tests/input` is selected. | `M8-DataValidation-windows-browser-upload-selected-YYYY-MM-DD.png` |
| 5 | Processing state | Plain-language upload steps show file accepted, document uploaded, text read, and transactions checked. | `M8-DataValidation-windows-browser-processing-YYYY-MM-DD.png` |
| 6 | Transaction check results | M8 checkpoint shows transactions found, ready to save, needs review, and saved count where available. | `M8-DataValidation-windows-browser-validation-summary-YYYY-MM-DD.png` |
| 7 | Needs-review queue | Review items show user-facing title, message, affected fields, status, and Edit/Accept actions where applicable. | `M8-DataValidation-windows-browser-review-queue-YYYY-MM-DD.png` |
| 8 | Ready rows | Ready/accepted transaction rows show normalized date, posted date when supplied, description, amount, currency, direction, status, and visible Edit action. | `M8-DataValidation-windows-browser-ready-rows-YYYY-MM-DD.png` |
| 9 | Extracted-data toggle | Supporting non-transaction tables are hidden by default and visible only after opening the extracted-data toggle. | `M8-DataValidation-windows-browser-extracted-data-toggle-YYYY-MM-DD.png` |
| 10 | Duplicate handling | Duplicate result is visible through the app's M9 pre-save duplicate check when persistence is in scope; if the UI cannot surface it yet, record a blocker and attach supporting API/database proof separately. | `M8-DataValidation-windows-browser-duplicate-result-YYYY-MM-DD.png` or blocker note |
| 11 | Review correction | User can edit or accept review rows; reconciliation-gated save readiness updates after local changes. | `M8-DataValidation-windows-browser-review-corrected-YYYY-MM-DD.png` |
| 12 | Save result | Save ready transactions either succeeds, resets the upload page for another upload, or shows a precise duplicate/save blocker. | `M8-DataValidation-windows-browser-save-result-YYYY-MM-DD.png` |
| 13 | `/Documents` | Saved document appears when persistence was expected, or no-save/duplicate blocker is documented. | `M8-DataValidation-windows-browser-documents-result-YYYY-MM-DD.png` |
| 14 | `/Reports` | Saved validated data appears in reporting output when persistence was expected, or reporting is marked out of scope for the M8 run. | `M8-DataValidation-windows-browser-reports-result-YYYY-MM-DD.png` |

## Supporting M8 API Flow

When UI fixtures do not naturally trigger every M8 validation state, include direct container/API output as supporting evidence only. It can explain M8 internals, but it cannot by itself satisfy the user-flow acceptance requirement.

```text
POST http://127.0.0.1:8017/api/v1/validations
```

The request should be derived from a real M7 fixture flow or a minimal M7-shaped controlled payload. Evidence must show only redacted or summary-safe output for:

- `validation_id`
- `status`
- normalized record count
- review item count
- finding codes
- same-batch duplicate finding and duplicate reference, when tested
- low-confidence or invalid field finding, when tested
- document review status and recommended action
- reconciliation delta, when tested

## Reviewer Walkthrough Requirements

Create `M8-DataValidation-reviewer-walkthrough-YYYY-MM-DD.md` with this structure:

```markdown
# M8 Data Validation Reviewer Walkthrough - YYYY-MM-DD

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

Every embedded screenshot must be visually checked before the walkthrough is marked passed. The expected result for that step must be readable in the screenshot itself, such as transaction check results, review queue, ready rows, extracted-data toggle, duplicate/save blocker, saved result, `/Documents` state, or terminal `Result: PASSED`. If the expected result is not visible, retake the screenshot or add a dedicated result screenshot.

Each reviewer check should say exactly what to look for, for example:

- address bar shows `http://127.0.0.1:8080/Upload`
- upload result says transaction check results
- review queue shows only items that need attention before the full extracted-data tables
- ready rows remain editable
- duplicate handling is visible before final persistence
- save result gives a precise success, duplicate, or blocker message

## Pass / Fail Criteria

Pass only when:

- Docker runtime health is verified.
- The Upload page reaches the M8 transaction validation checkpoint for a real transaction-bearing fixture.
- UI evidence from the actual Stats app shows normalized dates, descriptions, amount, currency, direction, signed amount behavior, review-required findings, invalid/low-confidence findings, and validation-ready records.
- Duplicate behavior is visible through the app's M9 pre-save flow, or the UI gap is recorded as a blocker with supporting API/database proof.
- Review edit/accept behavior is exercised when supported by the UI.
- Save-ready behavior is exercised and either persists, duplicate-blocks, or records a precise not-ready reason.
- Documents/Reports outcome is verified when saved records are expected.
- Raw output, terminal screenshot, screenshot evidence index, and reviewer walkthrough with embedded screenshots and visible-result checks are created.
- Temporary uploaded documents/records are cleaned up where practical.

Fail when:

- `stats-runtime` is unavailable.
- `/health` does not return HTTP `200`.
- Upload cannot reach the transaction validation checkpoint for a valid fixture.
- M8 output omits required normalized transaction fields.
- Review items or findings are hidden behind raw developer JSON only.
- Duplicate/save behavior returns a generic message without a visible reason.
- Evidence screenshots do not show actual visible browser windows with the address bar.
- Evidence screenshots do not visibly show the expected validation, review, duplicate, save, or document result for their step.
- The run relies on API, database, or terminal output as the primary acceptance evidence instead of the normal Stats app user flow.
- Secrets or unredacted sensitive OCR text appear in output or evidence.

## Cleanup

- Remove temporary uploaded documents and saved transaction records through the app/API where supported.
- Record any retained documents, transactions, duplicate-check rows, processing jobs, blobs, or local files that could not be cleaned up.
- Do not stop a Docker stack that was already running before the test unless the user asked for that cleanup.
- Record whether the Docker stack was reused, started, or left running.

<!-- M8 End -->
