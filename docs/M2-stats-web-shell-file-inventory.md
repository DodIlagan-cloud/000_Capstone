<!-- M2 - Stats Web Shell Start -->
<!-- Documents the files created or modified for Module 2 Stats Web Shell. -->

# M2 Stats Web Shell File Inventory

## Summary

This document lists the files created or modified for **M2 - Stats Web Shell** and describes the purpose of each change.

M2 establishes `apps/stats-web/` as the Stats product web shell. It preserves the M1 Identity Access consumer flow while adding the dashboard-first home page, upload-documents action page, email-ingestion setup action page, document/report shell surfaces, and configurable downstream module targets.

## Specification and Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M2-stats-web-shell-spec.md` | Created/Modified | Defines the Module 2 specification, including the Stats Web Shell boundary, goals, non-goals, M1 consumer requirements, later-module upload checkpoint boundary, configuration, tests, evidence, and acceptance criteria. |
| `docs/M2-stats-web-shell-file-inventory.md` | Created | Documents the M2 files created or modified and explains the purpose of each change. |

## Application Configuration and Startup

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/Program.cs` | Modified | Adds `StatsWebShellOptions` so shell feature flags, deferred downstream endpoints, Power BI/Fabric placeholders, and Azure deployment settings are supplied through ASP.NET Core configuration. |
| `apps/stats-web/appsettings.json` | Modified | Adds committed safe defaults for upload, email setup, dashboard/reporting shell, merged file intake endpoints, future Power BI/Fabric identifiers, and Azure managed identity/Key Vault placeholders. |

## Razor Pages

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/Pages/Index.cshtml` | Modified | Updates the authenticated landing page into the dashboard-first Stats workspace shell with upload-documents and email-ingestion setup action buttons. |
| `apps/stats-web/Pages/Index.cshtml.cs` | Modified | Supplies shell feature flags to the authenticated landing page. |
| `apps/stats-web/Pages/Users.cshtml` | Modified | Adds shell navigation links to the administrator user-management page while preserving M1 behavior. |
| `apps/stats-web/Pages/Upload.cshtml` | Created/Modified | Adds the authenticated upload-documents action page and later-module checkpoint surface for M3/M4/M5/M7/M8 results. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Created | Supplies configured API settings to the upload-documents action page. |
| `apps/stats-web/Pages/EmailSetup.cshtml` | Created | Adds the authenticated email-ingestion setup action page with a controlled deferred state. |
| `apps/stats-web/Pages/EmailSetup.cshtml.cs` | Created | Supplies configured API settings to the email-ingestion setup page. |
| `apps/stats-web/Pages/Documents.cshtml` | Created | Adds the authenticated document-status shell with a controlled empty/deferred state. |
| `apps/stats-web/Pages/Documents.cshtml.cs` | Created | Supplies configured API settings to the document-status shell page. |
| `apps/stats-web/Pages/Reports.cshtml` | Created | Adds the authenticated reports shell with a controlled deferred report state. |
| `apps/stats-web/Pages/Reports.cshtml.cs` | Created | Supplies configured API settings to the reports shell page. |

## Frontend Assets

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/wwwroot/js/app.js` | Modified | Allows the existing M1 access guard to be reused by shell pages that do not render user identity fields. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Adds shell navigation, deferred states, dashboard cards, ingestion action buttons, and mobile layout styling for M2. |

## Verification Artefacts

| File or Folder | Change Type | Description |
| --- | --- | --- |
| `tests/results/M2-StatsWebShell-M0-M1/` | Created | Stores M2 build/test evidence and carried-forward M0/M1 regression notes for this execution session. |

## Notes

- M2 keeps authentication and authorization behavior delegated to the M1 Identity Access API.
- Dashboard, email setup, document tracking, and reports are shell surfaces only until their owning modules exist. Upload documents is now a shell-owned presentation/orchestration surface that can call M3/M4/M5/M7/M8 while keeping reusable rules in those backend modules.
- Official M2 acceptance evidence after M13 must come from the Docker stack and `stats-runtime`; older host-side build/browser evidence remains historical.
- Module 2 code blocks were tagged using the `M2 - Stats Web Shell Start` and `M2 End` convention.

<!-- M2 End -->
