<!-- M1 - User Access Management Start -->
<!-- Summarizes regression results for the admin-created user and first-login password reset flow. -->

# M1 User Access Management Regression Results

| Field | Value |
| --- | --- |
| Session | `RegTest-AdminUserFlow-M0-M1` |
| Date | `2026-05-23` |
| Backend database used for browser flow | PostgreSQL `stats` |
| Admin test email | `m1.regression.admin.20260523@example.com` |
| Created test user email | `m1.regression.user.20260523@example.com` |
| Test-only passwords | Used only inside this evidence session |
| Result | Passed |

## Automated Regression

| Check | Evidence | Result |
| --- | --- | --- |
| Identity Access Python tests | `M1-UserAccessManagementRegression-test-raw-output-2026-05-23.txt` | `29 passed` |
| Stats Web .NET build | `M1-UserAccessManagementRegression-dotnet-build-output-2026-05-23.txt` | Build succeeded with `0` errors |
| PostgreSQL post-flow state | `M1-AdminUserFlow-database-check-output-2026-05-23.txt` | Admin and created user exist; created user no longer requires password change |
| Direct PostgreSQL user query | `M1-AdminUserFlow-database-query-output-2026-05-23.txt` | Query returns the admin and created user rows from the `users` table |

## Browser Evidence Flow

The visible Edge evidence script seeded only a test administrator account in PostgreSQL, then used the real Stats Web UI for the remaining flow:

1. Admin logged in.
2. Admin opened User management.
3. Admin created `m1.regression.user.20260523@example.com`.
4. Admin signed out.
5. New user logged in with a temporary test password.
6. New user completed first-login password reset with a test-only password.
7. New user reached the main app landing page.

## Evidence Files

- `M1-AdminUserFlow-capture-output-2026-05-23.txt`
- `M1-AdminUserFlow-database-check-output-2026-05-23.txt`
- `M1-AdminUserFlow-database-query-output-2026-05-23.txt`
- `M1-AdminUserFlow-windows-browser-admin-created-user-2026-05-23.png`
- `M1-AdminUserFlow-windows-browser-admin-signed-out-2026-05-23.png`
- `M1-AdminUserFlow-windows-browser-new-user-password-setup-2026-05-23.png`
- `M1-AdminUserFlow-windows-browser-new-user-main-app-2026-05-23.png`

<!-- M1 End -->
