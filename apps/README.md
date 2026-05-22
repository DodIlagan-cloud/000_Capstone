# Apps

<!-- M0 Foundation: boundary for encompassing Stats applications. -->

This folder is the target home for Stats-specific applications.

Planned lanes from the building-block module plan:

- `stats-web/` for the encompassing .NET user-facing app and orchestration shell.
- `stats-data/` for the Stats-specific database schema, migrations, persistence adapters, and query layer.
- `stats-admin-tools/` for Stats-only operational tools if they are needed.

Stats applications call module contracts. They should not absorb reusable identity, file validation, ingestion, OCR, classification, extraction, or data-quality internals.

<!-- M0 Foundation Start -->
<!-- Applies the project runtime configuration rule to Stats-specific applications. -->
Stats applications must keep environment-dependent runtime values in configuration files or supported environment/secret providers rather than hardcoding them in source.
<!-- M0 Foundation End -->
