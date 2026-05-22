# M0 Architecture Foundation Manual Test Checklist

<!-- M0 Foundation: manual review checklist for the new architecture setup. -->

| Check | Result | Evidence |
| --- | --- | --- |
| Building-block plan exists and identifies M0 as Project Foundation. | Pass | `docs/building-block-module-plan.md` |
| Building-block I/O map exists for reusable module handoffs. | Pass | `docs/building-block-module-io-map.md` |
| Root README identifies the new `apps`, `modules`, `contracts`, `infrastructure`, `samples`, and integration-test boundaries. | Pass | `README.md` |
| Boundary READMEs are present for the new architecture folders. | Pass | Direct verification script output |
| Module spec template is available for later building blocks. | Pass | `docs/specs/module-spec-template.md` |
| Existing `stats/` code is described as transitional implementation work. | Pass | `stats/README.md` |
| Ignore rules cover local DOCX render checks, .NET build output, and the local Stats SQLite runtime file. | Pass | Direct verification script output |

## Manual Review Note

This checklist verifies M0 project conventions. Application test suites remain owned by the module or app that changes executable behavior.
