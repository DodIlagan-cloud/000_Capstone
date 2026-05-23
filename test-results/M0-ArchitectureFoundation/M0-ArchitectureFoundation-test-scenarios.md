# M0 Architecture Foundation Test Scenarios

<!-- M0 Foundation: architecture verification scenarios for the building-block setup. -->

## Scope

These scenarios verify M0 as a project foundation module after the building-block architecture shift.

They do not verify Python API behavior, .NET page behavior, or M1 identity behavior. M1 executable evidence now lives with the migrated Identity Access Module.

## Scenarios

| ID | Scenario | Verification Method | Expected Result |
| --- | --- | --- | --- |
| `M0-AF-01` | Required architecture artefacts exist | Run `M0-ArchitectureFoundation_terminal_check.py` and inspect the required-path checks. | Root entry point, boundary READMEs, foundation docs, module spec template, and transition note are present. |
| `M0-AF-02` | Local and build artefacts stay out of Git changes | Run `M0-ArchitectureFoundation_terminal_check.py` and inspect `git check-ignore` checks. | Local DOCX render output, .NET build output, and Python test cache output are ignored. |
| `M0-AF-03` | Stats Data persistence boundary replaces reusable Records Storage | Run `M0-ArchitectureFoundation_terminal_check.py` and inspect content checks. | M0 docs and app/module boundaries include `apps/stats-data` and omit the obsolete `records-storage-module` lane. |
| `M0-AF-04` | Runtime values must not be hardcoded | Run `M0-ArchitectureFoundation_terminal_check.py` and inspect configuration-rule checks. | M0 plan, spec, root/app/module guidance, and module template require config files or supported environment/secret providers for environment-dependent runtime values. |
| `M0-AF-05` | Common files have migration ownership decisions | Run `M0-ArchitectureFoundation_terminal_check.py` and inspect migration checks. | Common/config/shared files have documented target owners and actions before code is physically moved. |
| `M0-AF-06` | Later modules have a spec starting point | Inspect `docs/specs/module-spec-template.md`. | Template includes module identity, BA alignment, goals, non-goals, contracts, dependencies, tests, acceptance criteria, and deferred items. |
| `M0-AF-07` | Retired transitional implementation paths are absent | Run `M0-ArchitectureFoundation_terminal_check.py` and inspect retired-path absence checks. | Active M1 work has moved to `modules/identity-access-module` and `apps/stats-web`; old source and evidence paths are absent. |

## Evidence Mapping

| Scenario | Evidence |
| --- | --- |
| `M0-AF-01` | Raw output and Windows terminal screenshot from the direct verification script. |
| `M0-AF-02` | Raw output and Windows terminal screenshot from the direct verification script. |
| `M0-AF-03` | Raw output and Windows terminal screenshot from the direct verification script. |
| `M0-AF-04` | Raw output and Windows terminal screenshot from the direct verification script. |
| `M0-AF-05` | Raw output and Windows terminal screenshot from the direct verification script. |
| `M0-AF-06` | Checklist review plus the retained module spec template. |
| `M0-AF-07` | Raw output and Windows terminal screenshot from the direct verification script. |
