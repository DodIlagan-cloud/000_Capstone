# Validation Plan

## Goal

Validate that the architecture hardening pass creates a clean baseline without duplicating full module execution unnecessarily.

## Automated Checks

| Check | Command | Purpose |
| --- | --- | --- |
| Registry JSON parse | `python -c "...json.loads(...)"` | Confirms central runtime, path, and logging registries are valid JSON. |
| Architecture hardening contract | `pytest tests\integration\test_architecture_hardening_contract.py` | Ensures central registries exist, module defaults use registered keys, active specs avoid retired architecture wording, and logging rules require redaction/stdout behavior. |
| M13 container contract | `pytest tests\integration\test_m13_containerization_contract.py` | Ensures container packaging and container-first runtime contracts remain valid. |
| Docker full regression | `powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_docker_full_regression_evidence.ps1 -LeaveStackRunning` | Runs the single authoritative M1-M8 backend regression through the Docker runtime. |
| Optimized web-flow evidence | `python tests\scripts\regression\capture_web_app_flow_evidence_optimized_2026_05_30.py` | Reuses the running Docker stack, captures browser-visible flow once, and uploads one representative fixture without repeating full backend regression. |

## Duplicate Avoidance

- Do not run both M13-specific OCR acceptance and full Docker regression unless the change specifically targets OCR/container packaging.
- Use the full Docker regression as the authoritative M1-M8 backend pass.
- Use optimized browser evidence only for UI-visible flow and screenshots.
- Upload one representative UI fixture in the browser evidence because full per-fixture processing is already covered by Docker regression.

## Evidence Locations

| Evidence | Location |
| --- | --- |
| Docker regression | `tests/results/DockerRegression/` |
| Optimized web flow | `tests/results/WebAppFlowOptimized/2026-05-30/` |
