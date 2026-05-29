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

<!-- M0 Foundation Start -->
<!-- Applies the project runtime configuration rule to reusable modules. -->
Each reusable module must expose its runtime configuration through config files or supported environment/secret providers so URLs, ports, data targets, secrets, limits, paths, and environment switches do not require source-code edits.
<!-- M0 Foundation End -->
