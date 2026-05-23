<!-- M1 - User Access Management Start -->
<!-- Indexes visible Edge screenshots for the admin-created user evidence flow. -->

# M1 User Access Management Screenshot Evidence

| Field | Value |
| --- | --- |
| Session | `RegTest-AdminUserFlow-M0-M1` |
| Date | `2026-05-23` |
| Browser | Microsoft Edge |
| Stats Web URL | `http://127.0.0.1:5013` |
| API URL | `http://127.0.0.1:8013` |
| Database | PostgreSQL `stats` |

## Screenshot Index

| Evidence | File | Result |
| --- | --- | --- |
| Admin created user | `M1-AdminUserFlow-windows-browser-admin-created-user-2026-05-23.png` | User management page shows the admin session, success message, and created test user in the user table. |
| Admin signed out | `M1-AdminUserFlow-windows-browser-admin-signed-out-2026-05-23.png` | Edge returned to the `/Login` page after admin sign-out. |
| New user first login | `M1-AdminUserFlow-windows-browser-new-user-password-setup-2026-05-23.png` | New user reached the required first-login password setup form. |
| New user main app access | `M1-AdminUserFlow-windows-browser-new-user-main-app-2026-05-23.png` | New user completed password reset and reached the main app landing page. |

## Notes

- Screenshots were captured from the visible Microsoft Edge window.
- The temporary and final passwords are test-only values used only for this regression evidence session.
- The PostgreSQL database check confirms the created user no longer has `must_change_password` after reset.

<!-- M1 End -->
