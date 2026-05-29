# Architecture Hardening File Inventory

## Pass

| Field | Value |
| --- | --- |
| Date | 2026-05-30 |
| Pass name | Architecture, configuration, logging, and spec sanity hardening |
| Branch target | `architecture-hardening-baseline` |
| Purpose | Clean the active architecture baseline before later MVP modules continue. |

## Created Files

| File | Purpose |
| --- | --- |
| `config/stats.runtime.json` | Central runtime configuration registry for paths, URLs, ports, database settings, secrets, storage providers, OCR settings, service endpoints, test fixtures, and cloud-ready settings. |
| `config/stats.paths.json` | Central logical path map resolved from `STATS_APP_ROOT`. |
| `config/stats.logging.json` | Central logging contract for log level, format, redaction, correlation/request context, and stdout/stderr collection. |
| `docs/architecture-hardening/README.md` | Explains the repeatable architecture hardening area and future pass structure. |
| `docs/architecture-hardening/current-baseline.md` | Latest accepted Stats architecture baseline. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/architecture-baseline.md` | Dated snapshot/summary of the baseline established by this pass. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/file-inventory.md` | This inventory. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/validation-plan.md` | Validation plan for the hardening pass. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/validation-results.md` | Validation results for the hardening pass. |
| `tests/integration/test_architecture_hardening_contract.py` | Automated contract checks for central registries, module config key registration, retired architecture wording, and logging redaction/container rules. |
| `tests/scripts/regression/capture_web_app_flow_evidence_optimized_2026_05_30.py` | Optimized web-flow evidence runner that avoids duplicating the full backend regression. |

## Modified Files

| File | Purpose |
| --- | --- |
| `README.md` | Points foundation readers to the architecture hardening baseline and central runtime/logging registries. |
| `docs/M0-foundation-module-spec.md` | Adds active architecture, central configuration, logging, and spec-first hardening rules. |
| `docs/building-block-module-plan.md` | Adds central runtime/logging governance and module logging expectations. |
| `docs/specs/module-spec-template.md` | Adds runtime registry and logging policy fields to future module specs. |
| `docs/M1-user-management-access-control-spec.md` | Removes ambiguous transitional wording from active guidance and keeps M1 aligned to active module paths. |
| `docs/M2-stats-web-shell-spec.md` | Clarifies diagnostic-only local orchestration and Docker-first official evidence. |
| `docs/M13-containerization-module-spec.md` | Adds runtime/logging config variables and container logging expectations. |
| `infrastructure/containers/stats/Dockerfile` | Copies central `config/` into the image and defines runtime/logging config environment variables. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Resolves runtime paths and logging config through environment variables. |
| `infrastructure/containers/stats/.env.container.example` | Documents runtime root, path config, logging config, and logging environment variables. |
| `infrastructure/compose/stats-runtime.compose.yml` | Passes central runtime/logging variables into `stats-runtime`. |
| `infrastructure/compose/.env.container` | Local container env values for runtime/logging config. |
| `tests/scripts/config/test-script-settings.json` | Links test helper settings to the central runtime/path registries. |
| `tests/scripts/common/test_config.py` | Loads central runtime/path registries when test helpers resolve settings. |
| `tests/scripts/regression/run_module_unit_tests.ps1` | Uses configurable container root paths for container-first module tests. |
| `tests/scripts/M13-Containerization/capture_m13_m1_m7_screenshot_evidence_2026_05_28.py` | Uses `STATS_APP_ROOT` and `STATS_EDGE_EXECUTABLE` overrides for screenshot evidence. |
| `tests/scripts/regression/run_docker_full_regression_evidence.ps1` | Updates setup guidance to use `STATS_APP_ROOT`. |

## Retired/Moved Files

| File | Change |
| --- | --- |
| `docs/stats-architecture-baseline.md` | Replaced by `docs/architecture-hardening/current-baseline.md`. |

## Notes

- The optimized web-flow evidence found a real Stats Web configuration gap: Upload reaches validation, ingestion, and parsing, then browser-side transaction extraction fails because the page uses direct container-internal M7/M8 URLs instead of the Stats Web same-origin proxy.
- That gap is documented in `tests/results/WebAppFlowOptimized/2026-05-30/`.
