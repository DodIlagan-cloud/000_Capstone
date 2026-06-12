<!-- M1 - User Access Management Start -->
<!-- Defines the targeted M1 acceptance test flow for future Docker-based evidence runs. -->

# M1 Identity Access Management Test Flow

## Purpose

This flow defines the targeted acceptance path for **M1 - User Access Management**. It is a test-flow specification only; do not treat this document as evidence that the flow has been run.

M1 evidence must prove the full identity journey through the live Stats app:

- public Stats Web entry point on `http://127.0.0.1:8080`
- login through the M1 Identity Access API
- first-login password maintenance when required
- administrator-only user management
- creation of a non-admin user with temporary password behavior
- standard-user login and standard-user block from admin-only user management
- database persistence of created users without exposing password hashes or secrets

## Evidence Capture Principle

All M1 acceptance evidence must be captured from an actual run of the Stats app, following the same browser paths a normal user would use. Evidence screenshots must come from the live application in a visible Windows Edge browser with the address bar visible.

The reviewer should be able to walk through the screenshots and supporting files as the real user journey: open Stats Web, log in, maintain password state, manage users as admin, sign out, log in as the new user, and verify the admin-only block.

Scripted checks, direct HTTP calls, database queries, raw API responses, or generated screenshots may support the evidence package, but they do not replace the user-flow browser evidence. If the browser flow is blocked by missing credentials, password-state constraints, runtime failure, or database configuration, record the blocker clearly and do not mark the full user flow as passed.

## Runtime Target

Official M1 evidence after M13 must use the Docker runtime where practical:

```text
Stats Web: http://127.0.0.1:8080
M1 internal API: http://localhost:8013 inside stats-runtime
Database: configured Stats runtime database target
```

Host-side `uvicorn`, host-side `dotnet run`, direct local module runs, or local database checks may be used only as diagnostics and must be labelled as non-acceptance evidence.

## Evidence Folder Pattern

Use a dated module-local evidence folder:

```text
modules/identity-access-module/test-results/M1-IdentityAccessManagement-DockerAcceptance-YYYY-MM-DD/
```

Expected files when this flow is executed:

- `M1-IdentityAccessManagement-test-results-YYYY-MM-DD.md`
- `M1-IdentityAccessManagement-test-raw-output-YYYY-MM-DD.txt`
- `M1-IdentityAccessManagement-manual-test-checklist.md`
- `M1-IdentityAccessManagement-screenshot-evidence-YYYY-MM-DD.md`
- `M1-IdentityAccessManagement-reviewer-walkthrough-YYYY-MM-DD.md`
- `M1-IdentityAccessManagement-windows-terminal-test-YYYY-MM-DD.png`
- actual visible Windows Edge screenshots for every browser route/state listed in this flow

## Credential And Secret Rules

- Do not print passwords, bearer tokens, connection strings, tenant IDs, subscription IDs, secret names that reveal values, or full secret values in chat, raw output, screenshots, or Markdown evidence.
- Admin credentials may be used only if already configured through the runtime environment, container secrets, Key Vault, or an approved temporary evidence seed.
- If admin credentials are missing, record a blocker and continue only with unauthenticated checks that remain valid.
- If admin login returns first-login password setup and changing that password would mutate a shared secret-backed admin account, record a credential-state blocker unless the user explicitly approves the mutation for the evidence run.
- A temporary non-admin user created for evidence should use a clearly test-only email and be deactivated, deleted, or reset after the flow where practical.
- Database proof must never display password hashes, tokens, or raw connection strings.

## Required Chat Progress Updates During A Run

When this flow is executed through Codex or another assistant, post concise progress updates after each major state:

1. Docker runtime health verified or failed.
2. Login page verified.
3. Admin credential availability checked without disclosing secrets.
4. Admin login result recorded.
5. First-login/password-maintenance state recorded.
6. Admin workspace verified.
7. Users route verified.
8. Temporary non-admin user creation attempted and result recorded.
9. User list/detail state verified.
10. Database persistence proof captured or blocker recorded.
11. Admin logout verified.
12. New user login result recorded.
13. New user password maintenance completed or blocker recorded.
14. New user permitted workspace verified.
15. New user admin-only block verified.
16. Terminal/raw-output evidence captured.
17. Evidence index and reviewer walkthrough with embedded screenshots written.
18. Cleanup completed or cleanup gap recorded.

## Automated Checks

Run or record the current equivalent Docker/container checks during an evidence run:

```powershell
docker ps
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health
docker exec stats-runtime curl -fsS http://127.0.0.1:8013/health
.\tests\scripts\regression\run_module_unit_tests.ps1
```

If the milestone requires full cross-module proof, use:

```powershell
.\tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

At minimum, M1 targeted evidence must include raw output for:

- Docker runtime status.
- Stats Web `/health` returning HTTP `200`.
- M1 internal `/health` from inside `stats-runtime`.
- M1 unit/contract tests from the container runtime.
- Authenticated current-user check for admin and standard user, with tokens redacted or omitted.
- Database query proof showing the created user exists in the configured runtime database.

## Browser Flow

Use actual visible Windows Edge screenshots with the address bar visible. Do not use rendered-response screenshots, static HTML captures, generated image previews, or isolated component renders as browser evidence.

| Step | Route / State | Expected Result | Required Screenshot |
| --- | --- | --- | --- |
| 1 | `/health` | Stats Web health returns healthy status from `http://127.0.0.1:8080/health`. | `M1-IdentityAccessManagement-windows-browser-health-YYYY-MM-DD.png` |
| 2 | `/Login` | Login page renders as unauthenticated entry point. | `M1-IdentityAccessManagement-windows-browser-login-YYYY-MM-DD.png` |
| 3 | Admin credential check | Admin credentials are available through approved runtime configuration, or a credential blocker is documented. | blocker note if credentials are unavailable |
| 4 | Admin login | Admin login succeeds, or the exact failure/blocker is documented. | `M1-IdentityAccessManagement-windows-browser-admin-login-YYYY-MM-DD.png` |
| 5 | Admin password maintenance | First-login password setup is shown and completed when required and approved, or no password change is required. | `M1-IdentityAccessManagement-windows-browser-admin-password-maintenance-YYYY-MM-DD.png` |
| 6 | Admin workspace | Admin reaches authenticated workspace and admin-only navigation is visible. | `M1-IdentityAccessManagement-windows-browser-admin-workspace-YYYY-MM-DD.png` |
| 7 | `/Users` as admin | Admin user-management route renders and supports user creation. | `M1-IdentityAccessManagement-windows-browser-admin-users-YYYY-MM-DD.png` |
| 8 | Create non-admin user | Admin creates a non-admin test user with temporary password behavior. | `M1-IdentityAccessManagement-windows-browser-user-created-YYYY-MM-DD.png` |
| 9 | Verify user list/detail | Created user appears with expected role, active state, and password-change state. | `M1-IdentityAccessManagement-windows-browser-user-state-YYYY-MM-DD.png` |
| 10 | Admin sign out | Browser returns to `/Login` or signed-out unauthenticated state. | `M1-IdentityAccessManagement-windows-browser-admin-signed-out-YYYY-MM-DD.png` |
| 11 | New user login | Created non-admin user signs in with temporary password. | `M1-IdentityAccessManagement-windows-browser-new-user-login-YYYY-MM-DD.png` |
| 12 | New user password maintenance | New user is forced through password setup when required and reaches completed state. | `M1-IdentityAccessManagement-windows-browser-new-user-password-maintenance-YYYY-MM-DD.png` |
| 13 | New user workspace | New user reaches permitted authenticated workspace. | `M1-IdentityAccessManagement-windows-browser-new-user-workspace-YYYY-MM-DD.png` |
| 14 | `/Users` as new user | Non-admin user is blocked from admin-only user management. | `M1-IdentityAccessManagement-windows-browser-new-user-admin-blocked-YYYY-MM-DD.png` |

## Database Proof

Use database proof as supporting evidence after the browser-created user flow. The query must run through the active runtime path and must not reveal secrets.

The database evidence should prove:

- which runtime container or cloud runtime is being used
- which database provider/target is active, without printing secret connection strings
- the test user's email or a redacted/hashed identifier
- role is non-admin
- active state is correct
- password-change state is correct for the step being verified
- row count/result and `Result: PASSED` or `Result: FAILED`

Do not select or print `hashed_password`, access tokens, refresh tokens, raw connection strings, or secrets.

## Reviewer Walkthrough Requirements

Create `M1-IdentityAccessManagement-reviewer-walkthrough-YYYY-MM-DD.md` with this structure:

```markdown
# M1 Identity Access Management Reviewer Walkthrough - YYYY-MM-DD

## Runtime
- Base URL:
- Container:
- Database target:
- Evidence folder:

## Flow Result
- Overall result:
- Gaps/blockers:
- Cleanup status:

## Step-by-Step Review
| Step | User State | Route/API/DB | Screenshot/Output | Reviewer Check |
| --- | --- | --- | --- | --- |

## Embedded Screenshots
### Step name
![Step name](screenshot-file-YYYY-MM-DD.png)

- Reviewer check:
- Result / comment:
```

The `Embedded Screenshots` section is required. Embed every browser and terminal screenshot inline with Markdown image syntax so the reviewer can inspect the evidence without opening each image separately.

Every embedded screenshot must be visually checked before the walkthrough is marked passed. The expected result for that step must be readable in the screenshot itself, such as the login form, authenticated workspace, admin-only Manage users control, created user state, standard-user block, database result, or terminal `Result: PASSED`. If the expected result is not visible, retake the screenshot or add a dedicated result screenshot.

Each reviewer check should say exactly what to look for, for example:

- address bar shows `http://127.0.0.1:8080/Login`
- admin reaches authenticated workspace
- Manage users is visible only for admin
- created user appears as non-admin and active
- database query shows the created user without password hash exposure
- standard user reaches permitted workspace
- standard user cannot open `/Users`
- no passwords, tokens, hashes, or connection strings appear in evidence

## Pass / Fail Criteria

Pass only when:

- Docker runtime health is verified.
- Login route is visible.
- Admin credentials are available through approved configuration or a precise blocker is documented.
- Admin login succeeds.
- Password-maintenance state is handled correctly for admin.
- Admin reaches authenticated workspace.
- Admin creates a non-admin test user.
- Created user appears in user-management list/detail with expected role and state.
- Database proof confirms user persistence without exposing secrets.
- Admin signs out.
- New user signs in, completes required password maintenance, and reaches permitted workspace.
- New user is blocked from admin-only user management.
- Raw output, terminal screenshot, screenshot evidence index, and reviewer walkthrough with embedded screenshots and visible-result checks are created during the evidence run.
- Temporary user/password state is cleaned up where practical, or retained state is documented.

Fail when:

- `stats-runtime` is unavailable.
- `/health` does not return HTTP `200`.
- Login page cannot render.
- Valid configured admin credentials cannot authenticate and no precise blocker is documented.
- Password maintenance cannot be completed when required for the evidence account.
- Admin cannot reach `/Users`.
- Standard user can access admin-only user management.
- Created user is not persisted in the configured runtime database.
- Evidence screenshots do not show actual visible browser windows with the address bar.
- Evidence screenshots do not visibly show the expected result for their step.
- Secrets, passwords, password hashes, bearer tokens, or connection strings appear in output or evidence.

## Cleanup

- Close temporary browser windows/profiles opened only for evidence.
- Clear browser session storage/cookies used for the evidence profile.
- Deactivate, delete, or reset the temporary non-admin evidence user where supported.
- Reset temporary password state only when approved and safe for the configured test account.
- Do not stop a Docker stack that was already running before the test unless the user asked for that cleanup.
- Record whether the Docker stack was reused, started, or left running.

<!-- M1 End -->
