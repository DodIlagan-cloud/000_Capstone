<!-- M2 - Stats Web Shell Start -->
<!-- Specifies the Stats Web encompassing app shell, navigation, identity consumption, and orchestration boundaries. -->

# Module 2 Stats Web Shell Specification

## Module Summary

Module 2 establishes the Stats Web Shell as the user-facing ASP.NET Core application for the Stats capstone project. It provides the authenticated web experience, product navigation, layout, access-state handling, and orchestration points that later document-processing modules will connect to.

This module builds on M0 Project Foundation and consumes the M1 Identity Access Module. It does not implement reusable authentication internals, file validation rules, file ingestion processing, OCR, classification, transaction extraction, data validation, Stats database persistence, reporting calculations, email ingestion, containerization, or cloud deployment.

M2 turns the current M1 access-flow consumer into an explicit Stats product app boundary.

## Architecture Alignment

M2 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M1-user-management-access-control-spec.md`

The building-block plan defines this module as:

| Field | M2 Direction |
| --- | --- |
| Build order | `2` |
| Module | Stats Web Shell |
| Type | Encompassing `.NET` app |
| Main responsibility | Login UI, app navigation, service orchestration shell |
| Reusable contract | Calls module APIs; no OCR/parsing logic |
| Owner folder | `apps/stats-web/` |

## Business Analysis Alignment

M2 supports the product-facing parts of these business-analysis areas:

- User Management and Access Control: presents login, sign out, current-user context, password setup, and administrator user-management access by consuming M1 APIs.
- Manual Document Upload: prepares an authenticated upload-documents action page and handoff boundary for later File Validation and File Ingestion modules.
- Email Ingestion: prepares an authenticated email ingestion setup action page for the later Email Ingestion Module.
- Dashboard and Reporting: makes the authenticated home page the dashboard shell and prepares report pages for later reporting modules.

The business need is to give users a stable, authenticated Stats workspace before the document-processing pipeline is expanded. The app shell should make later upload, processing status, dashboard, and reporting workflows feel like one coherent product while keeping reusable backend rules in their own modules.

## Goals

- Define `apps/stats-web/` as the Stats-specific web application boundary.
- Preserve current M1 login, first-login password setup, sign out, current-user display, and administrator user-management consumer behavior.
- Provide a consistent authenticated app layout where the home page is the dashboard shell, with primary actions for uploading documents and setting up email ingestion.
- Keep all Identity Access behavior behind M1 API calls and browser session handling.
- Prepare a manual-upload action page that can later call File Validation and File Ingestion APIs without embedding validation or ingestion rules.
- Prepare an email-ingestion setup action page that can later call the Email Ingestion Module without embedding mailbox retrieval logic.
- Prepare dashboard/reporting placeholders that do not calculate final financial analytics before later modules define persistence and reporting contracts.
- Keep service base URLs and runtime settings configurable through ASP.NET Core configuration providers.
- Keep the app usable on desktop and mobile widths.
- Provide M2-focused verification plus regression checks for M0 and M1.

## Tasks

1. Preserve the current Stats Web runtime under `apps/stats-web/`.
2. Refine the shell layout, authenticated navigation, access guard behavior, and session-token helpers.
3. Keep `/Login`, `/`, and `/Users` working against the M1 Identity Access API.
4. Add or prepare the dashboard home, upload-documents, email-ingestion setup, document status, and report routes as shell surfaces only.
5. Define API-client configuration so later module base URLs can be supplied without editing source code.
6. Keep M2 code and documentation tagged with the `M2 - Stats Web Shell` convention where comments are supported.
7. Add or update automated and manual checks for shell navigation, protected access, role-aware visibility, responsive layout, and M1 regression flows.
8. Capture M2 evidence in a named root `test-results/` evidence folder that includes raw output, checklist, and actual Windows browser/terminal screenshots where applicable.

## Non-Goals

- Implementing password hashing, token signing, token validation internals, role logic, or identity persistence.
- Replacing the M1 Identity Access Module with ASP.NET Core Identity.
- Implementing file content validation, MIME/signature checks, hash generation, or rejection-rule logic.
- Implementing file ingestion job storage, queues, OCR handoff, or processing status persistence.
- Implementing OCR, document classification, transaction extraction, data cleaning, duplicate detection, or confidence scoring.
- Implementing Stats database schema, migrations, persistence adapters, or dashboard queries.
- Implementing final financial dashboards, report exports, or analytics calculations.
- Implementing email ingestion.
- Containerizing or deploying the app to cloud.

## Architecture Boundary

### Owner Folder

M2 owns:

```text
apps/stats-web/
```

This folder owns Stats-specific Razor Pages, app layout, client-side scripts, styling, static assets, web runtime configuration, and module-local automated tests if added.

M2 specifications, file inventories, project-level documentation, and assessment evidence belong under root `docs/` and root `test-results/`.

### M2 Owns

- ASP.NET Core app startup for Stats Web.
- Razor Pages and page models for the Stats user experience.
- Shared layout, navigation, route structure, and responsive UI.
- Browser-side session-token storage and access guards while M1 remains token-based.
- Calls to the M1 Identity Access API for login, current-user, password setup, sign out behavior, and administrator user management.
- Shell pages or placeholders for dashboard home, document upload, email ingestion setup, document status, and reporting areas.
- Configured API base URLs and feature switches needed by the web app.
- Configured placeholders for future Power BI/Fabric dashboard embedding and Azure deployment settings.
- Controlled frontend error and empty states for unavailable downstream modules.

### M2 Calls

- M1 Identity Access Module through configured HTTP API base URL.
- Later File Ingestion or workflow APIs only after those modules define their contracts.
- Later Stats Data/query APIs only after Stats Data and Reporting modules define their contracts.

### M2 Must Not Absorb

- M1 password, token, role, or user persistence internals.
- File validation or ingestion rules from M3/M4.
- OCR, classification, transaction extraction, or data validation rules from later reusable modules.
- Stats database schema or migrations from Stats Data and Persistence.
- Dashboard calculations that depend on undefined persistence/query contracts.

## Required Project Structure

The current M2 app surface is:

```text
apps/stats-web/
  stats.Web.csproj
  Program.cs
  appsettings.json
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

M2 may add shell-specific pages, page models, scripts, styles, and assets under the same app folder.

Expected future M2 shell routes include:

| Route | Purpose |
| --- | --- |
| `/Login` | M1 login and required password setup consumer page. |
| `/` | Authenticated Stats dashboard/workspace shell with upload and email-ingestion setup action buttons. |
| `/Users` | Administrator user-management consumer page for M1. |
| `/Upload` | Authenticated upload-documents action page prepared for later ingestion contracts. |
| `/EmailSetup` | Authenticated email-ingestion setup action page prepared for later email ingestion contracts. |
| `/Documents` | Authenticated document status shell prepared for later workflow state. |
| `/Reports` | Authenticated reports shell prepared for later report views or exports. |

Routes that depend on later modules may show controlled "not connected yet" or empty states until the relevant module is implemented.

## Stats Web Input and Output Contract

M2 is an encompassing app, so its contracts are consumer-facing screens and configured service calls rather than a reusable backend API.

### Inputs

| Input | Source | Description |
| --- | --- | --- |
| User credentials | Browser user | Email and password submitted to M1 login API. |
| Password setup command | Browser user | New password submitted to M1 password-change API when required. |
| Browser session token | M1 Identity Access API | Bearer token stored for the active browser session. |
| Current-user profile | M1 Identity Access API | User email, role, full name, active status, and password-state information used by the shell. |
| Admin user command | Browser admin user | User-create or user-list interaction submitted to M1 user APIs. |
| Future upload candidate | Browser user | File selected for manual upload, held at shell boundary until File Validation and File Ingestion contracts are implemented. |
| Runtime configuration | ASP.NET Core configuration | API base URLs, feature switches, and environment-specific runtime values. |
| Future reporting configuration | ASP.NET Core configuration or Azure provider | Power BI/Fabric workspace, report, capacity, and embed-config endpoint settings for later M11 implementation. |
| Azure deployment configuration | ASP.NET Core configuration or Azure provider | Environment label, Key Vault URI, and managed identity switch for later cloud deployment. |

### Outputs

| Output | Consumer | Description |
| --- | --- | --- |
| Authenticated web session | Browser user | User reaches the Stats shell after valid login and required password setup. |
| Role-aware navigation | Browser user | Admin-only and user-level actions are visible or hidden based on M1 profile data. |
| Identity API requests | M1 Identity Access API | Login, current-user, password-change, and user-management requests. |
| Shell page state | Browser user | Dashboard home, upload, email setup, document, and report surfaces render controlled states. |
| Future module handoff | Later modules | Prepared UI boundaries for upload and workflow calls after contracts exist. |
| Future dashboard embed request | Later reporting module | Prepared configuration boundary for a backend embed-config endpoint after M11 defines Power BI/Fabric integration. |
| Frontend errors | Browser user | Clear messages for invalid credentials, unauthorized access, unavailable APIs, or deferred features. |

## M1 Identity Consumer Requirements

M2 must preserve these M1 consumer behaviors:

- Submit login credentials to `POST /api/v1/auth/login`.
- Store only the bearer token needed for the active browser session.
- Retrieve current-user context from `GET /api/v1/auth/me`.
- Show required password setup when M1 returns `password_change_required=true`.
- Submit required password setup to `POST /api/v1/auth/change-password`.
- Redirect authenticated users who completed password setup to the app shell.
- Show current-user identity and role in the shell.
- Allow sign out to clear browser session state and return to `/Login`.
- Restrict administrator user management to authenticated admin users.
- Prevent users who still require password setup from using ordinary app features.
- Display controlled messages for invalid credentials, missing token, forbidden access, and unavailable API responses.

## Manual Upload Shell Boundary

M2 introduces the visual upload-documents action page, but the executable upload workflow remains deferred until the relevant modules are implemented.

The M2 upload-documents shell may own:

- Authenticated route guard.
- File picker UI.
- Drag-and-drop visual state.
- Static upload guidance text that does not encode validation rules.
- Disabled or stubbed submit state when ingestion APIs are not configured.
- Controlled empty state showing that ingestion is not connected yet.

M2 must not own:

- Allowed file type policy.
- File signature validation.
- File hash generation.
- File persistence.
- Ingestion job creation.
- OCR handoff.

Those behaviors belong to M3 File Validation Module and M4 File Ingestion Module.

## Email Ingestion Setup Boundary

M2 may introduce the visual email ingestion setup action page, but mailbox authorization, retrieval, attachment filtering, polling, and email-to-ingestion handoff remain deferred until the Email Ingestion Module is implemented.

The M2 email setup shell may own:

- Authenticated route guard.
- Placeholder page structure for mailbox connection and setup state.
- Static setup text that does not encode mailbox retrieval rules.
- Controlled deferred state showing that email ingestion is not connected yet.

M2 must not own:

- Mailbox authorization.
- Email polling or retrieval.
- Attachment filtering.
- Email deduplication.
- Email-to-file-ingestion handoff.

Those behaviors belong to M12 Email Ingestion Module.

## Dashboard and Reporting Shell Boundary

M2 introduces the authenticated home page as the dashboard shell and may introduce placeholder report pages.

The M2 dashboard/reporting shell may own:

- Authenticated route guard.
- Page structure and navigation.
- Empty states for no data or deferred reporting.
- Configured API-client placeholders for later data calls.

M2 must not own:

- Financial calculations.
- Data-quality summaries.
- Stored document/transaction queries.
- Export formats.
- Dashboard aggregation logic.
- Power BI/Fabric embed token generation.
- Power BI/Fabric report publishing, workspace administration, or semantic model refresh.

Those behaviors belong to Stats Data and Persistence, Stats Workflow Integration, and Stats Dashboard and Reporting.

### Future Power BI/Fabric Boundary

The dashboard is expected to come from Power BI or Microsoft Fabric in a later module. M2 only prepares configuration placeholders and keeps the dashboard shell separate from implementation.

M2 may own:

- A dashboard shell route.
- Non-secret configuration keys for workspace/report/capacity identifiers.
- A future reporting embed-config endpoint URL setting.
- A deferred dashboard state when reporting is not connected.

M2 must not own:

- Power BI REST API calls.
- Embed token generation.
- Service principal credentials.
- Report authoring or deployment.
- Dataset/semantic model refresh.
- Row-level security implementation.

Those behaviours belong to M11 Stats Dashboard and Reporting, supported by M9 Stats Data and Persistence and M10 Stats Workflow Integration.

## File Tagging Convention

Any new file created for M2 should include a short top-of-file start comment identifying the module and file purpose when the file type supports comments.

Any meaningful code, configuration, route, test, or documentation section added to an existing file should include a nearby M2 start tag, a short purpose comment, and a matching end tag when the file type supports comments.

M2 files must use this label:

```text
M2 - Stats Web Shell Start
```

The end tag may be shortened to:

```text
M2 End
```

Examples:

```csharp
// M2 - Stats Web Shell Start
// Configures Stats Web shell services and route behavior.

...

// M2 End
```

```html
@* M2 - Stats Web Shell Start *@
@* Provides authenticated shell navigation. *@

...

@* M2 End *@
```

```markdown
<!-- M2 - Stats Web Shell Start -->
<!-- Specifies Stats Web shell requirements. -->

...

<!-- M2 End -->
```

Tiny formatting-only edits, generated files, binary assets, screenshots, lockfiles, and files that do not support comments do not need tags.

## Configuration

M2 must follow the M0 runtime configuration standard. Runtime values must be supplied through `appsettings.json`, ASP.NET Core environment-specific configuration files, environment variables, user secrets, or managed secret providers rather than hardcoded into app source.

### Current Config Files

| Config File | Purpose |
| --- | --- |
| `apps/stats-web/appsettings.json` | Committed safe local defaults for Stats Web runtime configuration. |
| `apps/stats-web/appsettings.Development.json` | Optional local development overrides if introduced. |
| ASP.NET Core environment variables | Runtime overrides for deployment, local scripts, or evidence sessions. |
| ASP.NET Core user secrets, Azure Key Vault, or managed secrets | Local or production secret values if later needed. |

### Required Settings

| Setting | Default | Description |
| --- | --- | --- |
| `StatsApi:BaseUrl` | `http://127.0.0.1:8013` | Current M1 Identity Access API base URL consumed by Stats Web. |
| `StatsWeb:Features:UploadShell` | `true` when introduced | Enables the M2 upload-documents action page without enabling ingestion behavior. |
| `StatsWeb:Features:EmailIngestionSetup` | `true` when introduced | Enables the M2 email-ingestion setup action page without enabling mailbox retrieval. |
| `StatsWeb:Features:DashboardShell` | `true` when introduced | Enables dashboard/reporting shell surfaces without final reporting logic. |
| `StatsWeb:Features:ReportsShell` | `true` when introduced | Enables the M2 reports shell without report generation. |
| `StatsWeb:Downstream:FileIngestionBaseUrl` | empty until M4 | Future File Ingestion API target after contract implementation. |
| `StatsWeb:Downstream:EmailIngestionBaseUrl` | empty until M12 | Future Email Ingestion API target after contract implementation. |
| `StatsWeb:Downstream:StatsDataBaseUrl` | empty until later app modules | Future Stats Data or reporting query target after contract implementation. |
| `StatsWeb:Downstream:ReportingEmbedConfigUrl` | empty until M11 | Future backend endpoint that will return Power BI/Fabric embed configuration. |
| `StatsWeb:PowerBi:TenantId` | empty until M11/cloud setup | Future Microsoft Entra tenant ID for Power BI embedding. |
| `StatsWeb:PowerBi:WorkspaceId` | empty until M11/cloud setup | Future Power BI/Fabric workspace ID for the dashboard report. |
| `StatsWeb:PowerBi:DashboardReportId` | empty until M11/cloud setup | Future Power BI report ID for the dashboard. |
| `StatsWeb:PowerBi:DatasetId` | empty until M11/cloud setup | Future semantic model/dataset ID when needed by reporting integration. |
| `StatsWeb:PowerBi:EmbedMode` | `AppOwnsData` | Planned embed mode; final licensing/capacity decision belongs to M11/cloud readiness. |
| `StatsWeb:Fabric:CapacityName` | empty until M11/cloud setup | Future Fabric capacity name or identifier. |
| `StatsWeb:Fabric:WorkspaceName` | empty until M11/cloud setup | Future Fabric workspace display name for operational clarity. |
| `StatsWeb:Fabric:LakehouseName` | empty until M9/M11 | Future Fabric lakehouse reference if Fabric storage/semantic model is used. |
| `StatsWeb:Fabric:SemanticModelName` | empty until M11 | Future semantic model display name. |
| `StatsWeb:Azure:Environment` | `local` | Environment label such as `local`, `dev`, `test`, or `prod`. |
| `StatsWeb:Azure:UseManagedIdentity` | `false` locally | Enables Azure managed identity usage in deployed environments when implemented. |
| `StatsWeb:Azure:KeyVaultUri` | empty locally | Future Azure Key Vault URI for secrets or protected settings. |

Environment variables should be able to override these values through the ASP.NET Core configuration pipeline. `STATS_API_BASE_URL` may remain supported for the current M1 identity API target.

### Hardcoded Runtime Values

Hardcoded runtime values allowed in source: none unless explicitly justified as stable code constants.

Examples that must remain configurable:

- API base URLs.
- Hosts and ports.
- Feature switches.
- Downstream module endpoints.
- Power BI/Fabric workspace, report, semantic model, capacity, and embed mode settings.
- Azure environment, Key Vault, and managed identity settings.
- Browser-visible environment labels.
- Timeouts and retry settings if added.

## Error and Status Results

| Result | User-Facing Meaning |
| --- | --- |
| Invalid credentials | Login failed without revealing whether email or password was wrong. |
| Password setup required | User must choose a new password before ordinary shell access. |
| Unauthenticated | User is returned to `/Login` because no valid browser session exists. |
| Forbidden | User is signed in but lacks the required role for the attempted page/action. |
| Identity API unavailable | Shell shows a controlled service-unavailable message and does not expose raw exception details. |
| Deferred feature | Shell route is visible but processing is not connected until the owning module is implemented. |
| Validation/ingestion unavailable | Upload submit is disabled or returns a controlled message until M3/M4 contracts exist. |

## Runtime Requirements

### Local Run Command

Run Stats Web from:

```text
apps/stats-web
```

Command:

```powershell
dotnet run --urls "http://127.0.0.1:5013"
```

The M1 Identity Access API must be running and reachable at the configured `StatsApi:BaseUrl` for login and user-management flows.

### Local Build Command

```powershell
dotnet build
```

### Current Identity API Runtime

Run the current M1 API from:

```text
modules/identity-access-module
```

Command:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8013
```

### Dependencies

M2 currently depends on:

- .NET SDK compatible with `apps/stats-web/stats.Web.csproj`.
- ASP.NET Core Razor Pages.
- A reachable M1 Identity Access API for authentication flows.
- Browser JavaScript for session state and API calls.
- Existing static assets in `apps/stats-web/wwwroot/`.

M2 must not add OCR, document parsing, database, or Python processing dependencies to the Stats Web app.

## Testing

M2 verification must include automated build checks, browser-level manual or scripted checks, and regression checks for previously completed modules.

### Carry-Forward Regression Rule

Each completed module adds to the Stats project regression baseline.

- M2 testing must include M2 verification plus regression verification for M0 and M1.
- M0 regression should verify architecture, configuration, and evidence conventions still hold.
- M1 regression should verify login, password setup, admin user management, protected access, and role restrictions still work after shell changes.
- A prior-module check may be removed only when formally replaced, no longer applicable, or explicitly narrowed and documented.

### Required Checks

| Check | Level | Evidence |
| --- | --- | --- |
| Stats Web builds successfully | Automated | `dotnet build` raw output. |
| Stats Web starts with configured API base URL | Direct/manual | Terminal output and browser screenshot. |
| `/Login` renders and submits credentials to M1 | Browser integration | Browser screenshot plus capture output. |
| Required password setup still blocks ordinary shell access | Browser integration | Browser screenshot and checklist result. |
| Authenticated home shell displays current-user context | Browser integration | Browser screenshot. |
| Sign out clears browser session and returns to login | Browser integration | Browser screenshot. |
| `/Users` is visible/usable for admin users | Browser integration | Browser screenshot and M1 API evidence. |
| `/Users` is hidden or blocked for standard users | Browser integration | Browser screenshot/checklist. |
| Authenticated home page is the dashboard shell and shows upload/email setup actions | Browser/manual | Browser screenshot and checklist. |
| Upload-documents action page is authenticated and shows controlled deferred state | Browser/manual | Browser screenshot and checklist. |
| Email-ingestion setup action page is authenticated and shows controlled deferred state | Browser/manual | Browser screenshot and checklist. |
| Report routes are authenticated and show controlled deferred state | Browser/manual | Browser screenshot and checklist. |
| Mobile width layout has no overlapping controls or unreadable text | Browser/manual | Mobile-width screenshot. |
| M0 architecture regression passes | Direct | M0 raw output or documented replacement. |
| M1 identity regression passes | Automated/browser | M1 raw output, database check, and browser evidence. |

### Suggested Evidence Folder

Use the root grouped evidence folder:

```text
test-results/M2-StatsWebShell-M0-M1/
```

Expected evidence artefacts:

- `M2-StatsWebShell-test-results-YYYY-MM-DD.md`
- `M2-StatsWebShell-test-raw-output-YYYY-MM-DD.txt`
- `M2-StatsWebShell-manual-test-checklist.md`
- `M2-StatsWebShell-screenshot-evidence-YYYY-MM-DD.md`
- Actual Windows browser screenshots for login, dashboard home with upload/email setup actions, upload-documents page, email-ingestion setup page, admin user management, report shell, and mobile layout.
- Actual Windows terminal screenshot for build/test commands when required for assessment evidence.

## Acceptance Criteria

M2 is complete when:

- `apps/stats-web/` is explicitly documented as the Stats Web Shell owner folder.
- The app builds successfully with `dotnet build`.
- Runtime service targets and shell feature switches are configurable without source edits.
- Existing M1 login, password setup, authenticated landing, sign out, and administrator user-management flows still work from Stats Web.
- Authenticated users can reach the main Stats shell after completing required password setup.
- Users who are not signed in are redirected or blocked from authenticated shell routes.
- Standard users cannot access administrator-only user-management functions.
- Admin-only navigation is visible only when the M1 current-user role allows it.
- The shell provides a dashboard-first authenticated home page with upload-documents and email-ingestion setup action buttons.
- Upload, email setup, dashboard, and report areas do not pretend to process real documents, retrieve mailbox data, or calculate financial data before their owning modules exist.
- Deferred downstream features show controlled empty/unavailable states.
- The app remains usable on desktop and mobile widths.
- M2 evidence includes build output, browser evidence, manual checklist, and M0/M1 regression evidence.
- M2 evidence is stored under root `test-results/`, not under `apps/stats-web/`.
- M2 code and documentation changes are traceable through file tags and a file inventory when implementation work is added.

## Deferred Items

- M3 File Validation Module will define file rules, signatures, size limits, metadata, hashes, and rejection reasons.
- M4 File Ingestion Module will define upload intake, ingestion records, status, and downstream handoff.
- M5 OCR Extraction Module will extract text and metadata from accepted documents.
- M6 Document Classification Module will identify document types.
- M7 Transaction Extraction Module will extract financial fields and transaction candidates.
- M8 Data Validation Module will clean, normalize, warn, and detect duplicate/incomplete records.
- M9 Stats Data and Persistence will define the product database schema, migrations, persistence adapters, and workflow result storage.
- M10 Stats Workflow Integration will connect the shell to the processing pipeline.
- M11 Stats Dashboard and Reporting will implement final dashboard and report behavior.
- M13/M14 will cover containerization and cloud readiness.

## Implementation Notes

- Prefer the existing Razor Pages structure unless a change clearly reduces complexity.
- Keep route/page models thin; reusable business rules belong in backend modules.
- Keep browser scripts focused on API calls, session state, access guards, and UI state.
- Keep product styling in `apps/stats-web/wwwroot/css/` and avoid introducing unrelated frontend frameworks unless the project chooses one explicitly.
- Preserve the current M1 API contract while the shell evolves.
- Use clear empty states for deferred pages so assessment reviewers can distinguish completed shell work from later processing modules.

<!-- M2 End -->
