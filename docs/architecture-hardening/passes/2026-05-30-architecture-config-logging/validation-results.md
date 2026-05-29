# Validation Results

## Date

2026-05-30

## Results

| Check | Result | Notes |
| --- | --- | --- |
| Registry JSON parse | Passed | `config/stats.runtime.json`, `config/stats.paths.json`, and `config/stats.logging.json` parsed successfully. |
| Architecture hardening contract | Passed | `4 passed`. Pytest cache warnings were local permission warnings only. |
| M13 container contract | Passed | `53 passed`. Pytest cache warning was local permission-only. |
| Docker full regression | Passed | `63 passed`, `0 failed`, `1 skipped`. |
| Optimized web-flow evidence | Completed with documented gap | Browser screenshots captured. Upload reached validation, ingestion, and parsing, then failed at browser-side transaction extraction due direct M7/M8 URLs. |

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
- Stats Web Upload page uses direct browser URLs for M7/M8 (`127.0.0.1:8016` and `127.0.0.1:8017`) instead of the same-origin Stats Web proxy, causing browser-side transaction extraction/data validation to fail after parsing.
