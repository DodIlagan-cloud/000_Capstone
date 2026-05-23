# Common File Migration Inventory

<!-- M0 Foundation Start -->
<!-- Records the current ownership map after retiring the old transitional code folders. -->

## Purpose

This inventory records the current architecture owner folders for shared, common, configuration, persistence, and support files after the initial M1 migration.

New work should be created directly in the owner folder. Retired transitional folders must not be recreated.

## Ownership Rules

- Runtime values must stay config-driven. URLs, ports, database targets, secrets, token settings, browser origins, paths, limits, and feature switches must not be hardcoded in source.
- Stats-specific persistence belongs to `apps/stats-data/`.
- Stats UI and orchestration belong to `apps/stats-web/`.
- Reusable identity logic belongs to `modules/identity-access-module/`.
- Reusable API contracts belong to `contracts/`.

## Current Owner Map

| Area | Owner | Notes |
| --- | --- | --- |
| Stats Web UI and orchestration | `apps/stats-web/` | Active M1 web consumer lives here. |
| Identity login, tokens, roles, and user administration | `modules/identity-access-module/` | Active M1 reusable module lives here. |
| Stats database schema and persistence adapters | `apps/stats-data/` | Future module will define schema, migrations, and query layer here. |
| Identity contracts | `contracts/identity/` | Future extraction of stable auth/token/user claims contracts. |
| Document/file contracts | `contracts/documents/` | Future file validation and ingestion handoff contracts. |
| Extraction contracts | `contracts/extraction/` | Future OCR, classification, and extraction contracts. |
| Transaction/data-quality contracts | `contracts/transactions/` | Future transaction and validation result contracts. |

## Migration Status

| Module/App | Status |
| --- | --- |
| M1 Identity Access Module | Migrated to `modules/identity-access-module/`. |
| M1 Stats Web consumer | Migrated to `apps/stats-web/`. |
| Stats Data and Persistence | Pending future module execution in `apps/stats-data/`. |
| File ingestion, validation, OCR, classification, extraction, and data validation | Pending future module specs under `modules/`. |

## Verification Expectations

Every migration pass should provide:

- Updated module spec or module-plan entry.
- File inventory showing created, moved, split, retired, and active files.
- Config sample proving runtime values do not require source edits.
- Module-local tests and regression evidence for any prior module affected by the move.
- Git commits separated by spec/design, implementation, evidence, and reusable skill/tooling where practical.

<!-- M0 Foundation End -->
