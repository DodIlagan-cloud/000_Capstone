# Stats Capstone

<!-- M0 Foundation: repository entry point for the building-block architecture. -->

Stats is a capstone product assembled from reusable building-block modules plus encompassing Stats product applications for the web experience and project data.

## Architecture Start

Use these foundation documents before starting a module:

- `docs/M0-foundation-module-spec.md`
- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/specs/module-spec-template.md`
- `docs/testing-build-loop-policy.md`
- `docs/privacy-security-data-governance-policy.md`
- `docs/architecture-hardening/current-baseline.md`

The building-block plan is the architecture boundary. Each later module should refine its own spec, contracts, tests, evidence, configuration sample, and runtime path before implementation grows.

Testing is part of the build loop. Each module change must identify and run the appropriate tests during implementation, with official acceptance evidence running through the M13 Stats container from M13 onward.

Privacy, security, and data governance are also part of the build loop. Financial documents, OCR text, extracted data, credentials, logs, screenshots, and evidence must be handled according to the project privacy and data-governance policy.

<!-- M0 Foundation Start -->
<!-- Applies the project-wide runtime configuration rule to all Stats modules and apps. -->
## Runtime Configuration Rule

Runtime values for the whole Stats project must be stored in configuration files or supported environment/secret providers instead of being hardcoded in application code.

This applies to modules, Stats apps, infrastructure scripts, admin tools, and deployment assets. Examples include URLs, ports, hosts, database targets, credentials, secrets, token settings, browser origins, file paths that vary by environment, cloud resource names, and feature/runtime switches.

Directory paths use a two-layer convention:

- `config/stats.paths.json` defines the logical project path map.
- `STATS_APP_ROOT` defines the physical runtime root for the current environment.

Local development may resolve from `C:\000_Capstone`; the Stats container resolves from `/app`; cloud deployment may resolve from an Azure App Service, Container Apps, mounted volume, or storage-backed location. Module code must not assume the physical root. It should resolve logical paths from the configured root or use a configured storage provider such as `STATS_STORAGE_PROVIDER=LocalFileSystem` now and `AzureBlobStorage` later.

The broader runtime configuration registry is `config/stats.runtime.json`. It names the expected environment variables, safe defaults, secret-bearing settings, service ports, downstream URLs, storage settings, OCR settings, database settings, and test fixture settings for the overall Stats application. Module specs should refer to that registry before adding new runtime values.

Logging is governed by `config/stats.logging.json`. Modules may implement logging locally, but log levels, format, redaction behavior, correlation/request context, and stdout/stderr collection must follow the central logging contract.

Committed config may provide safe local defaults and examples. Real secrets and developer-specific overrides must stay out of source control.
<!-- M0 Foundation End -->

## Repository Layout

| Path | Purpose |
| --- | --- |
| `apps/` | Stats-specific encompassing product applications such as Stats Web and Stats Data. |
| `modules/` | Standalone reusable backend building blocks. |
| `contracts/` | Explicit shared handoff contracts between modules and apps. |
| `infrastructure/` | Compose, containers, cloud, and deployment work. |
| `docs/` | Foundation specs, module plans, specs, evidence guidance, and project notes. |
| `samples/` | Safe sample data and fixtures. |
| `tests/integration/` | Cross-module Stats workflow checks. |

## Architecture Baseline

Active implementation belongs under the repository roots listed above. Retired or historical paths must not be used as current implementation guidance in module specs.
