# Modules

<!-- M0 Foundation: boundary for standalone reusable building blocks. -->

This folder is the target home for reusable backend modules.

Planned module lanes:

- `identity-access-module/`
- `file-validation-module/`
- `document-parsing-module/`
- `transaction-extraction-module/`
- `data-validation-module/`
- `email-ingestion-module/`

Each module should own a spec, README, tests, evidence, configuration sample, explicit contract, runtime instructions, and container wiring. From M13 onward, official module tests and evidence run through the Stats container.

Stats-specific persistence belongs in `apps/stats-data/`, not in a reusable processing module.

Current implemented module folders:

- `identity-access-module/`
- `file-validation-module/` for merged M3 validation and M4 ingestion behavior.
- `document-parsing-module/` for merged M5 parsing/OCR and retired M6 classification behavior.
- `transaction-extraction-module/` for M7 transaction and financial field candidate extraction.
- `data-validation-module/` for M8 transaction cleaning, validation, and duplicate detection.
- `email-ingestion-module/` for M12 automated email attachment intake into file ingestion. As of 2026-06-24 this is locally implemented / validation pending for cloud-hosted provider-neutral IMAP source profiles, Email Setup UI wiring, Azure SQL profile storage, encrypted secret handling, Blob-backed intake direction, password-protected PDF handling, and M3/M4 handoff validation.

<!-- M0 Foundation Start -->
<!-- Applies the project runtime configuration rule to reusable modules. -->
Each reusable module must expose its runtime configuration through config files or supported environment/secret providers so URLs, ports, data targets, secrets, limits, paths, and environment switches do not require source-code edits.
<!-- M0 Foundation End -->
