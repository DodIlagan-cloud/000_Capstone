<!-- Cloud-Dev User Flow Evidence Plan Start -->
<!-- Tracks segmented, evidence-driven cloud-dev testing by user-facing function. -->

# Cloud-Dev User Flow Evidence Plan

## Purpose

Cloud-dev evidence must prove the functionality that real Stats users interact with.

The test suite should be segmented by logical user function instead of running one long all-input regression. Each segment must produce reviewable evidence before the next segment starts. API, database, Azure, and terminal checks are supporting proof; the primary proof is the visible Stats Web user journey in the cloud-dev browser.

## Execution Principles

- Run one logical user function at a time.
- Use the cloud-dev URL with the browser address bar visible.
- Use approved fixtures from `tests/input`.
- Capture screenshots, redacted state JSON, raw terminal output, and a short pass/fail/blocker summary for each segment.
- Record elapsed time for each major setup/action/wait step, including long processing waits.
- When a segment creates or consumes a document-processing job, include the product's own `document_processing_steps` timings in the segment result.
- Stop after a failed segment when the failure invalidates later evidence.
- Prefer one known fixture first. Expand to more fixtures only after the single-fixture journey is proven.
- Do not print passwords, tokens, connection strings, full OCR text, tenant IDs, or subscription-sensitive values.
- Reset or clean up cloud-dev data between scenarios when duplicate state would affect the next result.
- Treat Segment 1 as the canonical login/navigation evidence. Later segments should still authenticate as needed, but should not recapture login pages unless authentication, role switching, session expiry, or access control is the specific behavior under test.
- Reuse an existing browser/session between segments whenever possible. Each segment should first attach to the shared evidence browser, check whether the required session/user is already authenticated, and navigate to the segment function. Launch a new browser only when no shared session is available.
- Do not use the local Docker runtime for cloud-dev user-flow segments. The cloud test path is the live Container App, Azure SQL, Key Vault, Azure resource checks, and the shared evidence browser.

## Evidence Folder Convention

Each segment should write a separate folder under:

```text
tests/results/CloudDevUserFlows/<segment-name>-YYYY-MM-DD-HHMMSS/
```

The live segment status board and run log are tracked in:

```text
tests/results/CloudDevUserFlows/USER-FLOW-TRACKER.md
```

The versioned tracking rules are documented in:

```text
docs/cloud-dev-user-flow-tracking.md
```

Each folder should contain:

- `walkthrough.md` with embedded screenshots,
- `raw-output.txt`,
- `state-summary.json`,
- cloud-native backend summaries, such as API/Azure SQL count snapshots, when persistence is explicitly in scope,
- product processing-step timings from `document_processing_steps` when document processing is in scope,
- elapsed timing summary for each major segment step,
- screenshots named in execution order,
- cleanup notes.

For segments after Segment 1, walkthroughs should reference the Segment 1 sign-in/navigation evidence as the authentication baseline and start embedded screenshots at the segment-specific UI state. The raw output or state summary should still record the authenticated role and user email.

Browser/session reuse convention:

- Use one shared Edge debugging session for segmented cloud-dev user-flow evidence.
- Keep the browser open between segment runs unless a cleanup/reset segment explicitly closes it.
- Before running a segment, attach to the existing debug session and inspect the current authenticated user.
- If the existing session is already the required user/role, reuse it and navigate directly to the target function.
- If the existing session is missing, expired, or the wrong user/role, switch/sign in silently as setup evidence, without login screenshots unless auth is in scope.
- Record browser/session reuse in `raw-output.txt` or `state-summary.json`; screenshots remain limited to the segment function.

Cloud-vs-local runtime convention:

- Cloud user-flow evidence targets the live Container App and Azure SQL.
- The local `stats-runtime` Docker container is not part of the cloud user journey.
- Do not use Docker as a cloud-dev database helper.
- When backend state is needed, use cloud app APIs, Azure resource checks, or direct Azure SQL diagnostics.
- If direct Azure SQL tooling is unavailable, record that backend diagnostics were not collected rather than falling back to local Docker.

## Segment Tracker

| Order | Segment | Primary User Function | Required Roles | Status | Evidence Target |
| --- | --- | --- | --- | --- | --- |
| 0 | Fresh-state setup | Prepare cloud-dev for user-flow evidence | Operator/Admin bootstrap | Planned | DB counts, `/health`, active revision, admin bootstrap status |
| 1 | Sign in and navigation | Prove role access and route boundaries | Admin and standard user | Planned | Login, navigation, protected route, admin-only route screenshots |
| 2 | Valid document upload | Prove user can upload a real document | Standard user first, admin optional | Planned | `/Upload` accepted/queued state |
| 3 | Processing, review, accept, and save | Prove user sees parse/extraction/validation output, acts on review rows, and saves ready results | Standard user first | Planned | M5/M7/M8 result screenshots, transaction detail, accept/save state, `/Documents`, AI/suggestion status |
| 4 | Edit and accept review items | Merged into Segment 3 for receipt-style parsed documents | Standard user first | Merged | Covered by Segment 3 unless a future scenario needs deeper edit-form evidence |
| 5 | Save transactions | Merged into Segment 3 for receipt-style parsed documents | Standard user first | Merged | Covered by Segment 3 unless a future scenario needs a save-only rerun |
| 6 | Duplicate handling | Prove user sees clear duplicate behavior | Standard user first | Planned | Same-file and same-record duplicate screenshots |
| 7 | Documents management | Prove user can inspect and remove saved records | Owner/user and admin if applicable | Planned | Documents list, detail/remove, empty state |
| 8 | Reports | Prove user-facing reporting loads and reflects saved data or readiness | Admin and/or standard user per product rules | Planned | `/Reports`, KPI/reporting API summary |
| 9 | Final cleanup | Return cloud-dev to a controlled state | Admin/operator | Planned | Post-cleanup counts and optional park status |

Status values should be `Planned`, `Ready`, `Running`, `Passed`, `Passed with classification gap`, `Failed`, `Blocked`, `Deferred`, or `Merged`.

## Segment 0: Fresh-State Setup

Goal: prove the test starts from a controlled cloud-dev state.

Steps:

1. Reset cloud-dev Azure SQL to a fresh-install data state when a clean test is required.
2. Bootstrap one admin user through the approved cloud-dev bootstrap path.
3. Confirm the app is healthy at `/health`.
4. Confirm baseline counts:
   - users: one bootstrap admin,
   - documents: zero,
   - processing jobs: zero,
   - processing steps: zero,
   - transactions: zero.
5. Confirm the active cloud URL and Container App revision without exposing secrets.

Evidence:

- health screenshot,
- redacted database count summary,
- active image/revision summary,
- bootstrap/admin status summary.

Stop condition:

- Do not continue if login credentials are unavailable, the app is unhealthy, or document/job/transaction counts are not clean when the scenario requires a fresh database.

## Segment 1: Sign In And Navigation

Goal: prove cloud-dev access, route visibility, and role boundaries for both admin and standard users.

### Admin Flow

Steps:

1. Open `/Login`.
2. Sign in as the cloud admin.
3. Verify the authenticated home page.
4. Visit normal user routes:
   - `/`,
   - `/Upload`,
   - `/Documents`,
   - `/Reports`.
5. Visit admin-only routes:
   - `/Users` or Manage users,
   - recognition/admin areas when present.
6. Confirm admin-only navigation entries are visible.

Evidence:

- login page screenshot,
- authenticated admin home screenshot,
- admin navigation screenshot,
- route screenshots with cloud URL visible,
- supporting route/API status summary.

### Standard User Setup

Steps:

1. From the admin session, create or confirm a standard test user.
2. Use an approved temporary password source.
3. Record only the email, role, and account status.
4. If first-login password maintenance is required, complete it as part of the flow or record it as a blocker.

Evidence:

- user creation/list screenshot,
- standard user visible with expected role and status,
- redacted user summary.

### Standard User Flow

Steps:

1. Sign out admin.
2. Sign in as the standard user.
3. Verify authenticated home.
4. Visit normal user routes:
   - `/`,
   - `/Upload`,
   - `/Documents`,
   - `/Reports`.
5. Attempt direct access to admin-only routes:
   - `/Users`,
   - recognition/admin areas when present.
6. Confirm admin-only navigation entries are absent or access is blocked.

Evidence:

- standard user login screenshot,
- standard user home/navigation screenshot,
- normal route screenshots,
- blocked admin-route screenshot,
- supporting authorization/API status summary.

Cleanup:

1. Sign back in as admin.
2. Remove, deactivate, or mark the standard test user according to the test cleanup plan.
3. Record final user count/role summary.

## Segment 2: Valid Document Upload

Goal: prove a user can upload a real fixture through the normal UI.

Steps:

1. Sign in as the standard test user unless the scenario is explicitly admin-only.
2. Open `/Upload`.
3. Select one approved fixture from `tests/input`.
4. Confirm validation starts automatically.
5. Confirm the file is accepted or a precise user-facing rejection appears.
6. Confirm ingestion/upload status is visible.

Evidence:

- upload page before file,
- selected filename visible,
- accepted/rejected validation state,
- ingestion/upload status,
- redacted state JSON.
- reference to Segment 1 for sign-in proof instead of repeated login screenshots.

## Segment 3: Processing, Review, Accept, And Save

Goal: prove the user sees cloud processing results after upload, can act on the extracted transaction, and can persist ready results.

Steps:

1. Wait for a stable processing outcome:
   - transaction check results,
   - processing failed,
   - upload stopped,
   - needs review.
2. Confirm visible summary fields:
   - file accepted,
   - document uploaded,
   - text read/OCR state,
   - transactions checked,
   - transactions found,
   - ready vs needs-review rows.
3. Open extracted-data details only enough to prove the UI works, without copying full sensitive text.
4. Capture the actual processed transaction details.
5. Confirm AI/recognition suggestion status from Developer details or backend diagnostics.
6. Accept or edit the review row when the UI allows it.
7. Confirm the row becomes ready to save.
8. Click `Save ready transactions`.
9. Wait for a stable save outcome:
   - transactions saved,
   - duplicate save blocked,
   - possible duplicates need review,
   - transaction save failed,
   - not-ready blocker.
10. Open `/Documents`.
11. Confirm saved records appear when save succeeds.

Evidence:

- stable result screenshot,
- transaction detail screenshot,
- before-accept and after-accept screenshots,
- save result screenshot,
- `/Documents` record list screenshot,
- redacted processing-job state,
- product processing-step timing summary for upload, parsing/OCR, extraction, and validation,
- redacted extraction/validation summary,
- AI/recognition suggestion summary,
- accept/save summary,
- blocker screenshot when processing fails.
- reference to Segment 1 for sign-in proof instead of repeated login screenshots.

If the transaction remains `Unknown` or `Uncategorized` and AI-assisted categorisation was expected, the segment must not be treated as a clean pass. Record it as `Passed with classification gap`, identify whether recognition settings were unavailable, AI was disabled, or no suggestion was created, and add a classification follow-up before duplicate/reporting evidence relies on categorised data.

Cloud-dev classification prerequisites:

- `STATS_INTERNAL_API_KEY` must be configured as a secret-backed Container App env var.
- `RECOGNITION_SETTINGS_URL` must point to the local Stats Data active-settings endpoint.
- `CLASSIFICATION_AI_ENABLED` and `TRANSACTION_CLASSIFICATION_AI_ENABLED` must be `true` in cloud-dev.
- `GEMINI_API_KEY` or the configured provider key must be present as a Container App secret reference.
- The deployed image must include the current M5/M7 AI fallback and skip-reason diagnostics.

## Segment 4: Edit And Accept Review Items

Goal: retained as a named test concept, but merged into Segment 3 for the current receipt flow.

Steps:

1. Do not create a separate review markdown when the Segment 3 parsed document already exposes a review row.
2. Use Segment 3 to capture before-accept and after-accept state.
3. Only run this separately for a scenario that specifically needs edit-form coverage beyond simple accept.

Evidence:

- Segment 3 merged walkthrough, or a future scenario-specific edit-form walkthrough.

## Segment 5: Save Transactions

Goal: retained as a named test concept, but merged into Segment 3 when a parsed document is already ready for save.

Steps:

1. Do not create a separate save markdown when Segment 3 already has a ready parsed transaction.
2. Use Segment 3 to capture save button readiness, save result, and `/Documents` persistence proof.
3. Only run this separately for a scenario that starts with existing ready rows or specifically tests save-only behavior.

Evidence:

- Segment 3 merged walkthrough, or a future scenario-specific save-only walkthrough.

## Segment 6: Duplicate Handling

Goal: prove duplicate behavior is clear to the user.

Steps:

1. Re-upload the exact same file after a fresh save.
2. Confirm same-file duplicate handling.
3. Upload a different file copy that should produce the same transaction fields, when a safe fixture exists.
4. Confirm same-record duplicate handling.
5. Confirm duplicate attempts do not create unintended extra saved records.

Evidence:

- same-file duplicate screenshot,
- same-record duplicate screenshot,
- duplicate message text,
- supporting DB/API counts.

## Segment 7: Documents Management

Goal: prove users can inspect and remove saved document records.

Steps:

1. Open `/Documents`.
2. Confirm saved document rows, transaction counts, and controls are visible.
3. Open detail controls when available.
4. Remove the scenario document through the app-supported path.
5. Reload `/Documents`.
6. Confirm the document is removed or the list is empty.

Evidence:

- documents list,
- detail/remove action,
- post-cleanup empty or updated state,
- supporting DB/API counts.

## Segment 8: Reports

Goal: prove reporting is user-visible and truthful for the current cloud-dev state.

Steps:

1. Open `/Reports`.
2. Confirm the report page loads.
3. If saved data exists, confirm visible reporting/KPI state reflects it.
4. If reporting is not fully wired, capture the configured, empty, or blocked state.

Evidence:

- reports page screenshot,
- redacted reporting API summary,
- Power BI/Fabric proof only as supporting evidence.

## Segment 9: Final Cleanup

Goal: leave cloud-dev in a known state after evidence.

Steps:

1. Delete scenario records through the app/API-supported path where possible.
2. Confirm document, job, transaction, and test-user cleanup state.
3. Park cloud-dev when the user requests cost-saving cleanup.

Evidence:

- cleanup summary,
- final database/API counts,
- optional park status.

## Runner Requirements

Future automation should run one segment per command or expose a segment selector such as:

```powershell
python tests/scripts/regression/run_cloud_dev_user_flow_segment.py --segment sign-in-navigation
python tests/scripts/regression/run_cloud_dev_user_flow_segment.py --segment upload-one --fixture 201810_HSBC.pdf
```

Each runner must:

- print progress before long waits,
- write checkpoints after each screenshot/state capture,
- write per-step elapsed timings to `raw-output.txt`, `state-summary.json`, and the walkthrough,
- perform login/session setup without login-page screenshots after Segment 1 unless auth is part of the segment,
- reuse the shared browser/session when available and leave it open for the next segment,
- keep cloud-dev backend diagnostics cloud-native: app API, Azure resource check, or direct Azure SQL only,
- use separate timeouts for session setup, processing, duplicate check, save, and final UI assertions,
- close the shared browser only during an explicit cleanup/reset step,
- report `PASSED`, `FAILED`, or `BLOCKED` for the segment.

<!-- Cloud-Dev User Flow Evidence Plan End -->
