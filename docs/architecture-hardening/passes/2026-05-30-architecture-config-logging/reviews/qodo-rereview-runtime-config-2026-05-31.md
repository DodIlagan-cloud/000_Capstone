# Qodo Re-review - Stats Web Runtime Config And Logging

Review source: Qodo AI Code Review
Review date: 2026-05-31
Pull request: https://github.com/DodIlagan-cloud/000_Capstone/pull/6
Reviewed scope: Stats Web runtime config/logging implementation after commit `1d65588`

## Qodo Summary

Qodo verified that commit `1d65588` significantly enhanced PR #6 by adding Stats Web runtime config and logging consumption. It also verified that all eight original merge-readiness items remain addressed.

Qodo identified one critical data-quality issue, two reliability issues, and one observability issue.

## Findings

### Critical: CORS_ALLOWED_ORIGINS default missing comma

Qodo reported that `config/stats.runtime.json` contained:

```text
http://localhost:8080http://127.0.0.1:8080
```

and recommended changing it to:

```text
http://localhost:8080,http://127.0.0.1:8080
```

Local verification after review showed the committed branch already has the comma-separated value. This finding is treated as stale/false positive for the current branch state, but an automated test was added so the value cannot regress.

### Medium: StatsCentralRuntime.Load should report malformed JSON clearly

Qodo found that `JsonDocument.Parse(...)` was called directly for the runtime, paths, and logging config files. A malformed JSON file would fail startup with a less helpful exception.

Resolution: wrap config parsing in a helper that throws a descriptive `InvalidOperationException` identifying the central config file path and config type.

### Medium: Empty CORS origin list silently registers an empty policy

Qodo found that an empty `CorsAllowedOrigins` list registered a CORS policy that allowed nothing, which could fail silently.

Resolution: only register and apply the named CORS policy when `CorsAllowedOrigins` contains at least one explicit origin. Wildcard values are still filtered out.

### Low: No startup visibility for central config loading

Qodo found that Stats Web loaded central config files before normal logging was configured and did not report which files were loaded.

Resolution: `StatsCentralRuntime.Load` now emits a startup line with the resolved app root, central config file paths, module port count, and CORS origin count.

## Verified Merge-Readiness Items

Qodo confirmed the eight original merge-readiness items remain addressed:

- Compose port values are environment-overridable.
- M7/M8 browser calls use the same-origin proxy.
- Logging destination mismatch is fixed and Stats Web logging is wired.
- `modulePorts` shape is consistent and consumed by Stats Web.
- `DOCUMENT_REFERENCE_ROOTS` no longer uses prose as default.
- CORS default is narrowed and consumed by Stats Web.
- Docker `HEALTHCHECK` exists.
- Review artifacts and validation results are documented.
