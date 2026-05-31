# Copilot Re-review - PR #6 Architecture Hardening Baseline

Review source: GitHub Copilot second-pass review
Review date: 2026-05-30
Pull request: https://github.com/DodIlagan-cloud/000_Capstone/pull/6
Reviewed commit: `de5456e Address architecture hardening review findings`

## High

### Central runtime/config not consumed at startup

- Action: Load `STATS_RUNTIME_CONFIG` and `STATS_PATHS_CONFIG` at app startup and source `modulePorts`, path map, and storage roots from it. Replace string literals in `Program.cs` and start scripts with resolved values.

### Runtime spec/prose left in DOCUMENT_REFERENCE_ROOTS

- Action: Replace prose default with a machine-friendly list or empty array; validate at startup and fail fast if missing.

### Duplicate orchestration

- Container entrypoint and in-process orchestrator both exist.
- Action: Pick one model. Prefer container entrypoint for container deployments; disable `StatsLocalServiceOrchestrator` by default and make it opt-in via explicit development environment variable.

### Browser same-origin proxy not enforced

- `appsettings.json` points to `127.0.0.1`; frontend may call other services.
- Action: Remove direct browser-facing `BaseUrl` defaults; set `StatsApi:BaseUrl` to empty or same-origin in committed safe defaults and ensure frontend uses relative `/api/v1/*` endpoints.

### Missing tests and CI gating for new behaviors

- Action: Add unit tests for `ResolveProxyBaseUrl`, proxy header handling, `StatsLocalServiceOrchestrator` (`IsLocalRuntime`, `StartService`, `ResolvePath`), and an integration/container-regression test. Add CI job to run them.

## Medium

### Logging registry not enforced

- No structured JSON, redaction, or correlation ID is wired to the app runtime.
- Action: Wire Serilog/Microsoft logging to respect `LOG_*` environment variables, output structured JSON to stdout, include required fields, add correlation-id middleware, and add a redaction hook.

### Path resolution and STATS_APP_ROOT usage inconsistent

- Action: Prefer `STATS_APP_ROOT` over `ContentRootPath`, resolve relative module paths via central path map, and validate resolved directories early.

### Health-timeout and environment-variable mismatches

- Action: Align health timeout names and values, such as `HEALTH_TIMEOUT` versus `StatsWeb:LocalOrchestration:HealthCheckTimeoutSeconds`; choose one source and use it across start script and code.

### Proxy header and health-check handling

- Action: Use `IsSuccessStatusCode` for health checks; restrict forwarded headers and drop sensitive/hop-by-hop headers.

### Hardcoded defaults still in code

- Ports and base URLs remain in code/config.
- Action: Remove development-only `127.0.0.1` fallbacks from committed config; use environment-overridable defaults via `stats.runtime.json`, `modulePorts`, and Docker Compose.

## Low

### Process start error handling and sanitized logging

- Action: Catch `Process.Start` exceptions, log sanitized messages, and add lifecycle/PID tracking for started processes in `start-stats-runtime.sh`.

### Dockerfile/image copies include tests/docs

- Action: Consider excluding `tests/input` or ensure no private fixtures are committed. Document intended image contents.

## Merge-Readiness Checklist

### Compose port values are environment-overridable

- Status: Addressed.
- Action: None, but ensure docs explain how to override.

### M7/M8 browser calls use the Stats Web same-origin proxy

- Status: Partially addressed.
- Evidence: `Program.cs` implements same-origin proxy; `appsettings.json` still contains `127.0.0.1` base URLs and startup overrides in start script pass empty strings.
- Action: Enforce same-origin by removing committed external `BaseUrl` defaults and ensuring frontend uses relative endpoints.

### Logging destination mismatch is fixed

- Status: Not fully addressed.
- Evidence: `LOG_DESTINATION` is set in Compose, but app does not configure structured JSON, correlation ID, or redaction per config.
- Action: Wire central logging registry into startup.

### modulePorts registry shape is consistent

- Status: Partially addressed.
- Evidence cited by review: `modulePorts` exist in `stats.runtime.json` as strings; code and Compose use numeric ports.
- Action: Normalize types and read ports from runtime registry at startup.

### DOCUMENT_REFERENCE_ROOTS no longer has prose as a default

- Status: Not addressed according to review.
- Action: Replace with structured default or empty list; validate.

### CORS default is narrowed

- Status: Not addressed according to review.
- Evidence cited by review: no CORS policy configured in `Program.cs`; runtime config mentions `CORS_ALLOWED_ORIGINS` but not enforced.
- Action: Implement CORS policy using `CORS_ALLOWED_ORIGINS` with safe default and document development override.

### Docker health check exists

- Status: Addressed.
- Action: None, but ensure health endpoints used by checks are stable.

### Review artifacts and validation results are documented

- Status: Partially addressed.
- Action: Add CI test result artifacts and docs linking to recent validation output.

## Blocking Items Before Moving Out Of Draft

1. Central config consumption.
2. `DOCUMENT_REFERENCE_ROOTS` prose default.
3. Enforce same-origin proxy / remove browser direct endpoints.
4. Logging wiring to registry.
5. Add tests and CI for orchestrator/proxy/integration.

## Copilot Suggested Focused PR

- Implement runtime config loader and use it for ports, paths, and logging.
- Remove prose/defaults and validate path map.
- Add unit tests for proxy and orchestrator.
- Wire Serilog JSON stdout and correlation ID.
- Disable in-process orchestrator by default.
