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
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/qodo-review.md` | Qodo review record for PR #6. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/copilot-review.md` | Copilot review record for PR #6. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/claude-review.md` | Claude review record for PR #6. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/review-triage.md` | Consolidated review triage and next hardening plan. |
| `tests/integration/test_architecture_hardening_contract.py` | Automated contract checks for central registries, module config key registration, retired architecture wording, review artifacts, registry consistency, and logging redaction/container rules. |
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

## Post-Review Updates

These changes were added after Qodo, Copilot, and Claude reviewed PR #6. They address the low-risk merge-readiness items from `reviews/review-triage.md`.

| File | Review-driven update |
| --- | --- |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/qodo-review.md` | Added the Qodo review record. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/copilot-review.md` | Added the Copilot review record. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/claude-review.md` | Added the Claude review record. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/reviews/review-triage.md` | Added consolidated triage, merge-readiness decisions, and the next hardening-pass plan. |
| `config/stats.logging.json` | Added `stderr` to `LOG_DESTINATION.allowedValues` to match the stdout/stderr container logging rule. |
| `config/stats.runtime.json` | Added logging authority note, converted `modulePorts` to metadata objects, added `STATS_WEB_HOST_PORT`, and changed `DOCUMENT_REFERENCE_ROOTS` from prose default to `null` plus note. |
| `infrastructure/compose/stats-runtime.compose.yml` | Made Stats Web and M7/M8 port values environment-overridable and updated the Compose health check to use the configured Stats Web port. |
| `infrastructure/containers/stats/Dockerfile` | Added a container `HEALTHCHECK` against Stats Web `/health`. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Blanks M7/M8 browser downstream URLs so browser calls use the Stats Web same-origin proxy while server-side proxy targets remain internal. |
| `infrastructure/containers/stats/.env.container.example` | Added `STATS_WEB_HOST_PORT` and clarified host/container port behavior. |
| `apps/stats-web/appsettings.json` | Changed M7/M8 browser downstream defaults to blank values so Upload uses the same-origin proxy instead of direct `127.0.0.1:8016/8017` browser calls. |
| `modules/identity-access-module/config/defaults.env` | Narrowed default CORS origins from `*` to local Stats Web origins. |
| `docs/M1-user-management-access-control-spec.md` | Updated the M1 CORS default to match the narrowed module default. |
| `docs/M13-containerization-module-spec.md` | Clarified `STATS_WEB_PORT` versus `STATS_WEB_HOST_PORT` and documented same-origin browser proxy expectations. |
| `tests/integration/test_architecture_hardening_contract.py` | Added checks for review artifacts, registry metadata consistency, logging authority, and stdout/stderr destination consistency. |
| `tests/integration/test_m13_containerization_contract.py` | Added checks for Compose port interpolation, Dockerfile `HEALTHCHECK`, M7/M8 same-origin downstream blanking, and module-unit cleanup behavior. |
| `tests/integration/test_stats_web_orchestration_config.py` | Updated expectations so Stats Web official runtime disables local orchestration and keeps M7/M8 browser downstream calls same-origin. |
| `tests/scripts/regression/run_module_unit_tests.ps1` | Added default Compose cleanup with an explicit `-LeaveStackRunning` opt-out. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/validation-plan.md` | Updated the hardening contract description to include review artifacts and registry consistency. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/validation-results.md` | Updated validation results after review fixes: hardening contract `6 passed`, M13 contract `55 passed`, Stats Web orchestration config `3 passed`, Stats Web build passed, and Compose config validation passed. |
| `docs/architecture-hardening/passes/2026-05-30-architecture-config-logging/file-inventory.md` | Added this post-review update section. |

## Retired/Moved Files

| File | Change |
| --- | --- |
| `docs/stats-architecture-baseline.md` | Replaced by `docs/architecture-hardening/current-baseline.md`. |

## Notes

- The optimized web-flow evidence originally found a real Stats Web configuration gap: Upload reached validation, ingestion, and parsing, then browser-side transaction extraction failed because the page used direct container-internal M7/M8 URLs instead of the Stats Web same-origin proxy.
- The review-fix pass addressed that configuration gap by blanking M7/M8 browser downstream defaults and extending static tests. A fresh browser evidence run is recommended before PR #6 leaves draft if full E2E proof is required.
- `infrastructure/compose/.env.container` is local-only runtime configuration and must remain uncommitted even though the inventory identifies it as the local override surface.
