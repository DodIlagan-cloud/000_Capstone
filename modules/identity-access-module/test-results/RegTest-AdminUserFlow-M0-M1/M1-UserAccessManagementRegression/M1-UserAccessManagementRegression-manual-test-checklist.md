<!-- M1 - User Access Management Start -->
<!-- Manual evidence checklist for the admin-created user and password reset flow. -->

# M1 User Access Management Manual Test Checklist

| Check | Result | Evidence |
| --- | --- | --- |
| PostgreSQL `stats` database was reachable and used for the browser flow. | Pass | `M1-AdminUserFlow_capture_windows.py`, capture output |
| Test-only admin account was prepared in PostgreSQL. | Pass | `M1-AdminUserFlow_setup_postgres.py`, capture output |
| Admin logged in and accessed User management. | Pass | `M1-AdminUserFlow-windows-browser-admin-created-user-2026-05-23.png` |
| Admin created a new active standard user. | Pass | `M1-AdminUserFlow-windows-browser-admin-created-user-2026-05-23.png` |
| Admin signed out. | Pass | `M1-AdminUserFlow-windows-browser-admin-signed-out-2026-05-23.png` |
| New user logged in with temporary test password and was required to reset password. | Pass | `M1-AdminUserFlow-windows-browser-new-user-password-setup-2026-05-23.png` |
| New user reset password with a test-only password and accessed the main app. | Pass | `M1-AdminUserFlow-windows-browser-new-user-main-app-2026-05-23.png` |
| Database state confirms the created user is active and no longer requires password change. | Pass | `M1-AdminUserFlow-database-check-output-2026-05-23.txt` |
| Direct PostgreSQL query returns the admin and created test user rows from the `users` table. | Pass | `M1-AdminUserFlow-database-query-output-2026-05-23.txt` |

<!-- M1 End -->
