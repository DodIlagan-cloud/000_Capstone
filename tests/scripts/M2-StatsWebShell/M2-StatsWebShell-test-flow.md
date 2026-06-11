<!-- M2 - Stats Web Shell Start -->
<!-- Defines the targeted M2 acceptance test flow for future Docker-based evidence runs. -->

# M2 Stats Web Shell Test Flow

## Purpose

This flow defines the targeted acceptance path for **M2 - Stats Web Shell**. It is a test-flow specification only; do not treat this document as evidence that the flow has been run.

M2 evidence must prove that the Stats Web shell works as the user-facing app boundary over the M13 `stats-runtime` container:

- public Stats Web entry point on `http://127.0.0.1:8080`
- login and authenticated session handling through M1
- shell navigation for Dashboard, Upload documents, Documents, Reports, Email setup, and admin-only Users
- admin-only navigation and route behavior
- non-admin navigation and admin-block behavior when a standard user is available
- protected-route redirect/block behavior after logout or session clear

## Evidence Capture Principle

All M2 evidence must be captured from an actual run of the Stats app, following the same browser paths a normal user would use. Evidence screenshots must come from the live application in a visible Windows Edge browser with the address bar visible.

Scripted checks, direct HTTP calls, raw API responses, static HTML rendering, or generated page screenshots may support the evidence package, but they do not replace the user-flow browser evidence. If a route is part of the user-facing shell, the evidence run must navigate to it through the running app or by entering the live route URL in the browser while using the same authentication/session behavior a user would have.

## Runtime Target

Official M2 evidence after M13 must use the Docker runtime where practical:

```text
http://127.0.0.1:8080
```

Host-side `dotnet run` or local sibling-service orchestration may be used only as diagnostics and must be labelled as non-acceptance evidence.

## Evidence Folder Pattern

Use a dated root evidence folder:

```text
tests/results/M2-StatsWebShell-DockerAcceptance-YYYY-MM-DD/
```

Expected files:

- `M2-StatsWebShell-test-results-YYYY-MM-DD.md`
- `M2-StatsWebShell-test-raw-output-YYYY-MM-DD.txt`
- `M2-StatsWebShell-manual-test-checklist.md`
- `M2-StatsWebShell-screenshot-evidence-YYYY-MM-DD.md`
- `M2-StatsWebShell-reviewer-walkthrough-YYYY-MM-DD.md`
- `M2-StatsWebShell-windows-terminal-test-YYYY-MM-DD.png`
- actual visible Windows Edge screenshots for every route/state listed in this flow

## Credential Rules

- Do not print passwords, bearer tokens, connection strings, tenant IDs, subscription IDs, or secret values in chat, raw output, screenshots, or Markdown evidence.
- Admin credentials may be used only if they are already configured through the runtime environment, container secrets, Key Vault, or an approved test seed.
- If admin credentials are missing, record a blocker and continue only with unauthenticated and HTTP route checks that remain valid.
- If admin login returns first-login password setup and changing that password would mutate a shared secret-backed admin account, record a credential-state blocker instead of changing it.
- If a temporary standard user is created for non-admin checks, deactivate it after the flow if the API supports update, and record cleanup status.

## Required Chat Progress Updates During A Run

When this flow is executed through Codex or another assistant, post concise progress updates after each major state:

1. Docker runtime health verified or failed.
2. Login page verified.
3. Admin credential availability checked without disclosing secrets.
4. Admin login result recorded.
5. Dashboard route verified.
6. Upload route verified.
7. Documents route verified.
8. Reports route verified.
9. Email setup route verified.
10. Admin Users route verified or blocker recorded.
11. Logout/session-clear behavior verified.
12. Standard-user route behavior verified or blocker recorded.
13. Terminal/raw-output evidence captured.
14. Evidence index and reviewer walkthrough written.
15. Cleanup completed or cleanup gap recorded.

## Automated Checks

Run or record the current equivalent Docker/container checks:

```powershell
docker ps
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health
pytest tests\integration\test_stats_web_orchestration_config.py
```

If the full Docker regression is in scope for the current milestone, use:

```powershell
.\tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

At minimum, M2 targeted evidence must include raw output for:

- Docker runtime status.
- `GET /health` returning HTTP `200`.
- M2 integration/configuration check.
- Any authenticated API checks used to support admin or non-admin flow.

## Browser Flow

Use actual visible Windows Edge screenshots with the address bar visible. Do not use rendered-response screenshots, static HTML captures, generated image previews, or isolated component renders as browser evidence.

| Step | Route / State | Expected Result | Required Screenshot |
| --- | --- | --- | --- |
| 1 | `/health` | Stats Web health returns healthy status from `http://127.0.0.1:8080/health`. | `M2-StatsWebShell-windows-browser-health-YYYY-MM-DD.png` |
| 2 | `/Login` | Login page renders as unauthenticated entry point. | `M2-StatsWebShell-windows-browser-login-YYYY-MM-DD.png` |
| 3 | Admin login | Admin reaches authenticated shell, or credential blocker is documented. | `M2-StatsWebShell-windows-browser-admin-dashboard-YYYY-MM-DD.png` or blocker note |
| 4 | `/` | Dashboard/home shell renders with main nav. | `M2-StatsWebShell-windows-browser-dashboard-YYYY-MM-DD.png` |
| 5 | `/Upload` | Upload documents route renders for authenticated user. | `M2-StatsWebShell-windows-browser-upload-YYYY-MM-DD.png` |
| 6 | `/Documents` | Documents route renders for authenticated user. | `M2-StatsWebShell-windows-browser-documents-YYYY-MM-DD.png` |
| 7 | `/Reports` | Reports route renders for authenticated user. | `M2-StatsWebShell-windows-browser-reports-YYYY-MM-DD.png` |
| 8 | `/EmailSetup` | Email setup route renders if still applicable to the shell. | `M2-StatsWebShell-windows-browser-email-setup-YYYY-MM-DD.png` |
| 9 | `/Users` as admin | Admin user-management route renders and admin-only nav is visible. | `M2-StatsWebShell-windows-browser-admin-users-YYYY-MM-DD.png` |
| 10 | Sign out or clear session | Browser returns to `/Login`; protected routes do not stay visible. | `M2-StatsWebShell-windows-browser-signed-out-YYYY-MM-DD.png` |
| 11 | Protected route while unauthenticated | `/`, `/Upload`, `/Documents`, `/Reports`, and `/Users` redirect/block unauthenticated access. | `M2-StatsWebShell-windows-browser-protected-route-blocked-YYYY-MM-DD.png` |
| 12 | Standard user dashboard | Standard user can access shell routes but does not see admin-only links. | `M2-StatsWebShell-windows-browser-standard-user-dashboard-YYYY-MM-DD.png` |
| 13 | `/Users` as standard user | Standard user is blocked from admin-only route. | `M2-StatsWebShell-windows-browser-standard-user-admin-blocked-YYYY-MM-DD.png` |

## Reviewer Walkthrough Requirements

Create `M2-StatsWebShell-reviewer-walkthrough-YYYY-MM-DD.md` with this structure:

```markdown
# M2 Stats Web Shell Reviewer Walkthrough - YYYY-MM-DD

## Runtime
- Base URL:
- Container:
- Evidence folder:

## Flow Result
- Overall result:
- Gaps/blockers:
- Cleanup status:

## Step-by-Step Review
| Step | User State | Route | Screenshot | Reviewer Check |
| --- | --- | --- | --- | --- |
```

Each reviewer check should say exactly what to look for, for example:

- address bar shows `http://127.0.0.1:8080/Login`
- dashboard navigation includes Home, Upload documents, Documents, Reports
- Manage users is visible only for admin
- standard user cannot open `/Users`
- signed-out browser returns to `/Login`

## Pass / Fail Criteria

Pass only when:

- Docker runtime health is verified.
- Login route is visible.
- Admin flow is completed, or a precise credential/state blocker is documented.
- Authenticated dashboard and main shell routes are verified through actual browser screenshots captured from the live Stats app while following normal user interaction paths.
- Protected routes redirect or block unauthenticated access.
- Standard-user behavior is verified, or a precise standard-user blocker is documented.
- Raw output, terminal screenshot, screenshot evidence index, and reviewer walkthrough are created.
- Temporary test users or sessions are cleaned up where applicable.

Fail when:

- `stats-runtime` is unavailable.
- `/health` does not return HTTP `200`.
- Login page cannot render.
- Authenticated shell navigation fails for valid configured credentials.
- Admin-only route is visible or usable by a standard user.
- Evidence screenshots do not show actual visible browser windows with the address bar.
- Secrets appear in output or evidence.

## Cleanup

- Close temporary browser windows/profiles opened only for evidence.
- Clear browser session storage/cookies used for the evidence profile.
- Deactivate temporary standard users where supported.
- Do not stop a Docker stack that was already running before the test unless the user asked for that cleanup.
- Record whether the Docker stack was reused, started, or left running.

<!-- M2 End -->
