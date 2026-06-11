<!-- M0 Foundation / M13 Containerization Start -->
<!-- Defines repeatable module-by-module test-flow planning without executing tests. -->

# Module Test Flow Playbook

## Purpose

This playbook defines the expected test flow for each Stats module. It is a planning and review document: updating this file does not mean the tests were run. Actual results must still be captured in `tests/results/` by the relevant Docker, cloud-dev, browser, terminal, or database evidence runner.

From M13 onward, official evidence runs through the Stats Docker runtime first. From M14 onward, cloud-dev evidence should repeat the container-proven flow when the tested behavior is deployed and practical to verify.

## Common Flow

Every module test flow should follow this order:

1. Confirm the module spec, file inventory, and affected contracts.
2. Identify the minimal module tests for the changed behavior.
3. Identify cross-module handoffs that must be proven.
4. Use real files from `tests/input` for document, OCR, extraction, validation, upload, and reporting behavior.
5. Run official module checks through `stats-runtime`, not host-only diagnostics.
6. Capture raw output and screenshots only during an evidence run.
7. Record gaps, blockers, and cleanup status in the evidence summary.
8. Update the module file inventory when a new runner, evidence folder, or acceptance path is added.

## Evidence Conventions

- Official evidence belongs under `tests/results/`.
- Reusable scripts belong under `tests/scripts/`.
- Real source fixtures belong under `tests/input/` and remain uncommitted.
- Primary acceptance evidence must be captured through an actual run of the Stats app, using the normal user-facing flow a user would follow in the browser.
- All module evidence must be captured through an actual run of the Stats app wherever the behavior has a user-facing path. The reviewer should be able to follow the evidence as a normal user journey through the application, not as an isolated API/script-only proof.
- Browser evidence should use the container-exposed app URL, normally `http://127.0.0.1:8080`, with an actual visible Windows Edge window and address bar.
- API, database, and container command output are supporting evidence only unless the user-facing flow is blocked; any fallback must clearly record the blocker and must not be presented as a completed user-flow pass.
- Evidence must not copy full sensitive OCR text, credentials, tokens, connection strings, or unredacted financial identifiers.
- Host-only checks may be listed as diagnostics, but they do not satisfy module acceptance after M13.

## Module Flows

| Module | Primary Flow | Required Proof | Evidence Notes |
| --- | --- | --- | --- |
| M0 Foundation | Inspect specs, contracts, repo conventions, file inventory, and testing policy. | Static contract checks and documentation consistency. | No UI proof unless a foundation change affects the visible app shell. |
| M1 Identity Access | Start container, reach `/Login`, authenticate, verify password-change and admin/user authorization paths. | Container DB/user state, token/session behavior, admin-only access checks. | Browser screenshots should show login and protected page URLs; terminal proof should avoid passwords/tokens. |
| M2 Stats Web Shell | Start container, open core routes, verify same-origin proxy configuration and navigation. | HTTP/browser proof for `/`, `/Upload`, `/Documents`, `/Reports`, and route-specific shell data. | Pair static config checks with browser screenshots when UI changed. |
| M3 File Validation | Upload real `tests/input` files through the Stats app UI and validate accepted/rejected states. | Browser-visible accepted PDF/image fixtures and at least one unsupported/invalid fixture when available, supported by API/raw output. | Evidence should show validation status, finding codes, and no raw private document text. |
| M4 File Ingestion | Continue from accepted M3 files through the Stats app UI into ingestion/storage handoff. | Browser-visible ingestion state, plus ingestion IDs, queued/accepted records, and controlled storage failure behavior where relevant. | Cleanup temporary ingestion records when practical; document anything retained. |
| M5/M6 Document Parsing and Classification | Continue upload flow into M5 parse, direct PDF text extraction, OCR fallback, classification, quality metadata, and downstream handoff readiness. | Text PDF parse, image/scanned OCR parse, document type/subtype or pending suggestion, low-quality/needs-review scenario, M7/M8 handoff state when available. | Use privacy-safe summaries: strategy, method, text length, OCR metadata, confidence, finding codes, and redacted preview counts only. |
| M7 Transaction Extraction | Continue real upload fixtures from M5 parse/OCR output into M7 extraction. | Transaction candidates, document-level financial fields, section/source metadata, transaction type, spending category, confidence, and finding codes. | Show that M7 consumes M5 output and does not rerun OCR; avoid storing full M5 raw text in Markdown. |
| M8 Data Validation | Feed M8 with M7 candidates from real fixture flows. | Normalized records, review items, duplicate/quality findings, and validation status. | Browser evidence should show user-facing review state; raw API evidence should be redacted. |
| M9 Stats Data and Persistence | Persist workflow outputs and query records through Stats Data. | Migration state, database target, persisted documents/transactions/jobs, duplicate checks, and cleanup. | DB evidence must show target database identity and result rows without secrets. |
| M11 Dashboard Reporting | Generate/report read models and verify reporting APIs/UI. | KPI/report data sourced from persisted records, semantic model or reporting query evidence. | Power BI/reporting screenshots must avoid exposing tokens or raw internal error details. |
| M13 Containerization | Build/start Docker runtime and verify packaged services. | `stats-runtime` health, module ports, Tesseract/PyMuPDF availability, and Docker regression path. | This is the official local runtime gate for earlier modules. |
| M14 Cloud Readiness | Repeat container-proven flows against cloud-dev where practical. | Container App health, Azure SQL/storage identity, cloud URL browser proof, and deployment config. | Redact subscription/secrets/connection strings; include concrete cloud endpoint and date. |

<!-- M1 - User Access Management Start -->
## M1 Detailed Flow

The M1 flow should be refined before each evidence run, then executed only when the user explicitly asks for the run. The detailed M1-specific flow lives in `tests/scripts/M1-IdentityAccessManagement/M1-IdentityAccessManagement-test-flow.md`.

M1 acceptance evidence must prove the actual user-facing identity journey through Stats Web, not only direct API calls. API, database, and terminal checks are supporting evidence unless the browser flow is blocked and the blocker is explicitly recorded.

1. Verify the container runtime is expected to be used: `stats-runtime`, `http://127.0.0.1:8080`, and M1 internal API on port `8013`.
2. Confirm the M1 spec, file inventory, identity contract, and current runtime configuration are aligned before testing.
3. Confirm admin credentials are available through approved runtime configuration, Container Apps secrets, Key Vault, or an approved test seed without printing passwords, tokens, or connection strings.
4. If admin credentials are unavailable, record the credential blocker and do not present the authenticated flow as passed.
5. Browser flow: open `/Login` in visible Windows Edge with the address bar visible.
6. Browser flow: admin signs in. If first-login password maintenance is required, complete it only when the evidence run is allowed to mutate the test admin password; otherwise record a credential-state blocker.
7. Browser proof: admin reaches authenticated workspace and admin-only Manage users entry point.
8. Browser flow: admin opens `/Users`, creates a non-admin test user with a temporary password, and verifies the new user appears with expected role and active/password-change state.
9. Database proof: from inside the active runtime path, query the configured database target to show the admin-created user exists without exposing password hashes or secrets.
10. Browser flow: admin signs out.
11. Browser flow: new user signs in, completes forced password maintenance when required, and reaches permitted workspace.
12. Browser proof: non-admin user cannot access `/Users` and does not see admin-only user-management controls.
13. Terminal proof: run the relevant container command or script and capture `Result: PASSED` or `Result: FAILED` only during evidence execution.
14. Cleanup: deactivate/delete the temporary user or reset temporary password state where practical; document anything retained and why.
<!-- M1 End -->

## M2 Detailed Flow

The M2 flow should be refined before each evidence run, then executed only when the user explicitly asks for the run. The detailed M2-specific flow lives in `tests/scripts/M2-StatsWebShell/M2-StatsWebShell-test-flow.md`.

1. Verify the container runtime is expected to be used: `stats-runtime` and `http://127.0.0.1:8080`.
2. Confirm the M2 spec, file inventory, route list, and shell configuration are current.
3. Confirm admin credentials are available through approved runtime configuration without printing secrets. If unavailable, record the credential blocker and continue only with unauthenticated checks that remain valid.
4. Confirm whether a standard non-admin user is available for role-boundary checks. If a temporary user is created during an evidence run, record cleanup expectations before starting.
5. Terminal/API flow: capture Docker runtime status, `GET /health` returning HTTP `200`, and the current M2 integration/configuration check.
6. Browser flow: open `/health` and `/Login` from the container-exposed Stats Web URL.
7. Browser flow: sign in as admin, then verify `/` renders the dashboard shell with Dashboard, Upload documents, Documents, Reports, and admin-only Manage users navigation.
8. Browser flow: navigate to `/Upload`, `/Documents`, `/Reports`, `/EmailSetup` when applicable, and `/Users` as admin.
9. Browser flow: sign out or clear session, then verify protected routes redirect or block unauthenticated access.
10. Browser flow: sign in as a standard user when available, verify ordinary shell navigation, and verify `/Users` is absent or blocked.
11. Evidence proof: capture actual visible Windows Edge screenshots from the live Stats app with the address bar visible for every verified route/state.
12. Evidence proof: capture raw output and a visible terminal screenshot only during execution.
13. Evidence documentation: create/update the screenshot evidence index and reviewer walkthrough under the dated root `tests/results/` folder.
14. Cleanup: close temporary browser sessions, clear evidence-session storage, deactivate temporary standard users where supported, and record whether Docker was reused, started, left running, or intentionally stopped.

## M3/M4 Detailed Flow

The M3/M4 flow should be refined before each evidence run, then executed only when the user explicitly asks for the run:

1. Verify the container runtime is expected to be used: `stats-runtime`, `http://127.0.0.1:8080`, and M3/M4 internal API on port `8014`.
2. Confirm `tests/input` contains at least one supported real PDF or image fixture for acceptance coverage.
3. Choose or create a controlled invalid fixture for rejection coverage, such as unsupported extension, empty file, or signature/extension mismatch.
4. Confirm login credentials or an approved temporary evidence-user plan. If credentials are unavailable, mark the browser-login step blocked and continue only with clearly labelled container/API proof.
5. Browser flow: `/Login` -> `/Upload` -> verify the drag-and-drop zone and file browse affordance are both visible.
6. Browser flow: upload or drop a real fixture using the actual Stats app controls and confirm validation starts automatically without a separate button.
7. Browser/API proof: confirm accepted validation metadata: status, normalized filename, extension, size, detected MIME type, and SHA-256 hash when enabled.
8. Browser/API proof: confirm accepted validation continues to M4 ingestion and returns queued state, ingestion id, workflow, source context, and handoff metadata.
9. Rejection proof: upload or submit the invalid fixture and confirm controlled rejection with finding code and user-facing message.
10. Duplicate proof: re-submit the same accepted fixture hash or idempotency key and confirm duplicate/idempotency handling is visible.
11. Status proof: verify the user-visible next state in the Stats app; call ingestion status lookup only as supporting evidence, and check `/Documents` only if the current flow also persists a document record through later modules.
12. Terminal proof: run the relevant container command or script as supporting evidence and capture `Result: PASSED` or `Result: FAILED` only during evidence execution.
13. Cleanup: remove temporary invalid fixtures, copied container files, evidence users, and persisted document rows where practical; document anything retained.

## M5/M6 Detailed Flow

The M5/M6 flow should be refined before each evidence run, then executed only when the user explicitly asks for the run:

1. Verify the container runtime is expected to be used: `stats-runtime`, `http://127.0.0.1:8080`, and M5 `/health`.
2. Confirm `tests/input` contains at least one text-layer PDF and at least one OCR-required image or scanned PDF.
3. Confirm login credentials or admin seeding plan. If credentials are unavailable, mark the browser-login step blocked and continue only with clearly labelled container/API proof.
4. Browser flow: `/Login` -> `/Upload` -> upload real text PDF -> wait for parse/review output.
5. Browser flow: upload real OCR image/scanned fixture -> wait for OCR parse/review output.
6. Browser/API proof: confirm classification fields are visible or captured safely: `document_type`, `document_subtype`, `confidence`, `status`, and `reason_codes`.
7. Needs-review proof: include unsupported, low-quality, unknown, ambiguous, or pending-suggestion behavior when a suitable fixture or controlled request exists.
8. Handoff proof: continue far enough to show M7/M8 transaction-check or review state when the product flow proceeds.
9. Terminal proof: run the relevant container command or script and capture `Result: PASSED` or `Result: FAILED` only during evidence execution.
10. Cleanup: remove temporary uploads/records where practical and document anything retained.

<!-- M7 Test Flow Update - 2026-06-12 Start -->
## M7 Detailed Flow

The M7 flow should be refined before each evidence run, then executed only when the user explicitly asks for the run. The detailed M7-specific flow lives in `tests/scripts/M7-TransactionExtraction/M7-TransactionExtraction-test-flow.md`.

M7 acceptance evidence must prove the transaction extraction checkpoint from the normal Stats app flow. API and terminal output are supporting evidence only; they can explain extraction internals, but they do not replace the visible upload-to-extraction user journey unless the UI path is blocked and the blocker is recorded.

1. Verify the container runtime is expected to be used: `stats-runtime`, `http://127.0.0.1:8080`, and M7 `/health`.
2. Confirm `tests/input` contains at least one real transaction-bearing fixture and one no-transaction, ambiguous, unknown, or low-confidence fixture when available.
3. Confirm login credentials or admin seeding plan. If credentials are unavailable, mark the browser-login step blocked and continue only with clearly labelled container/API proof.
4. Browser flow: `/Login` -> `/Upload` -> upload a real transaction-bearing fixture -> wait for M3 validation, M4 ingestion, M5 parse/OCR, and M7 extraction output.
5. M5 handoff proof: confirm M7 received parsed text, page/source context, classification, quality metadata, and findings from M5. M7 must not rerun Tesseract when M5 already supplied usable text/OCR output.
6. M7 extraction proof: confirm transaction-like rows include amount, date when available, description, direction or transaction type, spending category, source/section context, confidence, and finding metadata.
7. Non-transaction extracted-data proof: confirm document-level financial fields, sections, entities, references, line items, reconciliation metadata, and redacted snippets are available when present in the fixture.
8. Classification proof: confirm required MVP reporting labels are present or review-gated: document type from M5, transaction type from M7, and spending category from M7. Low-confidence or unknown required labels must be visible as review-required findings before persistence.
9. Negative/needs-review proof: run a no-transaction, ambiguous, low-confidence, or unknown fixture when available. If no real fixture exists, record the fixture gap and use a minimal controlled API payload only as supporting proof.
10. M8 handoff proof: continue far enough to show M8 validation/review state consuming M7 candidates, including normalized rows or precise review blockers.
11. Terminal proof: run the relevant container command or script and capture `Result: PASSED` or `Result: FAILED` only during evidence execution.
12. Evidence documentation: create or update the screenshot evidence index and reviewer walkthrough under the dated root `tests/results/` folder.
13. Cleanup: remove temporary uploads, processing records, review suggestions, and saved transactions where practical; document anything retained.
<!-- M7 Test Flow Update - 2026-06-12 End -->

<!-- M8 Test Flow Update - 2026-06-12 Start -->
## M8 Detailed Flow

The M8 flow should be refined before each evidence run, then executed only when the user explicitly asks for the run. The detailed M8-specific flow lives in `tests/scripts/M8-DataValidation/M8-DataValidation-test-flow.md`.

M8 acceptance evidence must come from the actual Stats app browser flow a user would normally follow. API, database, and terminal outputs are supporting evidence only; they can explain or diagnose the flow, but they do not replace the visible user journey.

1. Verify the container runtime is expected to be used: `stats-runtime`, `http://127.0.0.1:8080`, and M8 `/health`.
2. Confirm the selected `tests/input` fixture is transaction-bearing and has already been proven to reach M7 extraction or has a controlled M7-shaped API payload.
3. Confirm login credentials or admin seeding plan. If credentials are unavailable, mark the browser-login step blocked and continue only with clearly labelled container/API proof.
4. Browser flow: `/Login` -> `/Upload` -> upload a real fixture -> wait for M5 parse, M7 extraction, and M8 transaction check results.
5. Browser proof: confirm normalized transaction rows show date, posted date when supplied, description, amount, currency, direction, status, and a visible Edit action.
6. Browser proof: confirm review items are shown first for repaired OCR rows, low-confidence rows, invalid fields, duplicate candidates, reconciliation mismatches, and incomplete installment balances when present.
7. Browser proof: confirm supporting non-transaction extracted data is hidden behind a toggle by default.
8. Duplicate proof: use the app's M9 pre-save duplicate-check path when persistence is in scope; otherwise record a UI blocker and attach direct M8 same-batch API proof as supporting request-local duplicate validation only.
9. Save proof: click `Save ready transactions` when M9 is in scope and verify saved, duplicate-blocked, or precise not-ready behavior.
10. Outcome proof: open `/Documents` and `/Reports` only when saved records are expected from the run.
11. Terminal proof: run the relevant container command or script and capture `Result: PASSED` or `Result: FAILED` only during evidence execution.
12. Cleanup: remove temporary uploads/records where practical and document anything retained.
<!-- M8 Test Flow Update - 2026-06-12 End -->

## Refinement Checklist

Before running any module evidence, update the planned flow with:

- Changed module(s).
- Required fixtures by filename or fixture class.
- Browser routes to capture.
- Container/API commands to run.
- Database queries, if persistence is part of the assertion.
- Expected pass/fail signals.
- Known blockers, credentials, or cleanup constraints.

<!-- M0 Foundation / M13 Containerization End -->
