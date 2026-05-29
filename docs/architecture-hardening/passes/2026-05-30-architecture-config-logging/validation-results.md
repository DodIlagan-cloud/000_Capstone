# Validation Results

## Date

2026-05-30

## Results

| Check | Result | Notes |
| --- | --- | --- |
| Registry JSON parse | Passed | `config/stats.runtime.json`, `config/stats.paths.json`, and `config/stats.logging.json` parsed successfully. |
| Architecture hardening contract | Passed | `6 passed`. Pytest cache warnings were local permission warnings only. |
| M13 container contract | Passed | `55 passed`. Pytest cache warning was local permission-only. |
| Stats Web orchestration config | Passed | `3 passed`. Confirms local orchestration is disabled by default and M7/M8 browser downstream values use same-origin proxy behavior. |
| Stats Web build | Passed | `dotnet build apps\stats-web\stats.Web.csproj` completed with `0 Warning(s)` and `0 Error(s)`. |
| Docker Compose config validation | Passed | `docker compose --file infrastructure\compose\stats-runtime.compose.yml --env-file infrastructure\compose\.env.container config` rendered successfully with interpolated runtime values. |
| Docker full regression | Passed | `63 passed`, `0 failed`, `1 skipped`. |
| Optimized web-flow evidence | Completed before review fixes | Browser screenshots captured. Upload reached validation, ingestion, and parsing, then failed at browser-side transaction extraction due direct M7/M8 URLs. Static configuration tests now verify this gap is fixed by blanking M7/M8 browser downstream URLs so the same-origin proxy is used. A fresh browser evidence run should be captured before PR #6 leaves draft if full E2E proof is required. |

## Regression Evidence

| Artefact | Path |
| --- | --- |
| Docker regression summary | `tests/results/DockerRegression/docker-regression-summary-2026-05-30.md` |
| Docker regression raw output | `tests/results/DockerRegression/docker-regression-raw-output-2026-05-30.txt` |
| Web-flow evidence index | `tests/results/WebAppFlowOptimized/2026-05-30/web-app-flow-evidence-2026-05-30.md` |
| Web-flow summary | `tests/results/WebAppFlowOptimized/2026-05-30/web-app-flow-summary-2026-05-30.json` |
| Web-flow contact sheet | `tests/results/WebAppFlowOptimized/2026-05-30/web-app-flow-contact-sheet-2026-05-30.png` |

## Known Gaps

- M1 authenticated backend regression is skipped unless `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` are supplied in `.env.container`.
- Full runtime consumption of `config/stats.runtime.json`, `config/stats.paths.json`, and `config/stats.logging.json` remains a follow-up hardening pass. PR #6 establishes and validates the baseline contract and fixes low-risk merge-readiness items.
- Process supervision, graceful shutdown, and production image slimming remain cloud-readiness follow-ups.
