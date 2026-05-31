<!-- M1 - User Access Management Start -->
<!-- Documents the files created or modified for Module 1 user access management. -->

# M1 User Access Management File Inventory

## Summary

This document lists the files created or modified for **M1 - User Access Management** and describes the purpose of each change.

The M1 User Access Management module establishes database-backed user accounts, email-based login, password hashing, bearer token authentication, protected API access, role-based authorization, administrator-only user management, and an ASP.NET Core access frontend for the Stats capstone project.

## Specification and Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M1-user-management-access-control-spec.md` | Created | Defines the Module 1 specification, including business analysis alignment, PostgreSQL database direction, user field rules, login rules, role requirements, endpoint contracts, security requirements, file tagging, tests, dependencies, and acceptance criteria. |
| `docs/M1-user-management-flow-diagram.md` | Created | Provides a three-role Module 1 activity diagram for first-admin bootstrap, frontend login, backend authorization, and administrator user addition. |
| `docs/M1-user-management-file-inventory.md` | Created | Documents the files created or modified for M1 and explains the purpose of each change. |

## Reusable Project Convention

| File | Change Type | Description |
| --- | --- | --- |
| `skills/module-file-tagging/SKILL.md` | Created | Adds a reusable Codex skill for applying module start/end comments and short purpose comments to new files and meaningful code blocks added to existing files. |
| `skills/module-file-tagging/agents/openai.yaml` | Created | Provides UI metadata for the reusable module file tagging skill. |

## Environment Setup

| File | Change Type | Description |
| --- | --- | --- |
| `docs/local-environment-setup.md` | Created | Documents local environment notes, including how to make Git available in PowerShell when it is installed but missing from `PATH`. This file was committed separately from the Module 1 implementation changes. |

## Application Configuration and Startup

| File | Change Type | Description |
| --- | --- | --- |
| `.gitignore` | Modified | Ignores local `.env` override files so M1 secrets and developer-specific runtime values stay out of source control. |
| `modules/identity-access-module/config/defaults.env` | Created | Stores committed local backend runtime defaults for API binding, browser origins, shared PostgreSQL database access, authentication, bootstrap placeholders, and existing service settings. |
| `modules/identity-access-module/.env.example` | Created or Modified | Lists local backend override values for API settings, the shared PostgreSQL application database URL, and authentication-related environment variables, including access token settings, password hash scheme, and optional default admin placeholders. |
| `modules/identity-access-module/app/config.py` | Modified | Loads backend runtime values from the committed defaults config, optional local `.env`, and environment overrides instead of keeping M1 runtime values in Python source. |
| `modules/identity-access-module/app/main.py` | Modified | Registers the new authentication and user management routers and reads API bind and browser-origin settings from backend configuration. |
| `modules/identity-access-module/app/db.py` | Modified | Ensures the user model is imported before metadata table creation so `init_db()` can create the users table. |
| `modules/identity-access-module/requirements.txt` | Modified | Adds PostgreSQL and authentication dependencies for future local/cloud runtime use: `psycopg[binary]`, `passlib[bcrypt]`, `python-jose[cryptography]`, and `email-validator`. |

<!-- M1 - User Access Management Start -->
<!-- Documents the migrated standalone Identity Access Module files. -->
## Migrated Identity Access Module

| File | Change Type | Description |
| --- | --- | --- |
| `modules/identity-access-module/README.md` | Created | Documents the migrated standalone Identity Access Module runtime, tests, and configuration surface. |
| `modules/identity-access-module/requirements.txt` | Created | Defines the standalone Python dependencies for the Identity Access Module. |
| `modules/identity-access-module/config/defaults.env` | Created | Provides committed local runtime defaults for the standalone Identity Access API. |
| `modules/identity-access-module/.env.example` | Created | Provides local override examples for Identity Access settings and bootstrap placeholders. |
| `modules/identity-access-module/app/main.py` | Created | Starts the standalone Identity Access API with health, auth, and user routes. |
| `modules/identity-access-module/app/config.py` | Created | Loads Identity Access runtime values from committed defaults, optional local `.env`, and environment overrides. |
| `modules/identity-access-module/app/db.py` | Created | Provides the standalone Identity Access database engine and session dependency. |
| `modules/identity-access-module/app/errors.py` | Created | Provides controlled Identity Access error types and API error helpers. |
| `modules/identity-access-module/app/models/common.py` | Created | Provides shared response schemas for health and root metadata. |
| `modules/identity-access-module/app/models/database.py` | Created | Defines the standalone SQLAlchemy metadata base for Identity Access models. |
| `modules/identity-access-module/app/models/user.py` | Created | Defines the user table, role enum, validation helpers, and safe request/response schemas. |
| `modules/identity-access-module/app/routes/auth.py` | Created | Provides login, current-user, and password-change endpoints. |
| `modules/identity-access-module/app/routes/health.py` | Created | Provides standalone health and root metadata endpoints. |
| `modules/identity-access-module/app/routes/users.py` | Created | Provides administrator user-management endpoints. |
| `modules/identity-access-module/app/services/auth_service.py` | Created | Provides authentication, token, active-user, and administrator authorization dependencies. |
| `modules/identity-access-module/app/services/user_service.py` | Created | Provides user persistence, bootstrap admin, password-change, update, and last-admin protection logic. |
| `modules/identity-access-module/app/utils/security.py` | Created | Provides password hashing, verification, bearer token creation, and token decoding. |
| `modules/identity-access-module/app/scripts/create_admin.py` | Created | Provides the first-administrator bootstrap command for the migrated module. |
| `modules/identity-access-module/tests/conftest.py` | Created | Provides isolated SQLite test setup for migrated Identity Access tests. |
| `modules/identity-access-module/tests/test_auth.py` | Created | Verifies authentication, password-change, token, and response-safety behavior in the migrated module. |
| `modules/identity-access-module/tests/test_users.py` | Created | Verifies user administration and authorization behavior in the migrated module. |
| `modules/identity-access-module/tests/test_foundation.py` | Created | Verifies migrated module startup, health, root metadata, settings, and database initializer. |
<!-- M1 End -->

## Models and Schemas

| File | Change Type | Description |
| --- | --- | --- |
| `modules/identity-access-module/app/models/user.py` | Created | Defines the SQLAlchemy `User` model, user roles, first-login password-change state, email/password/full-name/role validation helpers, and Pydantic schemas for login, token responses, password change, user creation, user updates, user responses, and current-user responses. |
| `modules/identity-access-module/app/errors.py` | Modified | Adds Module 1 authentication and authorization error types such as `INVALID_CREDENTIALS`, `UNAUTHENTICATED`, `FORBIDDEN`, `USER_ALREADY_EXISTS`, `USER_NOT_FOUND`, `INACTIVE_USER`, and `INVALID_TOKEN`. |

## Security and Services

| File | Change Type | Description |
| --- | --- | --- |
| `modules/identity-access-module/app/utils/security.py` | Created | Adds password hashing, password verification, signed bearer token creation, and token decoding/expiry validation. |
| `modules/identity-access-module/app/services/auth_service.py` | Created | Adds login authentication, bearer token generation, current-user resolution, required-password-change gating, active-user checks, and administrator authorization dependencies. |
| `modules/identity-access-module/app/services/user_service.py` | Created | Adds user persistence functions for creating users with temporary-password first-login setup, bootstrapping the first administrator with first-login password setup, changing passwords, finding users by email or ID, listing users, updating users, and checking for another active administrator. |

<!-- M1 - User Access Management Start -->
<!-- Documents the Module 1 initial administrator bootstrap command files. -->
## Bootstrap Command

| File | Change Type | Description |
| --- | --- | --- |
| `modules/identity-access-module/app/scripts/__init__.py` | Created | Marks the Module 1 command helper package used for local setup commands. |
| `modules/identity-access-module/app/scripts/create_admin.py` | Created | Creates the first administrator from `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` before any users exist. |
<!-- M1 End -->

## Routes

| File | Change Type | Description |
| --- | --- | --- |
| `modules/identity-access-module/app/routes/auth.py` | Created | Adds `POST /api/v1/auth/login` for bearer token login, `GET /api/v1/auth/me` for authenticated profile retrieval, and `POST /api/v1/auth/change-password` for first-login password setup. |
| `modules/identity-access-module/app/routes/users.py` | Created | Adds administrator user management endpoints for creating users, listing users, retrieving users, and updating users with role and active-status protections. |

<!-- M1 - User Access Management Start -->
<!-- Documents the Module 1 ASP.NET Core frontend files. -->
## Frontend

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/stats.Web.csproj` | Created | Defines the Module 1 ASP.NET Core Razor Pages frontend project. |
| `apps/stats-web/.gitignore` | Created | Ignores generated ASP.NET Core `bin` and `obj` build outputs. |
| `apps/stats-web/appsettings.json` | Created | Stores the current Stats Web Module 1 API base URL for the ASP.NET Core configuration pipeline. |
| `apps/stats-web/Program.cs` | Created | Starts the Razor Pages frontend and requires the Module 1 API base URL from app configuration or an environment override. |
| `apps/stats-web/Pages/Index.cshtml` | Created | Provides the authenticated main web app landing page after login and password setup. |
| `apps/stats-web/Pages/Index.cshtml.cs` | Created | Supplies the API base URL to the authenticated landing page. |
| `apps/stats-web/Pages/Login.cshtml` | Created | Provides the Module 1 login and first-login password setup Razor Page. |
| `apps/stats-web/Pages/Login.cshtml.cs` | Created | Supplies the API base URL to the login Razor Page. |
| `apps/stats-web/Pages/Users.cshtml` | Created | Provides the Module 1 administrator user management Razor Page. |
| `apps/stats-web/Pages/Users.cshtml.cs` | Created | Supplies the API base URL to the user management Razor Page. |
| `apps/stats-web/Pages/_ViewImports.cshtml` | Created | Declares Razor Pages namespace and tag helpers. |
| `apps/stats-web/wwwroot/css/access.css` | Created | Styles the login, main landing, and user management pages for desktop and mobile use. |
| `apps/stats-web/wwwroot/js/access.js` | Created | Shares session-token and API helpers across Module 1 frontend pages. |
| `apps/stats-web/wwwroot/js/app.js` | Created | Guards the authenticated main app landing page and shows current-user context. |
| `apps/stats-web/wwwroot/js/login.js` | Created | Submits login credentials, handles first-login password setup, and redirects completed logins to the landing page. |
| `apps/stats-web/wwwroot/js/users.js` | Created | Validates the admin browser session, loads users, creates temporary-password users, refreshes the list, and signs out. |
| `apps/stats-web/wwwroot/images/login-workspace.webp` | Created | Provides the generated login background image used by the Module 1 frontend. |
<!-- M1 End -->

<!-- M1 - User Access Management Start -->
<!-- Documents the migrated Stats Web app files. -->
## Migrated Stats Web App

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/README.md` | Created | Documents the migrated Stats Web app consumer runtime and configuration surface. |
| `apps/stats-web/stats.Web.csproj` | Created | Defines the migrated ASP.NET Core Razor Pages project. |
| `apps/stats-web/appsettings.json` | Created | Stores the current Identity Access API base URL for the migrated Stats Web consumer. |
| `apps/stats-web/Program.cs` | Created | Starts the migrated Razor Pages frontend and requires the API base URL from configuration. |
| `apps/stats-web/Pages/` | Created | Contains the migrated login, main landing, and user management Razor Pages. |
| `apps/stats-web/wwwroot/` | Created | Contains migrated CSS, JavaScript, and login background image assets. |
<!-- M1 End -->

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/unit/identity_access_module/conftest.py` | Modified | Provides the active isolated test database override, reusable database session fixture, and admin/standard/inactive user fixtures for container-executed authentication tests. |
| `tests/unit/identity_access_module/test_auth.py` | Created | Tests password hashing, password verification, successful login, required bootstrap-admin password change, password-change API, failed login, inactive-user login rejection, current-user profile access, missing/invalid/expired tokens, duplicate email handling, and response safety. |
| `tests/unit/identity_access_module/test_users.py` | Created | Tests user model import, initial administrator bootstrap rules, required initial-admin password change before user addition, admin-created temporary-password user creation, admin user listing, standard-user access rejection, self-profile access, cross-user access rejection, and last-active-admin deactivation/demotion protection. |
| `tests/unit/identity_access_module/test_foundation.py` | Modified | Verifies migrated module startup, health, root metadata, settings, and database initializer through the active root test suite. |

## API Endpoints Added

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/v1/auth/login` | `POST` | Authenticates an active user with email and password and returns a bearer token. |
| `/api/v1/auth/me` | `GET` | Returns the authenticated user's profile from a valid bearer token. |
| `/api/v1/auth/change-password` | `POST` | Changes the authenticated user's password and clears required first-login password setup. |
| `/api/v1/users` | `POST` | Allows administrators to create users. |
| `/api/v1/users` | `GET` | Allows administrators to list users. |
| `/api/v1/users/{user_id}` | `GET` | Allows administrators to retrieve any user and standard users to retrieve their own profile. |
| `/api/v1/users/{user_id}` | `PATCH` | Allows administrators to update user account details, roles, passwords, and active status with last-admin protection. |

| `.NET /Login` | `GET` | Serves the Module 1 ASP.NET Core login and password setup experience. |
| `.NET /` | `GET` | Serves the authenticated main web app landing page. |
| `.NET /Users` | `GET` | Serves the Module 1 ASP.NET Core administrator user management page. |

## Verification

<!-- M13 - Containerization Start -->
Official M1 verification now runs through the M13 container-first module runner:

```powershell
powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1
```

Result:

```text
M1 Identity Access: 29 passed
```

Historical host-side `pytest` or `dotnet build` evidence is retained only as development history and is not valid M1 acceptance evidence after M13.
<!-- M13 End -->

## Notes

- PostgreSQL is now the primary configured shared database target for the application; Module 1 adds user access tables to that database.
- Tests intentionally use isolated SQLite through dependency overrides so local verification does not require a running PostgreSQL server.
- The active standalone Identity Access Module is now under `modules/identity-access-module`.
- The active Stats Web access-flow consumer is now under `apps/stats-web`.
- The old transitional M1 folders were retired after migration; active M1 work now belongs in the architecture folders above.
- The current password/token implementation uses standard-library cryptographic primitives so tests can run in the current environment. Runtime dependencies for `passlib`, `python-jose`, and PostgreSQL drivers are documented in `requirements.txt` for future installation and hardening.
- Module 1 code blocks were tagged using the requested `M1 - User Access Management Start` and `M1 End` convention.
- The Git/PowerShell setup note was committed separately as requested.

<!-- M1 End -->

