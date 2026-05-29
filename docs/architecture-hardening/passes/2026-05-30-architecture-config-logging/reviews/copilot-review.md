# Copilot Review - PR #6 Architecture Hardening Baseline

Review source: GitHub Copilot CLI/session review
Review date: 2026-05-30
Pull request: https://github.com/DodIlagan-cloud/000_Capstone/pull/6

## High Severity

### Central config is not consumed by runtime code

- `apps/stats-web/Program.cs` does not appear to consume `config/stats.runtime.json` or `config/stats.paths.json`.
- Action: Load `STATS_RUNTIME_CONFIG` and `STATS_PATHS_CONFIG` at startup and resolve app/module paths and module ports from the central registry instead of `ContentRootPath` or literals.

### Path and working-directory hardcodes remain

- `appsettings.json` uses `LocalOrchestration.Services.WorkingDirectory` values such as `../../modules/...`.
- `Program.cs` `ResolvePath` uses `ContentRootPath`.
- Action: Replace relative paths with resolved values from the central path map, using `STATS_APP_ROOT` plus `stats.paths.json`. Validate `Path.IsPathRooted` and fail fast if a required path is missing.

### Missing or insufficient tests for new runtime behavior

- Runtime behavior needs tests for the orchestrator, proxy resolution, and path resolution.
- Action: Add unit tests for `ResolveProxyBaseUrl`, `StatsLocalServiceOrchestrator`, `IsLocalRuntime` gating, `StartService` logic, and `ResolvePath`. Add integration/container regression scripts and a CI step to run them.

### Container and local orchestration are duplicated

- `start-stats-runtime.sh` starts module processes inside the container.
- `Program.cs` also contains a hosted local service orchestrator.
- Action: Choose one orchestration model per runtime. Prefer the container entrypoint for container deployments and disable the in-container `.NET` orchestrator by default using an explicit development-only flag. Document the boundary.

## Medium Severity

### Hardcoded proxy/base URL defaults remain

- `Program.cs` contains hardcoded defaults such as `http://localhost:8013`.
- `appsettings.json` contains `127.0.0.1:8013` values.
- Action: Read proxy targets from central runtime config or environment variables, such as `STATS_*` values or `stats.runtime.json` module ports. Remove hardcoded fallbacks or mark them as explicit development-only defaults.

### Inconsistent health timeout defaults

- `appsettings.json` has `LocalOrchestration.HealthCheckTimeoutSeconds=2`.
- `stats.runtime.json` has `network.HEALTH_TIMEOUT=60`.
- Action: Align defaults to central runtime config and use one environment variable naming convention, such as `HEALTH_TIMEOUT` or `STATS_HEALTH_TIMEOUT`, across code and scripts.

### Logging is not wired to the central logging registry

- `config/stats.logging.json` is not enforced by application runtime.
- Correlation ID and redaction behavior are not implemented.
- Action: Add centralized logging configuration at startup, consume `LOG_LEVEL` and `LOG_FORMAT`, add correlation-id middleware, and implement redaction rules per registry.

### Orchestrator assumes commands and tools exist

- The orchestrator assumes `python` and `uvicorn` are available.
- External processes are started without robust error handling.
- Action: Validate executables before starting services, wrap `Process.Start` in `try/catch`, fail gracefully with clear logs, and document development versus container expectations.

### Proxy health and header handling need hardening

- `Program.cs` health checks use `StatusCode == OK`.
- Header copying may leak hop-by-hop or sensitive headers.
- Action: Use `IsSuccessStatusCode` for health checks. Copy only safe response headers and explicitly remove or normalize sensitive headers such as `Set-Cookie` and `Authorization` where appropriate.

## Medium-Low / Low Severity

### StartService exception handling and logging need cleanup

- `StartService` does not catch exceptions from `Process.Start`.
- It may log environment values.
- Action: Catch exceptions, log sanitized errors, avoid logging raw environment values, and apply redaction rules.

### ResolvePath fallback should prefer STATS_APP_ROOT

- `ResolvePath` falls back to `ContentRootPath`.
- Action: Prefer `STATS_APP_ROOT` when set and use `ContentRootPath` only as a development fallback.

### Startup script launch arguments are duplicated

- `start-stats-runtime.sh` sets empty downstream URLs and then proxy overrides.
- Action: Simplify launch arguments by injecting desired proxy/downstream endpoints from central config or environment variables instead of manual empty overrides.

## Specs Versus Implementation Mismatches

### stats.runtime.json declares central path and module port settings but runtime code does not consume them

- Action: Implement a loader for `stats.runtime.json` at startup and ensure module ports, paths, and logging defaults are sourced from it.

### stats.logging.json prescribes required fields and stdout logging but Program.cs does not enforce structured stdout logging

- Action: Configure application logging to output structured JSON to stdout and include required fields such as service/module, timestamp, level, message, and correlation ID.

## Summary

This review overlaps with the Qodo findings but focuses more heavily on the `.NET` Stats Web runtime and local orchestration layer. The main concern is that the architecture baseline is well documented, but the actual runtime still needs loaders, tests, and behavior changes before centralized configuration and logging are fully operational.
