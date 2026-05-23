<!-- M1 - User Access Management Start -->
<!-- Indexes focused Windows Edge and terminal screenshots for the Module 1 config-driven runtime regression pass. -->

# M1 User Access Management Regression Screenshot Evidence

## Evidence Session

| Field | Value |
| --- | --- |
| Module | M1 - User Access Management |
| Regression focus | Config-driven runtime values |
| Date | 2026-05-23 |
| API URL | `http://127.0.0.1:8013` |
| Stats Web URL | `http://127.0.0.1:5013` |

## Screenshots

| Evidence | File | Result |
| --- | --- | --- |
| Windows Edge Stats Web login page | `M1-UserAccessManagementRegression-windows-browser-dotnet-login-2026-05-23.png` | Edge shows the local `.NET` `/Login` page at `127.0.0.1:5013/Login`. |
| Windows Edge backend API docs | `M1-UserAccessManagementRegression-windows-browser-api-docs-2026-05-23.png` | Edge shows the local FastAPI docs at `127.0.0.1:8013/docs`, including authentication and users endpoints. |
| Windows Edge protected auth route | `M1-UserAccessManagementRegression-windows-browser-auth-me-unauthenticated-2026-05-23.png` | Edge shows `GET /api/v1/auth/me` rejects a missing bearer token with `Not authenticated`. |
| Windows terminal direct verification | `M1-UserAccessManagementRegression-windows-terminal-test-2026-05-23.png` | PowerShell shows configured runtime values, visible URL checks, first-login password gating, user creation, and `Result: PASSED`. |

Screenshots are actual Windows screenshots captured from Microsoft Edge and PowerShell, cropped to the relevant browser or terminal window.

<!-- M1 End -->
