# Apps

<!-- M0 Foundation: boundary for encompassing Stats applications. -->

This folder is the target home for Stats-specific applications.

Planned lanes from the building-block module plan:

- `stats-web/` for the encompassing .NET user-facing app and orchestration shell.
- `stats-admin-tools/` for Stats-only operational tools if they are needed.

Stats applications call module contracts. They should not absorb reusable identity, file validation, ingestion, OCR, classification, extraction, data-quality, or storage internals.
