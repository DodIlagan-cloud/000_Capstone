# Qodo Review - PR #6 Architecture Hardening Baseline

Review source: Qodo IDE review
Review date: 2026-05-30
Pull request: https://github.com/DodIlagan-cloud/000_Capstone/pull/6

## Actionable Issues

## High Severity

### stats.paths.json is not actually consumed at runtime

- `start-stats-runtime.sh` defines module directories with hardcoded suffixes like `identity-access-module`, not by reading the central path map.
- This breaks the stated architecture baseline: "Resolve logical paths from `STATS_APP_ROOT` and `stats.paths.json`."

### Runtime logging contract is only declarative, not enforced

- `stats.logging.json` defines required fields and container logging rules, but no runtime validation or log-output test exists.
- The implementation does not appear to load or enforce `STATS_LOGGING_CONFIG` in any actual service runtime.

### docker compose config overrides .env.container values

- `stats-runtime.compose.yml` sets many environment keys explicitly in `environment:`, including `ALLOW_OCR_FALLBACK`, `OCR_ENGINE`, `STATS_APP_ROOT`, and `STATS_STORAGE_PROVIDER`.
- This undermines the intended centralized config flow from `.env.container` and means some runtime values are effectively hardcoded by compose.

### Background service startup is fragile

- `start-stats-runtime.sh` launches module APIs in the background and then `exec`s `dotnet`.
- If one of the background `uvicorn` processes crashes after the initial health check, the container may continue running without failing fast.

## Medium Severity

### STATS_LOGGING_CONFIG and STATS_PATHS_CONFIG are set but never used

- `start-stats-runtime.sh` exports these environment variables, but no runtime code appears to read the actual config files.
- This is a mismatch with the new central config docs and the architecture baseline.

### Compose file hardcodes internal container service ports

- `TRANSACTION_EXTRACTION_PORT` and `DATA_VALIDATION_PORT` are fixed in the compose environment block.
- The M13 spec says runtime values should be configurable via environment/config, so these should be overridable rather than hardcoded.

### Logging contract mismatch: stdout/stderr wording vs allowed values

- `stats.logging.json` says container logs should use stdout/stderr.
- `LOG_DESTINATION.allowedValues` only includes `stdout`.

### Container image packages non-runtime artifacts

- `Dockerfile` copies docs, tests, readme files, and `.gitignore` into `/app`.
- This is not aligned with the spec's portable runtime packaging goal and inflates the image unnecessarily.

### Specs/tests are too static for container-first claims

- `test_m13_containerization_contract.py` only inspects file contents and static defaults.
- There is no lightweight test that actually exercises `docker compose up` or verifies the containerized runtime behavior against `stats.logging.json` and `stats.paths.json`.

## Low Severity

### run_module_unit_tests.ps1 leaves containers running

- The script starts `docker compose up --build --detach` and never calls `docker compose down` on completion.
- This is a usability/cleanup gap for a container-first test runner.

### Active spec validation does not include architecture hardening docs

- `test_architecture_hardening_contract.py` focuses on module specs and not `current-baseline.md` or pass artifacts.
- Those are part of the hardened architecture surface and should be included in the spec hygiene check.

### Dockerfile and startup script use runtime defaults rather than a centralized path loader

- Even though `STATS_APP_ROOT` is central, the runtime still defines paths like `${STATS_APP_ROOT}/modules/transaction-extraction-module` manually.
- If the path layout changes, the single source of truth is not being honored end-to-end.

## Summary

The PR makes strong progress on architecture hardening, central config registry docs, and container-first evidence. The main gaps are:

- central config is documented but not fully wired into runtime execution;
- compose/runtime layers still hardcode environment and path values;
- logging governance is declared but not operationally validated.

Fixing those will make the implementation much more aligned with the M13 architecture baseline.
