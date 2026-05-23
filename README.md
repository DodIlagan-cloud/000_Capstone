# Stats Capstone

<!-- M0 Foundation: repository entry point for the building-block architecture. -->

Stats is a capstone product assembled from reusable building-block modules plus encompassing Stats product applications for the web experience and project data.

## Architecture Start

Use these foundation documents before starting a module:

- `docs/M0-foundation-module-spec.md`
- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/specs/module-spec-template.md`

The building-block plan is the architecture boundary. Each later module should refine its own spec, contracts, tests, evidence, configuration sample, and runtime path before implementation grows.

<!-- M0 Foundation Start -->
<!-- Applies the project-wide runtime configuration rule to all Stats modules and apps. -->
## Runtime Configuration Rule

Runtime values for the whole Stats project must be stored in configuration files or supported environment/secret providers instead of being hardcoded in application code.

This applies to modules, Stats apps, infrastructure scripts, and transitional code. Examples include URLs, ports, hosts, database targets, credentials, secrets, token settings, browser origins, file paths that vary by environment, cloud resource names, and feature/runtime switches.

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

## Current Code Homes

The project now uses the architecture folders directly. M1 is active under:

- `modules/identity-access-module/`
- `apps/stats-web/`

New module work should use the owning `apps/`, `modules/`, `contracts/`, `infrastructure/`, `samples/`, or `tests/` path rather than recreating retired transitional folders.
