<!-- M1 - User Access Management Start -->
<!-- Specifies identity login, roles, permissions, protected access, and current Stats account persistence. -->

# Module 1 Identity Access Module Specification

## Module Summary

Module 1 establishes the reusable Identity Access Module for the Stats capstone project. It provides account and credential rules, secure password handling, login, identity claims, token-based authenticated access, role-based authorization decisions, and clear separation between administrator and standard user capabilities.

This module builds on the Project Foundation module and follows the building-block architecture boundary. It does not own Stats-specific web screens, document upload, OCR, document classification, transaction extraction, reporting dashboards, email ingestion, containerization, or cloud deployment. It creates the identity and authorization capability that Stats Web and later protected modules can consume through explicit contracts.

## Architecture Alignment

Module 1 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`

The building-block plan defines this module as:

| Field | M1 Direction |
| --- | --- |
| Build order | `1` |
| Module | Identity Access Module |
| Type | Standalone reusable module |
| Main responsibility | User login, role claims, tokens, protected access checks |
| Reusable contract | Auth/token API and token verification contract |

The active implementation demonstrates the desired behavior through a FastAPI identity API and a consuming ASP.NET Core Stats Web access flow. This specification preserves that behavior while separating ownership:

- M1 owns reusable identity/access rules, endpoints, identity account data requirements, token behavior, role checks, and identity contracts.
- Stats Web owns product-specific login, user-management, navigation, and landing-page presentation as a consumer of the M1 identity API.
- Stats Data and Persistence owns the Stats database schema, migrations, and product persistence adapters when that encompassing product module is implemented.
- Cross-boundary frontend verification may remain in the M1 evidence set when it proves that Stats Web consumes the identity contract.

## Business Analysis Alignment

The business-analysis area for this module is:

```text
User Management and Access Control
Login, roles, permissions, authenticated access, admin/user separation.
```

The business need is to ensure that financial document processing is only available to authorized users, and that administration tasks are separated from normal user workflows. Because later modules will handle sensitive financial documents and transaction data, access control must be implemented before upload, extraction, validation, storage, reporting, and email ingestion features are expanded.

## Goals

- Define the account, credential, claims, and authorization data required by an identity consumer.
- Keep the Stats PostgreSQL-backed identity implementation working while the Stats Data boundary is introduced.
- Provide secure password hashing and verification.
- Implement login with token-based authenticated access.
- Expose a reusable identity contract that Stats Web and later protected modules can call.
- Define roles for administrator and standard user access.
- Protect API routes using reusable authentication dependencies.
- Provide role-based authorization dependencies for future modules.
- Expose basic user profile and administration endpoints.
- Keep authentication behavior compatible with later upload, reporting, and ingestion workflows.
- Include tests proving successful login, failed login, protected access, and role restrictions.

## Tasks

1. Preserve the current working login, token, first-password-change, role, and administrator user-management behavior.
2. Define the reusable Identity Access inputs, outputs, safe schemas, errors, and authorization decisions used by Stats Web and later modules.
3. Keep identity persistence, bootstrap behavior, API binding, browser origin access, and consumer API routing configurable for the current PostgreSQL-backed Stats deployment without making Stats database schema ownership a reusable M1 concern.
4. Keep Stats-specific Razor Pages and navigation as consumer behavior outside the reusable identity internals.
5. Keep the migrated identity code under `modules/identity-access-module/` and make new reusable identity changes there.
6. Retain module-local automated tests, Stats Web consumer verification where useful, root `tests/results/` evidence artefacts, configuration samples, and regression coverage.

## Non-Goals

- Implementing password reset email workflows.
- Implementing external identity providers such as Microsoft Entra ID, Google, or OAuth social login.
- Implementing multi-factor authentication.
- Implementing full audit logging for every user action.
- Implementing document ownership or document-level permissions beyond preparing user identifiers for future modules.
- Owning Stats-specific login screens, navigation, landing pages, or user-management page presentation.
- Owning the Stats database schema, migrations, persistence adapters, or data-product associations after the Stats Data and Persistence product module is introduced.
- Deploying PostgreSQL or Azure Database for PostgreSQL infrastructure.
- Migrating to Azure SQL Database.

## Architecture Boundary

### Current Owner Folder

The current repository boundary for Module 1 is:

```text
modules/identity-access-module/
```

This folder owns reusable identity/access code, module-local automated tests, configuration samples, runtime instructions, and module README files.

M1 specifications, file inventories, project-level documentation, and assessment evidence belong under root `docs/` and root `tests/results/`.

<!-- M13 - Containerization Start -->
Authoritative M1 automated tests live under root `tests/unit/identity_access_module/` and execute inside `stats-runtime`.
<!-- M13 End -->

### Current Implementation Surface

The M1 identity implementation has been migrated to:

```text
modules/identity-access-module/
```

New M1 identity changes must be made under `modules/identity-access-module/`.

<!-- M1 - User Access Management Start -->
<!-- Documents the current Stats Web consumer boundary for the M1 identity contract. -->
## Stats Web Consumer Boundary

The current consumer app has been migrated to:

```text
apps/stats-web/
```

New Stats Web access-flow changes must be made under:

```text
apps/stats-web/
```

Stats Web must remain an ASP.NET Core app that can submit credentials to the M1 login API, store session token material for the active browser session, retrieve the current-user profile, present the current access flow, and call administrator user endpoints. Those UI screens are product-consumer behavior, not identity-module internals.
<!-- M1 End -->

## Stats Data and Persistence Alignment

The updated building-block plan places the Stats database under the encompassing product module:

```text
apps/stats-data/
```

`apps/stats-data/` owns Stats database schema, migrations, persistence adapters, dashboard/reporting queries, and associations between users and later document workflow results. The reusable Identity Access Module defines identity account data needs and identity API behavior; it does not own the whole Stats database direction.

### Current Persistence

The current Stats implementation uses one PostgreSQL-compatible database named `stats` and stores M1 user access data there through SQLAlchemy.

- `DATABASE_URL` identifies the Stats PostgreSQL database used by the identity API.
- The current `users` table satisfies the identity account data requirements described in this spec.
- Test databases may remain isolated from local PostgreSQL.
- Current SQLAlchemy persistence should remain behind identity services and contracts so a future Stats persistence adapter can be separated without changing login/token behavior.

### Target Persistence Boundary

- M1 must describe the minimum account, credential, role, active-status, and password-state data needed by the Identity Access contract.
- Stats Data and Persistence will own Stats-specific schema placement and migrations when the database product module is executed.
- Other projects that reuse Identity Access may supply a different persistence adapter or database strategy.
- M1 code must avoid exposing password hashes, database sessions, or Stats-specific persistence internals to consumers.

### Local Database Assumptions

- Current local Stats database: PostgreSQL database `stats`.
- Current database connection setting: `DATABASE_URL`.
- Current persistence library: SQLAlchemy in the FastAPI implementation.
- PostgreSQL-specific raw SQL should be avoided so the identity behavior remains portable across future persistence decisions.

### Future Deployment Note

The current preferred Azure target for Stats remains Azure Database for PostgreSQL Flexible Server. Cloud database deployment and any future Azure SQL reassessment belong to Stats Data, Containerization, and Cloud Readiness decisions rather than the reusable M1 identity contract.

## Required Project Structure

### Current M1 Structure

The reusable module currently uses:

```text
modules/identity-access-module/
  app/
    config.py
    db.py
    errors.py
    main.py
    models/
      user.py
    routes/
      auth.py
      users.py
    services/
      auth_service.py
      user_service.py
    utils/
      security.py
  tests/
    conftest.py
    test_auth.py
    test_users.py
  README.md
  requirements.txt
  .env.example
```

### Migrated Stats Web Structure

The current Stats Web consumer uses:

```text
apps/stats-web/
  stats.Web.csproj
  Program.cs
  Pages/
    Index.cshtml
    Index.cshtml.cs
    Login.cshtml
    Login.cshtml.cs
    Users.cshtml
    Users.cshtml.cs
    _ViewImports.cshtml
  wwwroot/
    css/
      access.css
    images/
      login-workspace.webp
    js/
      access.js
      app.js
      login.js
      users.js
```

The paths above are the active architecture-aligned locations for M1 work.

## Identity Input and Output Contract

The Identity Access Module starts from the building-block I/O map and refines it for the current Stats implementation.

### Inputs

| Input | Description |
| --- | --- |
| Credentials | Email login username and password submitted for login. |
| Bearer token | Existing signed token submitted for current-user or protected-route validation. |
| Access request | User identity plus requested role/action/resource context for an authorization decision. |
| Administrator user command | Validated user-create, user-list, user-read, or user-update request from an authorized admin consumer. |

### Outputs

| Output | Description |
| --- | --- |
| Auth result | Success/failure response for credential verification. |
| Token result | Bearer token material, token type, expiry behavior, and password-change-required flag where applicable. |
| User identity claims | Stable user identifier, email, role, active status, optional display name, and first-login password state. |
| Authorization decision | Allowed or denied protected access with controlled error/status behavior. |
| User administration result | Safe user response data without password hashes or secret material. |

### Consumer Boundary

- Stats Web may call M1 login, current-user, password setup, and administrator user APIs.
- Other backend modules may rely on M1 token verification and authorization outcomes through explicit API/dependency/adaptor contracts.
- A consumer must not import password hashing, token signing, or user persistence internals from M1 unless the implementation remains temporarily co-located during the architecture transition.

<!-- M1 - User Access Management Start -->
<!-- Documents tagging requirements for new files and added code sections. -->
## File Tagging Convention

Any new file created for this module must include a short top-of-file start comment identifying the module and the file purpose when the file type supports comments.

Any new file created for this module must also include a matching end comment at the bottom of the file when the file type supports comments.

Any meaningful code, configuration, schema, migration, route, test, or documentation section added to an existing file must also include a nearby module start tag, a short purpose comment, and a matching end tag. The start tag should be placed immediately before the added block where practical, and the end tag should be placed immediately after the added block.

When a Module 1 change replaces an existing line in a commentable file, the prior line must remain commented out inside the tagged block and the updated line must be written directly below it.

Module 1 files must use this label:

```text
M1 - User Access Management Start
```

The end tag may be shortened to:

```text
M1 End
```

The second comment line after the start tag must briefly describe what the file is for.

For existing files, the second comment line must briefly describe what the added section is for.

Examples:

```python
# M1 - User Access Management Start
# Defines authentication routes for login and current-user access.

...

# M1 End
```

```markdown
<!-- M1 - User Access Management Start -->
<!-- Specifies user login, roles, permissions, and protected access requirements. -->

...

<!-- M1 End -->
```

```python
# M1 - User Access Management Start
# Requires an authenticated active user for protected routes.
def get_current_active_user(...):
    ...
# M1 End
```

```python
# M1 - User Access Management Start
# Changes the configured identity persistence target to the Stats database.
# database_url: str = "sqlite:///./stats_ingestion.db"
database_url = _config_value(config_values, "DATABASE_URL")
# M1 End
```

Do not tag every individual line. One start/end pair should cover a related added block. Tiny mechanical edits, formatting-only changes, import-only edits, generated files, binary assets, screenshots, lockfiles, and files that do not support comments do not need tags.

This convention is also captured as a reusable local Codex skill at:

```text
skills/module-file-tagging/SKILL.md
```

The same convention should be adapted for later modules by changing the module label, for example `M2 - Manual Document Upload`.
<!-- M1 End -->

## Configuration

Identity authentication configuration must be centralized through the M1 module settings pattern and follow the M0 project-wide runtime configuration standard. Runtime values used by M1 and its Stats Web consumer must be read from config files or supported environment overrides rather than being hardcoded in application code. The Stats PostgreSQL persistence setting remains behind the backend settings loader until the Stats Data persistence boundary is executed.

### Current Config Files

| Config File | Purpose |
| --- | --- |
| `modules/identity-access-module/config/defaults.env` | Committed local backend runtime defaults for the current identity API, including bind settings, CORS origins, shared Stats database URL, and M1 authentication values. |
| `modules/identity-access-module/.env` | Optional local backend override file for secrets, admin bootstrap values, or developer-specific runtime values; it must stay out of source control when it contains real secrets. |
| `modules/identity-access-module/.env.example` | Example backend override file and list of current backend setting names. |
| `apps/stats-web/appsettings.json` | Committed Stats Web consumer config for the M1 API base URL. |

Environment variables override backend config values. Stats Web may override `StatsApi:BaseUrl` through its normal ASP.NET Core configuration providers or through `STATS_API_BASE_URL`.

### Required Settings

| Setting | Default | Description |
| --- | --- | --- |
| `database_url` | `postgresql+psycopg://postgres:postgres@localhost:5432/stats` | Current Stats PostgreSQL connection URL used by identity persistence |
| `api_host` | `0.0.0.0` | Backend bind host for direct Python startup |
| `api_port` | `8000` | Backend bind port for direct Python startup |
| `cors_allowed_origins` | `http://localhost:8080,http://127.0.0.1:8080` | Comma-separated origins allowed to call the current API from browser consumers |
| `access_token_secret_key` | development-only value | Secret used to sign access tokens |
| `access_token_algorithm` | `HS256` | JWT signing algorithm |
| `access_token_expire_minutes` | `60` | Access token expiry window |
| `password_hash_scheme` | `pbkdf2_sha256` | Current password hashing scheme setting; may be hardened behind the same identity contract |
| `default_admin_email` | empty | Optional seed administrator email for local setup |
| `default_admin_password` | empty | Optional seed administrator password for local setup |
| `StatsApi:BaseUrl` | `http://127.0.0.1:8013` | Current Stats Web API base URL stored in `appsettings.json` |

### Environment Behavior

- Settings must support environment variable overrides.
- Runtime URLs, database targets, bind settings, browser origins, token settings, bootstrap values, and consumer API targets must live in config files or supported secret/environment providers instead of code literals.
- The application must not require hardcoded database credentials.
- The development secret key may be used locally only.
- Production and cloud environments must provide a strong secret through environment variables or managed secrets.
- Token expiry must be configurable without code changes.

## Identity Account Data Contract

The Identity Access Module requires safe account, credential, role, and password-state data. The current implementation stores that data in PostgreSQL through SQLAlchemy; future Stats Data work may wrap or relocate the Stats-specific persistence while preserving this contract.

Email is the login username for this module. A separate username field is not required unless a later business requirement introduces one.

### Required Account Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID or integer primary key | Yes | Stable internal user identifier supplied by the identity persistence implementation |
| `email` | string | Yes | Unique login username; store normalized lowercase |
| `full_name` | string | No | Display name for user-facing workflows |
| `hashed_password` | string | Yes | Never store plain text passwords |
| `role` | enum/string | Yes | Must support `admin` and `user` |
| `is_active` | boolean | Yes | Allows account disabling |
| `must_change_password` | boolean | Yes | Requires bootstrap or temporary-password users to set a password before ordinary protected actions |
| `created_at` | datetime | Yes | UTC timestamp |
| `updated_at` | datetime | Yes | UTC timestamp |
| `last_login_at` | datetime | No | Updated after successful login |

### Role Requirements

The module must support these roles:

- `admin`: can manage users and access administrator-only endpoints.
- `user`: can access authenticated user endpoints but cannot manage other users.

Later modules may add more granular permissions, but Module 1 must provide a reusable pattern for checking roles.

### User Field Validation Rules

#### Email Login Username

- `email` is required and is used as the login username.
- The value must be a valid email address.
- Leading and trailing spaces must be removed before validation and storage.
- The stored value must be lowercase.
- The value must be unique across users.
- Maximum length is 255 characters.
- Blank or whitespace-only values must be rejected.
- Duplicate emails must return a controlled `USER_ALREADY_EXISTS` error.
- Email changes should be treated carefully once later modules link documents or transactions to a user.

Example normalization:

```text
" EDUARDO.I@example.com " -> "eduardo.i@example.com"
```

#### Password

- Password is required when creating a user.
- Minimum length is 8 characters.
- Maximum length is 128 characters.
- Must include at least one letter.
- Must include at least one number.
- Symbols are allowed but not required.
- Blank or whitespace-only passwords must be rejected.
- Plain text passwords must never be stored, logged, or returned in API responses.
- Only the generated password hash may be persisted.

#### Full Name

- `full_name` is optional but recommended.
- Leading and trailing spaces must be removed.
- If provided, length must be between 2 and 100 characters.
- Names may include letters, spaces, hyphens, apostrophes, and periods.
- The value does not need to be unique.

#### Role

- `role` is required.
- Allowed values are `admin` and `user`.
- Default role is `user`.
- Only admin users can assign or change roles.
- A standard user must not be able to promote themselves to admin.
- The system should prevent deactivating, deleting, or demoting the last active admin where practical.
- The system must always retain at least one active administrator.

#### Account Status

- `is_active` is required.
- Default value is `true`.
- Inactive users cannot log in.
- Inactive users cannot access protected routes.
- Administrators can deactivate users instead of deleting records.

#### Password Setup Status

- Admin-created users must be created with `must_change_password=true` because the administrator-provided password is temporary.
- The initial bootstrap administrator must also be created with `must_change_password=true`.
- A user marked with `must_change_password=true` can log in and change their password.
- Administrator user-management actions must be blocked until required password setup is completed.

#### System-Managed Fields

- `id` is generated by the system and must not be editable by users.
- UUID is preferred for long-term cloud and database portability.
- `created_at` is generated in UTC when the user is created and must not be directly editable.
- `updated_at` is generated in UTC when the user record changes and must not be directly editable.
- `last_login_at` is generated in UTC after successful login and may be null before first login.

## Authentication Contract

### Password Handling

- Plain text passwords must never be stored.
- Passwords must be hashed using a recognized password hashing library.
- Password verification must compare a submitted password against the stored hash.
- Password validation must follow the Module 1 user field validation rules.

### Token Handling

- Login must return a bearer access token.
- Tokens must include enough claims to identify the authenticated user.
- Tokens must expire.
- Invalid, expired, or malformed tokens must be rejected.
- The current FastAPI implementation must use reusable authentication dependencies to retrieve the current authenticated user.
- The reusable module contract must remain usable by future non-Stats consumers without requiring Stats Web page code.

### Required Auth Endpoints

#### `POST /api/v1/auth/login`

Authenticates a user and returns an access token.

Request shape:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Success response shape:

```json
{
  "access_token": "signed-token-value",
  "token_type": "bearer",
  "password_change_required": false
}
```

Failure behavior:

- Invalid credentials return HTTP 401.
- Inactive users return HTTP 403.
- Responses must not reveal whether the email or password was incorrect.

#### `GET /api/v1/auth/me`

Returns the authenticated user's profile.

Success response shape:

```json
{
  "id": "user-id",
  "email": "user@example.com",
  "full_name": "Example User",
  "role": "user",
  "is_active": true
}
```

Failure behavior:

- Missing token returns HTTP 401.
- Invalid token returns HTTP 401.
- Inactive user returns HTTP 403.

<!-- M1 - User Access Management Start -->
<!-- Defines the first administrator bootstrap flow for initial login. -->
## Initial Administrator Bootstrap

A fresh database has no administrator account. Module 1 must provide a local command that creates the first administrator before admin-only user creation endpoints are used.

### Current Bootstrap Command

The active implementation provides this bootstrap command from:

```text
modules/identity-access-module
```

Command:

```powershell
python -m app.scripts.create_admin
```

Required environment settings:

- `DATABASE_URL`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`

Required behavior:

- Create database tables needed for Module 1 user accounts when they do not exist.
- Create one active `admin` user from the configured initial email and password.
- Reuse Module 1 email and password validation rules.
- Store only the generated password hash.
- Refuse initial-administrator creation when any user already exists.
- Print a clear success message without printing the password.

After the initial administrator exists, a consumer may call the identity APIs to complete the first-login password change and add users. The current Stats Web consumer demonstrates this by using the ASP.NET Core `/Login` and `/Users` pages backed by M1 APIs.
<!-- M1 End -->

<!-- M1 - User Access Management Start -->
<!-- Defines the authenticated password setup endpoint used on first login. -->
#### `POST /api/v1/auth/change-password`

Changes the authenticated user's password and clears the first-login password setup requirement.

Request shape:

```json
{
  "new_password": "new-password123"
}
```

Required behavior:

- Require a valid bearer token.
- Reuse Module 1 password validation rules.
- Store only the new password hash.
- Return the current user with `must_change_password=false` after success.
<!-- M1 End -->

## User Administration Contract

Administrator endpoints must require an authenticated `admin` user.

### Required User Endpoints

#### `POST /api/v1/users`

Creates a user account.

Authorization:

- Admin only.

Password setup behavior:

- The administrator supplies an initial temporary password in Module 1.
- The created user must change that password on first login before ordinary protected access continues.

Request shape:

```json
{
  "email": "new.user@example.com",
  "full_name": "New User",
  "password": "password123",
  "role": "user",
  "is_active": true
}
```

Success response shape:

```json
{
  "id": "user-id",
  "email": "new.user@example.com",
  "full_name": "New User",
  "role": "user",
  "is_active": true
}
```

#### `GET /api/v1/users`

Lists users.

Authorization:

- Admin only.

#### `GET /api/v1/users/{user_id}`

Returns one user profile.

Authorization:

- Admin can retrieve any user.
- Standard users may retrieve only their own profile if this endpoint is reused for self-service access.

#### `PATCH /api/v1/users/{user_id}`

Updates user account details.

Authorization:

- Admin only for role and active-status changes.
- Standard users must not be able to grant themselves administrator permissions.

<!-- M1 - User Access Management Start -->
<!-- Defines current Stats Web consumer checks against the M1 identity contract. -->
## Stats Web Consumer Access Flow

Stats Web UI ownership belongs to the Stats Web Shell architecture area, not to the standalone Identity Access Module. The current Stats Web access screens are retained as a consumer flow because the user access behavior is already useful and proves the M1 contract works from the product UI.

### Current Consumer Routes

#### `.NET GET /Login`

Returns the current Stats Web login experience that consumes the M1 login API.

#### `.NET GET /`

Returns the authenticated main web app landing page after login and required password setup.

#### `.NET GET /Users`

Returns the current Stats Web administrator user management experience that consumes M1 user administration APIs.

### Current Consumer Behaviour to Preserve

- Show email and password inputs and a clear submit action.
- Use email as the login username.
- Submit credentials to `POST /api/v1/auth/login`.
- Store the returned bearer token in browser session storage.
- Retrieve the current user through `GET /api/v1/auth/me` after login.
- When login requires a password change, show password setup before ordinary signed-in actions.
- Submit password setup to `POST /api/v1/auth/change-password`.
- Redirect users who completed login and required password setup to the main web app landing page.
- Show the authenticated user's email, role, and optional full name on the landing page.
- Show an administrator route to user management from the landing page after signed-in admin access is ready.
- Provide sign out that clears the session token and returns to the login page.
- Show a controlled invalid-login message without exposing sensitive backend details.
- Keep the interface usable on desktop and mobile widths.

### Current Consumer User Management Behaviour

- Require an authenticated admin browser session before showing user management data.
- Block user management when first-login password setup is still required.
- List users from `GET /api/v1/users`.
- Create users through `POST /api/v1/users`.
- Capture email, optional full name, temporary password, role, and active status for created users.
- Show that created users must change their temporary password on first login.
- Provide sign out from the user management page.

### Current End-to-End Consumer Flow

Current M1 evidence should preserve a manual Stats Web consumer test that proves the administrator and standard-user paths connect correctly:

1. An administrator signs in through the ASP.NET Core `/Login` page.
2. The administrator reaches the authenticated main app landing page.
3. The administrator opens the `/Users` page from the admin-only user management action.
4. The administrator creates an active standard user with an email address and temporary password.
5. The created user signs in through `/Login` with the temporary password.
6. The created user is required to set a new password before ordinary app access continues.
7. After password setup, the created user reaches the authenticated main app landing page.
8. The standard user does not receive administrator-only user management access.

### Consumer UI Deferred to Stats Web Shell

- Future UI refinement for password reset, registration, navigation, role editing, account deactivation, and password reset controls belongs to Stats Web Shell or later app modules.
- Upload, dashboard, OCR, reporting, and document review UI remain outside the M1 identity module.
- M1 must not absorb Stats-specific presentation code into reusable password, token, role, or persistence internals.
<!-- M1 End -->

## Shared Schemas

The current FastAPI Identity Access implementation must define request and response schemas for authentication and safe user data. Pydantic schemas are the current implementation form.

### Required Schemas

- `LoginRequest`
- `TokenResponse`
- `PasswordChangeRequest`
- `UserCreate`
- `UserUpdate`
- `UserResponse`
- `CurrentUser`

Schemas should avoid exposing `hashed_password` or other internal security fields.

## Error Handling Contract

The current M1 API must return controlled error shapes for identity and authorization failures. The FastAPI implementation uses this response convention:

```json
{
  "type": "ERROR_TYPE",
  "message": "Human-readable error message"
}
```

### Required Error Types

The current implementation may reuse existing API error helpers and should add authentication-specific errors where needed:

- `INVALID_CREDENTIALS`
- `UNAUTHENTICATED`
- `FORBIDDEN`
- `USER_ALREADY_EXISTS`
- `USER_NOT_FOUND`
- `INACTIVE_USER`
- `INVALID_TOKEN`

### Requirements

- Authentication failures must not leak sensitive details.
- Internal exceptions must be logged but not returned to clients.
- Database errors must use the existing database error convention.
- Role failures must return a clear authorization error.

## Security Requirements

- Store only password hashes.
- Never log plain text passwords or access tokens.
- Do not include secrets in source control.
- Use bearer token authentication for protected API routes.
- Apply route-level authorization dependencies consistently.
- Keep development seed credentials out of committed code unless they are placeholders in `.env.example`.
- Use HTTPS in production or cloud deployment documentation.

## Current Schema and Future Migration Boundary

The current implementation must remain able to create the identity user table for local and test execution.

- If Alembic is introduced before Stats Data and Persistence is executed, it must clearly state that it covers the current identity table placement.
- Once `apps/stats-data/` owns the Stats database lifecycle, Stats-specific schema migrations and persistence adapters belong there.
- Identity Access tests must keep a test database setup that does not depend on production credentials.
- If Alembic is deferred, `init_db()` may create the current identity user table for local and test execution and the deferral must remain documented.

## Testing

Module 1 must include tests proving authentication and authorization behavior.

### Carry-Forward Regression Rule

Each completed module adds to the Stats project regression baseline.

- Module 1 testing must include Module 1 verification and Module 0 regression verification.
- When Module 2 is added, its test session must include Module 2 verification plus regression verification for Modules 0 and 1.
- Every later module must continue carrying the earlier completed module tests so new work is checked against the behavior already delivered.
- A prior-module check may be removed from a later regression run only when it is formally replaced, no longer applies, or the test scope is explicitly narrowed and documented.

### Required Tests

- User model can be imported.
- Password hashing does not return the original password.
- Password verification succeeds for the correct password.
- Password verification fails for the wrong password.
- Login succeeds with valid active user credentials.
- Login fails with invalid credentials.
- Login fails or is forbidden for inactive users.
- `GET /api/v1/auth/me` returns the current user when given a valid token.
- Protected endpoint rejects missing tokens.
- Protected endpoint rejects invalid tokens.
- Admin-only endpoint allows admin users.
- Admin-only endpoint rejects standard users.
- Creating a duplicate email returns a controlled error.
- User responses do not expose `hashed_password`.
- Initial administrator can be created before other users exist.
- Initial administrator creation is blocked after users exist.
- Bootstrap administrator login reports that a password change is required.
- Admin-created user login reports that a password change is required until the temporary password is replaced.
- Authenticated user can change a required first-login password.
- Initial administrator can log in, change password, and add a user through the admin API.
- Current Stats Web consumer builds successfully while it is used as the M1 contract consumer.
- Current Stats Web consumer verification covers admin login, administrator user creation, created-user login, required password setup, and authenticated landing-page access against the Module 1 API.

### Test Tooling

- From M13 onward, run module tests inside the Stats runtime container.
- Use FastAPI `TestClient` for endpoint tests.
- Use a test database configuration isolated from development data.
- Use fixtures in module tests for users, tokens, and database sessions where practical.
- Use grouped regression evidence folders under root `tests/results/` for sessions that cover multiple modules so the current module and prior-module regression results remain together.

## Runtime Requirements

### Current Module Runtime

The current `modules/identity-access-module/` runtime defines its own run command, test command, and configuration sample. From M13 onward, official verification runs through the Stats container.

<!-- M13 - Containerization Start -->
### Container Runtime Boundary

M1 official runtime verification and tests run inside the Stats runtime container. Host-started `uvicorn` runs are diagnostics only and must not be recorded as module completion, regression, database validation, or capstone evidence.

The current M1 identity API must connect to the Stats PostgreSQL database when `DATABASE_URL` is configured. That current connection does not make M1 the owner of the future Stats database schema lifecycle.

The current Stats Web consumer is verified through the Docker stack entry point at `http://127.0.0.1:8080` for official evidence.

The Stats Web consumer must read `StatsApi:BaseUrl` from `appsettings.json` or a supported override such as `STATS_API_BASE_URL` before it starts.
<!-- M13 End -->

## Dependencies

Module 1 requires these additional or confirmed dependencies:

- `sqlalchemy`
- `psycopg` or `psycopg2-binary`
- `passlib[bcrypt]` or equivalent password hashing library
- `python-jose[cryptography]` or equivalent JWT library
- `email-validator`
- Container-executed module tests
- `httpx`
- `alembic` if identity migrations are introduced before Stats Data owns the Stats schema lifecycle

PDF-specific dependencies do not belong to the reusable Identity Access Module contract and must not expand M1 behavior.

## Acceptance Criteria

Module 1 is complete when:

- The identity contract defines the account, credential, role, claims, token, and authorization data required by consumers.
- The current Stats implementation persists identity account data through the configured PostgreSQL `stats` database while Stats Data ownership is pending.
- Current M1 runtime values are config-file driven and do not require backend or Stats Web source edits when API targets, bind settings, CORS origins, database URLs, token settings, or bootstrap values change.
- Passwords are stored as secure hashes only.
- Login returns a bearer access token.
- Protected routes reject missing, invalid, and expired tokens.
- Authenticated users can retrieve their own profile.
- Admin users can create and list users.
- Standard users cannot access administrator-only endpoints.
- User responses never expose password hashes.
- A fresh current Stats identity persistence store can create the first administrator through the local bootstrap command.
- The first administrator is required to set a new password on first login before user-management actions continue.
- Admin-created users are required to replace their administrator-provided temporary password on first login before ordinary protected access continues.
- The system keeps at least one active administrator by blocking last-admin deactivation and demotion.
- The identity contract exposes login, current-user, password-change, token, role, and user-administration behavior without depending on Stats-specific page code.
- The current Stats Web consumer can submit credentials to the Module 1 login API, show current-user identity, and clear browser-session token material on sign out.
- The current Stats Web consumer can route authenticated users who completed required password setup to its ASP.NET Core main app landing page.
- The current Stats Web administrator consumer can list users and create temporary-password users after password setup is complete.
- A standard user created through the current Stats Web consumer can sign in, replace the temporary password, and reach the app landing page without administrator-only user management access.
- Authentication and authorization errors use consistent response shapes.
- Tests for login, protected access, and role restrictions pass.
- Later modules and alternate consumers can reuse the identity claims and authorization contract.

## Implementation Notes

- Prefer the current SQLAlchemy ORM/service split over raw SQL while the identity persistence code remains in the FastAPI implementation.
- Keep authentication logic in service and utility modules rather than embedding it directly in route handlers.
- Keep route handlers thin and focused on request/response behavior.
- Use current settings, database, error, logging, and router patterns within the active FastAPI module surface.
- Keep Stats Web consumer behaviour focused on login, first-login password setup, landing-page access, user management, auth error feedback, and sign out until the Stats Web Shell spec refines the app UI.
- Reusable identity code and module-local automated tests now live under `modules/identity-access-module/`; Stats-specific Razor Pages now live under `apps/stats-web/`; project documentation and evidence live under root `docs/` and `tests/results/`.
- Avoid implementing document-specific ownership rules until Stats Data and the relevant workflow specs define document models and user associations.

<!-- M1 End -->
