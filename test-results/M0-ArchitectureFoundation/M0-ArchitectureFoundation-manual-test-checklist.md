# M0 Architecture Foundation Manual Test Checklist

<!-- M0 Foundation: manual review checklist for the new architecture setup. -->

| Check | Result | Evidence |
| --- | --- | --- |
| Building-block plan exists and identifies M0 as Project Foundation. | Pass | `docs/building-block-module-plan.md` |
| Building-block I/O map exists for reusable module handoffs. | Pass | `docs/building-block-module-io-map.md` |
| Root README identifies the new `apps`, `modules`, `contracts`, `infrastructure`, `samples`, and integration-test boundaries. | Pass | `README.md` |
| Boundary READMEs are present for the new architecture folders. | Pass | Direct verification script output |
| Stats-specific persistence is identified as `apps/stats-data/`, not a reusable records storage module. | Pass | `docs/building-block-module-plan.md`, `apps/README.md`, `modules/README.md` |
| Runtime values, secrets, and environment-dependent targets are required to come from config files or supported environment/secret providers instead of hardcoded source values. | Pass | `README.md`, `docs/building-block-module-plan.md`, `docs/M0-foundation-module-spec.md`, `docs/specs/module-spec-template.md` |
| Common/config/shared files have documented owners and migration actions before physical code movement. | Pass | `docs/module-plans/common-file-migration-inventory.md` |
| Module spec template is available for later building blocks. | Pass | `docs/specs/module-spec-template.md` |
| Retired transitional source and evidence paths are absent after the M1 migration. | Pass | Direct verification script output |
| Ignore rules cover local DOCX render checks, .NET build output, and Python test cache output. | Pass | Direct verification script output |

## Manual Review Note

This checklist verifies M0 project conventions. Application test suites remain owned by the module or app that changes executable behavior.
