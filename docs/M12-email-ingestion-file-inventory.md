<!-- M12 - Email Ingestion Module Start -->

# M12 Email Ingestion File Inventory

| File | Status | Purpose |
| --- | --- | --- |
| `docs/M12-email-ingestion-module-spec.md` | Created / Updated | Defines M12 goals, contract, automated pathway, configuration, testing, and acceptance criteria. Updated to make the production path cloud-hosted provider-neutral IMAP ingestion with multiple mailbox source profiles, Azure Blob-backed attachment intake, Stats Web setup-tab requirements, password-protected PDF handling, and phased implementation. |
| `docs/M12-email-ingestion-file-inventory.md` | Created | Tracks files created or modified for the M12 implementation slice. |
| `modules/email-ingestion-module/README.md` | Created | Documents module boundary, runtime, tests, and secret handling. |
| `modules/email-ingestion-module/requirements.txt` | Created | Defines Python runtime/test dependencies. |
| `modules/email-ingestion-module/config/defaults.env` | Created | Provides committed safe defaults for local/container runtime. |
| `modules/email-ingestion-module/app/main.py` | Created | Builds the FastAPI app and registers health and email-ingestion routes. |
| `modules/email-ingestion-module/app/config.py` | Created | Loads M12 configuration from defaults, ignored local env, and environment variables. |
| `modules/email-ingestion-module/app/models/common.py` | Created | Defines service metadata response models. |
| `modules/email-ingestion-module/app/models/ingestion.py` | Created | Defines automated email ingestion request/result and source profile contracts. `EmailSourceProfileUpdate` accepts `connection_settings` so custom IMAP host/port edits persist on PATCH. |
| `modules/email-ingestion-module/app/routes/health.py` | Created | Exposes `/health` and root metadata endpoints. |
| `modules/email-ingestion-module/app/routes/ingestions.py` | Created | Exposes `/api/v1/email-ingestions/automated-runs`. |
| `modules/email-ingestion-module/app/services/ingestion_service.py` | Created / Modified | Implements attachment filtering, deduplication, summary generation, and optional M3/M4 handoff. Adds safe structured handoff trace logging for imported files, including run ID, source profile ID, message ID, attachment ID, M3/M4 ingestion ID, handoff status, and Blob content reference without logging passwords or raw attachment content. |
| `modules/email-ingestion-module/app/services/source_profile_service.py` | Created | Stores multi-mailbox source profile metadata without retaining raw app passwords. Profile updates merge and re-validate so nested policies (including multiple `pdf_password_policy.password_rules`) stay typed models, keeping the in-memory and Azure SQL stores consistent. |
| `modules/email-ingestion-module/app/services/imap_service.py` | Created | Adds the provider-neutral IMAP adapter boundary for cloud mailbox connection tests and message retrieval. |
| `modules/email-ingestion-module/app/services/secret_service.py` | Created / Modified | Adds secret-reference helpers and encrypted central secret storage so mailbox and PDF passwords stay outside API responses and code. |
| `modules/email-ingestion-module/app/routes/sources.py` | Created | Exposes source profile list/create/update/test-connection endpoints for the Email Setup tab. |
| `apps/stats-data/migrations/azure-sql/email_ingestion_sources.sql` | Created | Adds central Azure SQL tables for mailbox source profile settings, run/test status metadata, and encrypted email secret values. |
| `apps/stats-web/Pages/EmailSetup.cshtml` | Modified | Replaces the placeholder setup page with the operational mailbox source profile, connection test, and manual ingestion controls. Includes a structured add/edit/remove PDF password rules editor (rule id, display name, secret reference, sender/subject/filename match keywords, enabled) backed by a `<template>`, replacing the prior raw JSON textarea. |
| `apps/stats-web/wwwroot/js/email-setup.js` | Created | Connects the setup tab to the M12 source profile and automated-run APIs without echoing app passwords back to the browser. Builds the PDF password rules array from the structured editor cards and validates that each saved rule has a rule id and password secret reference. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Adds layout and responsive styling for the Email Ingestion Setup source/profile/run panels, including the PDF password rule cards. |
| `tests/unit/email_ingestion_module/conftest.py` | Created | Provides isolated app import and test fixtures. |
| `tests/unit/email_ingestion_module/test_ingestion_service.py` | Created / Modified | Covers M12 automated pathway behavior, source profile setup, IMAP adapter delegation, and password-protected PDF status handling. Adds coverage for profile-update round-trip of multiple PDF password rules plus `connection_settings`, multiple source profiles sharing one mailbox address with distinct folders/filters/password rules, and safe handoff trace logs for imported files. |
| `modules/email-ingestion-module/test-results/m12-email-ingestion-evidence-test-cases-2026-06-29.md` | Created | Defines the M12 evidence-driven manual/browser/API test matrix for the 2026-06-29 Email Setup and runtime changes, including saved secrets, folder usage, IMAP simplification, PDF password collapse, Select action, pagination, PDF-only retrieval, message limits, and security log checks. |
| `modules/email-ingestion-module/test-results/m12_email_ingestion_runtime_evidence_check.py` | Created | Provides a repeatable local container evidence check that verifies the runtime Email Setup page, served JavaScript, M12 health, source-profile API privacy, central secret availability by reference, and saved-secret Test connection path without printing secret values. |
| `modules/email-ingestion-module/test-results/m12_email_ingestion_blob_evidence_check.py` | Created | Provides a repeatable post-import evidence check that lists imported files in the configured Azure Blob intake container/prefix for terminal screenshot evidence without printing storage secrets or file contents. |
| `tests/scripts/regression/run_module_unit_tests.ps1` | Modified | Adds the M12 unit test suite to the container-first module runner. |
| `infrastructure/containers/stats/Dockerfile` | Modified | Packages M12 dependencies and source into the Stats runtime image. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Modified | Starts and health-checks the M12 API inside the single Stats runtime. |
| `infrastructure/containers/stats/.env.container.example` | Modified | Documents M12 runtime variables. |
| `infrastructure/compose/stats-runtime.compose.yml` | Modified | Passes M12 runtime configuration into the Stats container. |
| `tests/integration/test_m13_containerization_contract.py` | Modified | Adds static checks that M12 is packaged and started. |
| `config/stats.runtime.json` | Modified | Registers M12 port and email-ingestion configuration keys. |
| `modules/README.md` | Modified | Marks the Email Ingestion Module as implemented. |

<!-- M12 End -->
