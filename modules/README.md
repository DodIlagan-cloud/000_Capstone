# Modules

<!-- M0 Foundation: boundary for standalone reusable building blocks. -->

This folder is the target home for reusable backend modules.

Planned module lanes:

- `identity-access-module/`
- `file-validation-module/`
- `file-ingestion-module/`
- `ocr-extraction-module/`
- `document-classification-module/`
- `transaction-extraction-module/`
- `data-validation-module/`
- `email-ingestion-module/`

Each module should own a spec, README, tests, evidence, configuration sample, explicit contract, local run instructions, and a container path when containerization is reached.

Stats-specific persistence belongs in `apps/stats-data/`, not in a reusable processing module.

<!-- M0 Foundation Start -->
<!-- Applies the project runtime configuration rule to reusable modules. -->
Each reusable module must expose its runtime configuration through config files or supported environment/secret providers so URLs, ports, data targets, secrets, limits, paths, and environment switches do not require source-code edits.
<!-- M0 Foundation End -->
