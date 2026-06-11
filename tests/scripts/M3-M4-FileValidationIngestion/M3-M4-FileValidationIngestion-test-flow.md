<!-- M3/M4 - File Validation and Ingestion Start -->
<!-- Defines the targeted M3/M4 acceptance test flow for future Docker-based evidence runs. -->

# M3/M4 File Validation and Ingestion Test Flow

## Purpose

This flow defines the targeted acceptance path for **M3 - File Validation** and **M4 - File Ingestion**. It is a test-flow specification only; do not treat this document as evidence that the flow has been run.

M3/M4 evidence must prove that the Stats intake boundary validates uploaded documents automatically, rejects invalid files with clear findings, queues accepted files for the next processing step, and handles duplicate submissions without creating a second active ingestion record for the same file hash or idempotency key.

The primary evidence path is the actual Stats app user journey. A reviewer should be able to see the same actions a normal user would take: open the app, sign in, go to Upload documents, drag/drop or browse for a document, and read the resulting validation/ingestion state in the UI.

## Runtime Target

Official M3/M4 evidence after M13 must use the Docker runtime where practical:

```text
Stats Web: http://127.0.0.1:8080
M3/M4 internal API: http://localhost:8014 inside stats-runtime
```

Host-side `uvicorn`, direct local module runs, browser checks outside the containerized Stats runtime, and direct API-only checks may be used only as diagnostics or supporting evidence. They must be labelled as non-acceptance evidence unless the normal user-facing Stats app flow is blocked and the blocker is explicitly recorded.

## Evidence Folder Pattern

Use a dated root evidence folder:

```text
tests/results/M3-M4-FileValidationIngestion-DockerAcceptance-YYYY-MM-DD/
```

Expected files when this flow is executed:

- `M3-M4-FileValidationIngestion-test-results-YYYY-MM-DD.md`
- `M3-M4-FileValidationIngestion-test-raw-output-YYYY-MM-DD.txt`
- `M3-M4-FileValidationIngestion-manual-test-checklist.md`
- `M3-M4-FileValidationIngestion-screenshot-evidence-YYYY-MM-DD.md`
- `M3-M4-FileValidationIngestion-reviewer-walkthrough-YYYY-MM-DD.md`
- `M3-M4-FileValidationIngestion-windows-terminal-test-YYYY-MM-DD.png`
- actual visible Windows Edge screenshots for every browser route/state listed in this flow

## Credential Rules

- Do not print passwords, bearer tokens, connection strings, tenant IDs, subscription IDs, or secret values in chat, raw output, screenshots, or Markdown evidence.
- Admin or user credentials may be used only if already configured through the runtime environment, container secrets, Key Vault, or an approved temporary evidence seed.
- If credentials are unavailable, record the browser-login blocker and continue only with clearly labelled container/API proof for M3/M4.
- If first-login password setup appears for a shared admin account, do not change it unless the user explicitly approves the credential-state mutation.
- If a temporary evidence user is created, remove or deactivate it after the flow where practical and record cleanup status.

## Required Chat Progress Updates During A Run

When this flow is executed through Codex or another assistant, post concise progress updates after each major state:

1. Docker runtime health verified or failed.
2. Login page verified.
3. Credential availability checked without disclosing secrets.
4. Upload page reached or browser-login blocker recorded.
5. Drag-and-drop zone verified on `/Upload`.
6. Real accepted fixture uploaded or submitted.
7. Validation acceptance state verified.
8. Ingestion queued state verified.
9. Unsupported or intentionally invalid fixture rejected.
10. Duplicate/idempotent re-upload verified.
11. `/Documents` or status lookup checked, depending on whether persistence is in scope.
12. Terminal/raw-output evidence captured.
13. Evidence index and reviewer walkthrough written.
14. Cleanup completed or cleanup gap recorded.

## Fixtures

Use real files from `tests/input` for positive coverage. Preferred fixture classes:

- Real PDF: any supported `.pdf` fixture, such as a bank statement sample.
- Real image: any supported `.jpg`, `.jpeg`, or `.png` fixture when image validation is in scope.
- Invalid fixture: a controlled unsupported file such as `.txt`, empty file, or intentionally mismatched extension/signature file created only for the evidence run.

Do not copy full document text, OCR output, account numbers, or other sensitive contents into Markdown evidence.

## Automated Checks

Run or record the current equivalent Docker/container checks during an evidence run:

```powershell
docker ps
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health
.\tests\scripts\regression\run_module_unit_tests.ps1
```

If the milestone requires full cross-module proof, use:

```powershell
.\tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

Automated checks support the browser/user-flow evidence. They do not replace the normal Stats app interaction.

At minimum, M3/M4 targeted evidence must include raw output for:

- Docker runtime status.
- Stats Web `/health` returning HTTP `200`.
- M3/M4 service health through the container runtime.
- `POST /api/v1/files/validate` accepted result for a real PDF or image from `tests/input`.
- `POST /api/v1/files/validate` rejected result for an unsupported, empty, oversized, or mismatched fixture.
- `POST /api/v1/ingestions` queued result for an accepted validation.
- Duplicate/idempotency result for the same accepted file hash or idempotency key.
- `GET /api/v1/ingestions/{ingestion_id}` status lookup for the created ingestion record.

## Browser Flow

This is the primary acceptance flow. Use the actual Stats app through normal user interactions, not direct DOM manipulation as the main proof. Use actual visible Windows Edge screenshots with the address bar visible. Do not use rendered-response screenshots as browser evidence.

| Step | Route / State | Expected Result | Required Screenshot |
| --- | --- | --- | --- |
| 1 | `/health` | Stats Web health returns healthy status from `http://127.0.0.1:8080/health`. | `M3-M4-windows-browser-health-YYYY-MM-DD.png` |
| 2 | `/Login` | Login page renders as unauthenticated entry point. | `M3-M4-windows-browser-login-YYYY-MM-DD.png` |
| 3 | Login or credential blocker | Authenticated user reaches the shell, or blocker is documented without exposing secrets. | `M3-M4-windows-browser-authenticated-shell-YYYY-MM-DD.png` or blocker note |
| 4 | `/Upload` initial state | Upload page renders, shows the drop zone, and has no manual validation button. | `M3-M4-windows-browser-upload-initial-YYYY-MM-DD.png` |
| 5 | Drag-and-drop target | Drop zone is visible and labelled for PDF, PNG, JPG, or JPEG files. | `M3-M4-windows-browser-drop-zone-YYYY-MM-DD.png` |
| 6 | Accepted real fixture | User browses for or drops a real fixture; validation starts automatically and shows selected file metadata. | `M3-M4-windows-browser-accepted-selected-file-YYYY-MM-DD.png` |
| 7 | Validation accepted | UI shows accepted validation state, detected type, extension, size, and no validation issues. | `M3-M4-windows-browser-validation-accepted-YYYY-MM-DD.png` |
| 8 | Ingestion queued | UI shows ingestion id, `queued` status, workflow, submitted-by/session context, and handoff reference or processing state. | `M3-M4-windows-browser-ingestion-queued-YYYY-MM-DD.png` |
| 9 | Invalid fixture rejected | Unsupported or invalid file is rejected automatically and shows a user-facing rejection message/finding. | `M3-M4-windows-browser-validation-rejected-YYYY-MM-DD.png` |
| 10 | Duplicate re-upload | Re-uploading the same accepted fixture shows duplicate/idempotency handling instead of a second independent queued record. | `M3-M4-windows-browser-duplicate-YYYY-MM-DD.png` |
| 11 | `/Documents` or status lookup | If later modules create a persisted document record, `/Documents` shows it; otherwise M4 status lookup is used and the limitation is documented. | `M3-M4-windows-browser-documents-or-status-YYYY-MM-DD.png` |

## API Flow

Use the API flow only as supporting proof beside the browser flow, or as a clearly labelled fallback when browser authentication or another app-level blocker prevents the normal user path from completing:

1. Copy a real fixture from `tests/input` into `stats-runtime`.
2. Call `POST http://localhost:8014/api/v1/files/validate` inside `stats-runtime`.
3. Confirm `status=accepted`.
4. Confirm metadata includes normalized filename, size, extension, detected MIME type, and SHA-256 hash when enabled.
5. Call `POST http://localhost:8014/api/v1/ingestions` with `validation_status=accepted`, validation hash, source context, and the same file.
6. Confirm `status=queued`, an `ingestion_id`, validation summary, and handoff metadata.
7. Call `GET http://localhost:8014/api/v1/ingestions/{ingestion_id}` and confirm the same queued record is returned.
8. Submit an unsupported or invalid fixture to validation and confirm `status=rejected` with the expected finding code.
9. Re-submit the same accepted file hash or idempotency key to ingestion and confirm `status=duplicate` with `DUPLICATE_SUBMISSION`.

## Reviewer Walkthrough Requirements

Create `M3-M4-FileValidationIngestion-reviewer-walkthrough-YYYY-MM-DD.md` with this structure:

```markdown
# M3/M4 File Validation and Ingestion Reviewer Walkthrough - YYYY-MM-DD

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
```

Each reviewer check should say exactly what to look for, for example:

- address bar shows `http://127.0.0.1:8080/Upload`
- drop zone is visible and labelled for supported document files
- validation starts automatically after file selection or drop
- accepted result shows detected type, extension, size, and no validation issues
- rejected result shows a controlled finding such as `UNKNOWN_SIGNATURE` or `UNSUPPORTED_EXTENSION`
- ingestion result shows `queued`, ingestion id, workflow, and handoff metadata
- duplicate result shows `duplicate` and `DUPLICATE_SUBMISSION`
- no secrets, bearer tokens, raw connection strings, or full private document contents appear

## Pass / Fail Criteria

Pass only when:

- Docker runtime health is verified.
- Login route is visible.
- Upload route is reached through valid authentication and the actual Stats app user flow is completed; if this is impossible, the result is not a full user-flow pass and must record the precise blocker plus supporting API proof.
- Drop zone is visible on the upload page.
- Validation runs automatically after browse or drop; no separate validation button is required.
- At least one real `tests/input` PDF or image is accepted.
- At least one unsupported or intentionally invalid fixture is rejected with a clear finding.
- Accepted file ingestion returns a queued record and status lookup succeeds.
- Duplicate/idempotent submission behavior is visible in the UI. API proof may support this, but should not replace it unless a blocker is documented.
- `/Documents` is checked when persistence is in scope, or explicitly marked out of M3/M4 scope when only ingestion handoff exists.
- Raw output, terminal screenshot, screenshot evidence index, and reviewer walkthrough are created during the evidence run as support for the browser-user journey.
- Temporary files, temporary users, and temporary records are cleaned up where practical.

Fail when:

- `stats-runtime` is unavailable.
- `/health` does not return HTTP `200`.
- Login page cannot render.
- Upload page cannot be reached with valid configured credentials and no API fallback is provided.
- Validation requires a manual button.
- Supported real PDF/image fixtures are rejected without an expected policy reason.
- Invalid fixtures are accepted.
- Accepted files do not produce an ingestion id or queued/duplicate status.
- Duplicate submission creates an unrelated active queued record for the same idempotency key/hash.
- Evidence screenshots do not show actual visible browser windows with the address bar.
- Evidence is API-only even though the normal Stats app user path was available.
- Secrets or full private document contents appear in output or evidence.

## Cleanup

- Close temporary browser windows/profiles opened only for evidence.
- Clear browser session storage/cookies used for the evidence profile.
- Remove controlled invalid fixtures created only for the run.
- Remove temporary files copied into `stats-runtime` where practical.
- Remove or deactivate any temporary evidence user where practical.
- Remove persisted document records only when they were created by this evidence run and cleanup is supported by the app/API.
- Do not stop a Docker stack that was already running before the test unless the user asked for that cleanup.
- Record whether ingestion records remain in memory or persisted storage and why.

<!-- M3/M4 End -->
