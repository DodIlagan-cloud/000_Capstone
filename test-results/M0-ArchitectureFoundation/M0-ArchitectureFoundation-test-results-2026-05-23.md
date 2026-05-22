# M0 Architecture Foundation Test Results

<!-- M0 Foundation: result summary for the building-block architecture verification. -->

## Session

| Field | Value |
| --- | --- |
| Tested module | `M0 Project Foundation` |
| Test focus | Building-block architecture setup and repository hygiene |
| Date | `2026-05-23` |
| Verification command | `python test-results\M0-ArchitectureFoundation\M0-ArchitectureFoundation_terminal_check.py` |

## Result Summary

| Scenario | Result | Notes |
| --- | --- | --- |
| `M0-AF-01` Required architecture artefacts exist | Pass | Direct verification script checks the required repository entry points, documentation, template, and transition note. |
| `M0-AF-02` Local and build artefacts stay out of Git changes | Pass | Direct verification script checks Git ignore behavior for DOCX render output, .NET build output, and local SQLite runtime output. |
| `M0-AF-03` Stats Data persistence boundary replaces reusable Records Storage | Pass | Direct verification script checks the M0 docs and boundaries include `apps/stats-data` and omit `records-storage-module`. |
| `M0-AF-04` Runtime values must not be hardcoded | Pass | Direct verification script checks the plan, M0 spec, module template, and app/module guidance define config-driven runtime values. |
| `M0-AF-05` Later modules have a spec starting point | Pass | Manual review confirms the reusable module spec template covers scope, contracts, tests, and acceptance criteria. |
| `M0-AF-06` Existing implementation is marked transitional | Pass | Manual review confirms the root and `stats/` READMEs preserve current code while stating the new target boundaries. |

## Artefacts

- `M0-ArchitectureFoundation-test-scenarios.md`
- `M0-ArchitectureFoundation-test-raw-output-2026-05-23.txt`
- `M0-ArchitectureFoundation-manual-test-checklist.md`
- `M0-ArchitectureFoundation-screenshot-evidence-2026-05-23.md`
- `M0-ArchitectureFoundation-windows-terminal-test-2026-05-23.png`
- `M0-ArchitectureFoundation_terminal_check.py`

## Conclusion

The M0 foundation scenarios are updated for the project-level building-block architecture, including the Stats Data persistence boundary and config-driven runtime-value rule, and the direct architecture verification passed.
