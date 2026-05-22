# Stats Capstone

<!-- M0 Foundation: repository entry point for the building-block architecture. -->

Stats is a capstone product assembled from reusable building-block modules and an encompassing Stats web application.

## Architecture Start

Use these foundation documents before starting a module:

- `docs/M0-foundation-module-spec.md`
- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/specs/module-spec-template.md`

The building-block plan is the architecture boundary. Each later module should refine its own spec, contracts, tests, evidence, configuration sample, and runtime path before implementation grows.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `apps/` | Stats-specific encompassing applications such as Stats Web. |
| `modules/` | Standalone reusable backend building blocks. |
| `contracts/` | Explicit shared handoff contracts between modules and apps. |
| `infrastructure/` | Compose, containers, cloud, and deployment work. |
| `docs/` | Foundation specs, module plans, specs, evidence guidance, and project notes. |
| `samples/` | Safe sample data and fixtures. |
| `tests/integration/` | Cross-module Stats workflow checks. |

## Transitional Code

Earlier implementation work currently remains under `stats/`:

- `stats/stats.Web/`
- `stats/stats-ingestion-service/`

Those folders are not the final architecture boundary. Later module specs should decide the migration path for their owned behavior into `apps/` or `modules/` without mixing Stats UI logic into reusable services.
