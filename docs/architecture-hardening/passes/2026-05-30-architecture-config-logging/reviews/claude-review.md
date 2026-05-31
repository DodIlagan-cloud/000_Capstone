# PR #6 — Architecture Hardening Baseline: Code Review

**Reviewer:** Claude (Anthropic)
**Date:** 2026-05-30
**Branch:** `architecture-hardening-baseline`

---

## Overview

This PR establishes three central config registries (`stats.runtime.json`, `stats.paths.json`, `stats.logging.json`), wires `STATS_APP_ROOT`-based path resolution into the container startup script, adds M8 Data Validation to the container and regression coverage, disables Stats Web local orchestration, and hardens module specs to remove transitional/historical wording. Validation results show all automated checks passing (4+53+63 tests).

---

## 1. Additional Actionable Issues Found

**A — Compose file: port variables are inconsistently hardcoded**

In `stats-runtime.compose.yml`, the new runtime/logging vars correctly use `${VAR:-default}` interpolation, but the port variables don't:

```yaml
STATS_WEB_PORT: "8080"               # hardcoded literal
TRANSACTION_EXTRACTION_PORT: "8016"  # hardcoded literal
DATA_VALIDATION_PORT: "8017"         # hardcoded literal
```

The central registry (`stats.runtime.json`) registers `STATS_WEB_PORT`, `TRANSACTION_EXTRACTION_PORT`, etc. as env-configurable, but the compose file bypasses that by writing literals. If someone needs to override a port via `.env.container`, it won't take effect. These should use `${STATS_WEB_PORT:-8080}`, `${TRANSACTION_EXTRACTION_PORT:-8016}`, `${DATA_VALIDATION_PORT:-8017}`.

**B — Dockerfile image bloat from docs/meta-file copies**

The Dockerfile copies files that have no runtime purpose:

```dockerfile
COPY docs/ /app/docs/
COPY README.md /app/README.md
COPY .gitignore /app/.gitignore
COPY infrastructure/containers/stats/Dockerfile /app/infrastructure/containers/stats/Dockerfile
COPY infrastructure/containers/stats/start-stats-runtime.sh /app/infrastructure/containers/stats/start-stats-runtime.sh
COPY infrastructure/compose/stats-runtime.compose.yml /app/infrastructure/compose/stats-runtime.compose.yml
COPY apps/stats-web/Program.cs /app/apps/stats-web/Program.cs
COPY apps/stats-web/appsettings.json /app/apps/stats-web/appsettings.json
COPY apps/README.md ... COPY modules/README.md ... (etc.)
```

This is driven by the in-container contract tests reading the repo tree. The consequence is a production image carrying the entire `docs/` tree, source files, and infrastructure files that serve no runtime purpose. It meaningfully inflates the image and surfaces repo internals in a deployed artifact.

**C — No `HEALTHCHECK` instruction in Dockerfile**

The container exposes a `/health` endpoint on Stats Web (port 8080) but the Dockerfile has no `HEALTHCHECK` directive. For Docker Compose and cloud targets (Azure Container Apps, ACI, AKS), a container-level health check is how the orchestrator knows whether to restart or route traffic. `start-stats-runtime.sh` handles startup sequencing, but the runtime orchestrator has no post-start signal.

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -sf http://localhost:8080/health || exit 1
```

**D — Startup script: background process failures are silent until health timeout**

In `start-stats-runtime.sh`, all five uvicorn processes are started in the background before any health checks. If uvicorn crashes immediately (missing dependency, import error, config error), the script won't know until `wait_for_health` times out 60 seconds later, with no diagnostic about which process failed or why. There is also no `set -o pipefail`, so pipeline failures are silently swallowed.

A minimal improvement: after launching each background process, capture its PID and add a brief check that it is still alive before moving to the next service.

**E — Graceful shutdown gap: `exec dotnet` orphans uvicorn processes**

`start-stats-runtime.sh` ends with `exec dotnet stats.Web.dll ...`, which replaces the shell process with dotnet. The five uvicorn processes started in the background become orphans without a process supervisor. When Docker sends SIGTERM to stop the container, it goes only to PID 1 (dotnet/Stats Web). The uvicorn processes receive nothing and run until Docker's stop timeout triggers SIGKILL. This means:

- No graceful shutdown for the Python APIs (in-flight requests are dropped)
- Zombie process accumulation if any uvicorn worker exits during the session (nothing reaps them)

For a single-container MVP this is acceptable, but it is a cloud-readiness gap. It should be documented in the M13 spec Known Limitations, and the `docker stop` timeout in Compose should be set explicitly (e.g., `stop_grace_period: 30s`).

**F — Known browser-side M7/M8 proxy gap is unresolved**

The validation results document this explicitly:

> "Stats Web Upload page uses direct browser URLs for M7/M8 (`127.0.0.1:8016` and `127.0.0.1:8017`) instead of the same-origin Stats Web proxy."

The startup script correctly passes `--StatsWeb:Proxy:TransactionExtractionBaseUrl` and `--StatsWeb:Proxy:DataValidationBaseUrl`, and the M13 contract tests verify those proxy routes exist in `Program.cs`. But the browser-side JavaScript in the Upload page still constructs calls to `127.0.0.1:8016`/`8017` directly, which fail from a browser context when the container is running. The end-to-end upload flow is broken past M5 from the UI.

**G — `stats.runtime.json` schema inconsistency in `modulePorts` section**

All other sections in `stats.runtime.json` use the `{purpose, default, secret}` object pattern. The `modulePorts` section uses flat string values:

```json
"modulePorts": {
  "IDENTITY_PORT": "8013",
  "FILE_VALIDATION_PORT": "8014",
  ...
}
```

This is inconsistent and would be confusing for any tooling or future module that reads the registry expecting the documented schema. It should use the same metadata structure as the other entries.

**H — `DOCUMENT_REFERENCE_ROOTS` default is freeform prose, not a usable value**

```json
"DOCUMENT_REFERENCE_ROOTS": {
  "default": "modules/file-validation-module data/intake equivalent or configured Stats storage root"
}
```

A module config loader reading this as a path would get a broken value. This should either be an explicit path, a list, or explicitly marked `"default": null` with a `"note"` field explaining the lookup behavior.

**I — `cors_allowed_origins` default is `*`**

The M1 spec config table (and identity module defaults) still shows `cors_allowed_origins` defaulting to `*`. Since this PR is establishing the hardened production-readiness baseline, locking down the default to `http://localhost:8080` in the container context is appropriate. Open CORS is a known risk for financial document handling.

**J — Optimized evidence script mutates imported module globals**

`capture_web_app_flow_evidence_optimized_2026_05_30.py` uses `importlib.util.spec_from_file_location` to load `capture_m13_m1_m7_screenshot_evidence_2026_05_28.py`, then mutates globals post-exec (`module.DATE = DATE`, `module.EVIDENCE = EVIDENCE`). This is fragile:

- The source script is referenced by a hardcoded dated filename; any rename breaks the runner
- If constants are captured at module import time rather than referenced at call time, the mutations won't propagate
- `load_capture_module()` raises `RuntimeError` if the source file is missing, with no useful guidance

**K — `LOG_LEVEL` and logging vars duplicated between `stats.runtime.json` and `stats.logging.json`**

Both files define `LOG_LEVEL`, `LOG_FORMAT`, `LOG_REDACT_SENSITIVE_VALUES`, `LOG_INCLUDE_CORRELATION_ID`, and `LOG_DESTINATION`. The runtime JSON references the logging JSON as the authority (`"loggingRegistry": "config/stats.logging.json"`), but also repeats the entries. If they diverge, which one wins? This needs a clear "source of truth" note or the duplicates should be removed from `stats.runtime.json`.

---

## 2. Findings That Must Be Fixed Before Merge

**Must fix:**

| # | Issue | Why it blocks |
|---|---|---|
| F | Browser-side Upload page calls M7/M8 directly at `127.0.0.1:8016/8017`, bypassing the proxy | The PR claims to establish a production-ready baseline, but the core upload flow is documented as broken. If accepted as a known gap, it must be tracked as a filed issue with a target module, not just a note in validation-results. |
| A | Compose port vars are hardcoded literals, not `${VAR:-default}` | Contradicts the central config goal directly: changing a port in `.env.container` won't affect compose. |

**Should fix before merge if "production-readiness" is a stated goal:**

| # | Issue | Why |
|---|---|---|
| C | No Dockerfile `HEALTHCHECK` | Cloud and Compose orchestration cannot determine container readiness without it |
| I | `cors_allowed_origins` default is `*` | Security regression for financial data; the baseline should close this |
| G | `modulePorts` flat strings vs metadata objects | Breaks registry schema consistency that future tooling will rely on |

---

## 3. Findings That Can Be Documented Follow-Ups

| # | Issue | Suggested follow-up |
|---|---|---|
| B | Dockerfile copies docs/meta files for contract test support | Refactor: move to host-side the tests that verify file inventory; keep image lean |
| D | Background process failures silent until health timeout | Add PID liveness spot-check after each launch; file as M13 improvement |
| E | `exec dotnet` orphans uvicorn; no graceful shutdown | Document in M13 Known Limitations; add `stop_grace_period` to Compose |
| H | `DOCUMENT_REFERENCE_ROOTS` default is prose | Fix in same PR or immediately after |
| J | Evidence script depends on dated source filename via importlib mutation | Refactor into shared helpers module instead of dynamic import |
| K | Logging vars duplicated in two registries | Add a comment that `stats.runtime.json` logging entries are cross-references to `stats.logging.json` as authority, or remove duplicates |

---

## 4. Assessment of Known Review Themes

**Config not fully consumed at runtime** — Confirmed and unchanged by this PR. The registries are declarative contracts, not loaded at module startup. The PR is correct to establish the contract first. The follow-up is each module's `config_loader.py` asserting only registered keys are used and actually loading `LOG_LEVEL`/`LOG_FORMAT` from env. This PR does not pretend to do that; the spec language is honest about it.

**Hardcoded ports/paths in defaults** — Partially fixed. Startup script is now driven by env vars with hardcoded fallbacks (the correct pattern). Compose port literals are the remaining gap (Issue A above).

**Logging config declarative but not enforced** — Correct characterization; no change in this PR beyond establishing the contract. The contract test verifies the JSON schema; it does not verify modules emit JSON logs to stdout. Valid follow-up for each module's acceptance criteria.

**Compose/startup scripts duplicate config values** — Partially addressed. Startup script now reads from env vars. Compose still has hardcoded port literals (Issue A).

**Container startup may be fragile** — Confirmed (Issues D and E). Adequate for MVP; should be tracked.

**Stats Web local orchestration duplicates container orchestration** — Resolved by this PR. `LocalOrchestration:Enabled` and `StartMissingServices` are correctly set to `false`.

**Tests are mostly static contract tests** — Confirmed. All new tests are file-content and JSON-structure checks, not behavioral runtime tests. This is appropriate for a governance/baseline PR.

---

## 5. Summary Verdict

This PR is mergeable with two targeted fixes before merge: **(A)** fix compose port vars to use `${VAR:-default}` interpolation, and **(F)** either fix the browser-side M7/M8 proxy URLs in the Upload page JavaScript or explicitly file a blocking issue and note in the M2 spec that the upload flow is partially broken until that fix lands.

Everything else is either already acknowledged, a follow-up scope item, or a moderate hardening item that does not undermine the declared baseline goals.

The architecture is sound — central registries, path resolution from `STATS_APP_ROOT`, container-first evidence, spec-first governance — and the contract tests provide a solid regression fence for the declared rules.

---

## Re-Review — Post-Triage Update (2026-05-30, commit de5456e)

### Checklist Verification

All eight merge-readiness items from the original review are addressed:

| Item | Status | Notes |
|---|---|---|
| Compose port values are environment-overridable | ✅ Fixed | All ports use `${VAR:-default}`; host/container ports split into `STATS_WEB_HOST_PORT`/`STATS_WEB_PORT` |
| M7/M8 browser calls use same-origin proxy | ✅ Fixed | Full chain: `Upload.cshtml.cs` → `Upload.cshtml` data attrs → `upload.js` dataset → blank downstream defaults → `Program.cs` proxy routes |
| Logging destination mismatch | ✅ Fixed | `stats.logging.json` now allows `["stdout", "stderr"]`; `stats.runtime.json` logging section designates `stats.logging.json` as authority |
| modulePorts registry shape consistent | ✅ Fixed | All five ports use `{purpose, default, secret}` metadata objects; enforced by new contract test |
| DOCUMENT_REFERENCE_ROOTS default | ✅ Fixed | `"default": null` with `"note"` field; no longer parseable as a path |
| CORS default narrowed | ✅ Fixed | `CORS_ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080` in M1 defaults.env |
| Docker HEALTHCHECK | ✅ Added | 90s start-period, 30s interval, shell-form variable expansion for `STATS_WEB_PORT` |
| Review artifacts and validation results | ✅ Documented | All three review files, triage, updated validation results, new passing counts (6/55/3) |

### Remaining Before Leaving Draft

One open question: the existing browser evidence (`WebAppFlowOptimized/2026-05-30/`) captured the broken M7/M8 flow. `validation-results.md` explicitly notes a fresh browser E2E run should be captured before the PR leaves draft if full E2E proof is required. Contract tests and Stats Web build pass; the decision is whether browser screenshots of the full M5→M7→M8 flow are required by the project's evidence policy.

Minor: `ALLOW_OCR_FALLBACK` comment in compose still says "OCR is always enabled inside this container" but the value is now overridable via env. Consider updating the comment.

All other previously flagged items (runtime config loader, logging enforcement, process supervision, graceful shutdown, image bloat) are correctly tracked as the next hardening pass in `review-triage.md`.
