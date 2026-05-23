# M0 Project Foundation File Inventory

<!-- M0 Foundation: project-level file inventory for architecture scaffolding and repository rules. -->

## Summary

This inventory records the M0 Project Foundation files used to establish the building-block architecture boundary for Stats.

M0 is no longer treated as a FastAPI service foundation module. The active implementation now belongs in the architecture owner folders under `apps/` and `modules/`.

## Architecture and Entry Points

| File | Change Type | Description |
| --- | --- | --- |
| `README.md` | Created | Introduces the Stats building-block repository layout, foundation documents, and transitional location of existing implementation work. |
| `docs/M0-foundation-module-spec.md` | Modified | Reframes M0 as Project Foundation and aligns the repository target with the building-block module plan. |
| `docs/building-block-module-plan.md` | Created | Defines build order, module boundaries, architecture direction, BA alignment, and the target repository segregation. |
| `docs/building-block-module-io-map.md` | Created | Defines starting input/output handoffs and reusable contract families for standalone modules. |
| `README.md` | Modified | Points current implementation work to the architecture owner folders rather than retired transitional folders. |

## Repository Boundary Scaffolding

| File | Change Type | Description |
| --- | --- | --- |
| `apps/README.md` | Created | Reserves the encompassing Stats product boundary for `stats-web`, `stats-data`, and Stats-only tools. |
| `modules/README.md` | Created | Defines the standalone reusable module boundary and keeps Stats-specific persistence out of reusable processing modules. |
| `contracts/README.md` | Created | Defines the shared contract boundary for identity, document, extraction, and transaction handoffs. |
| `infrastructure/README.md` | Created | Reserves infrastructure work for Compose, containers, cloud configuration, and deployment notes. |
| `samples/README.md` | Created | Defines safe sample-data lanes for synthetic and anonymized fixtures. |
| `tests/integration/README.md` | Created | Defines the cross-module integration-test boundary. |

## Documentation Standards

| File | Change Type | Description |
| --- | --- | --- |
| `docs/specs/README.md` | Created | Documents where module specifications and their templates belong. |
| `docs/specs/module-spec-template.md` | Created | Supplies the M0 module-spec template for later standalone and encompassing modules. |
| `docs/module-plans/common-file-migration-inventory.md` | Created | Maps current common/config/shared files to their future owners and migration actions before code is physically moved. |
| `apps/stats-web/README.md` | Created | Marks the target owner folder for migrating the current Stats Web app. |
| `apps/stats-data/README.md` | Created | Marks the target owner folder for Stats-specific database schema, migrations, persistence adapters, and query layer. |
| `modules/identity-access-module/README.md` | Created | Marks the target owner folder for reusable identity/access behavior. |
| `contracts/identity/README.md` | Created | Marks the target folder for identity/access contracts. |
| `contracts/documents/README.md` | Created | Marks the target folder for document/file handoff contracts. |
| `contracts/extraction/README.md` | Created | Marks the target folder for OCR, extraction, and classification contracts. |
| `contracts/transactions/README.md` | Created | Marks the target folder for transaction and data-quality contracts. |

<!-- M0 Foundation Start -->
<!-- Records the project-wide runtime configuration convention update without replacing earlier inventory rows. -->
## Runtime Configuration Convention Update

| File | Change Type | Description |
| --- | --- | --- |
| `README.md` | Modified | Adds the project-wide rule that runtime values belong in config files or supported environment/secret providers. |
| `docs/M0-foundation-module-spec.md` | Modified | Defines the runtime configuration standard for reusable modules, Stats apps, transitional code, tools, and infrastructure. |
| `docs/building-block-module-plan.md` | Modified | Adds config-driven runtime values to architecture direction and per-module standards. |
| `docs/specs/module-spec-template.md` | Modified | Prompts later module specs to name owned runtime values, config samples, override paths, and providers. |
| `apps/README.md` | Modified | Applies the config-driven runtime rule to Stats-specific applications. |
| `modules/README.md` | Modified | Applies the config-driven runtime rule to reusable building-block modules. |
<!-- M0 Foundation End -->
| `docs/module-plans/README.md` | Created | Documents where detailed module plans and boundary refinements belong. |
| `docs/evidence/README.md` | Created | Documents the project-level evidence guidance area and requires final assessment evidence to live under root `test-results/`. |

## Repository Rules

| File | Change Type | Description |
| --- | --- | --- |
| `.gitignore` | Modified | Keeps generated Python, local runtime, IDE, .NET build, and local document-render output out of version control. |
| `docs/M0-foundation-file-inventory.md` | Modified | Replaces the older service-shaped inventory with this project-foundation architecture inventory. |

## Existing M0 Supporting Artefacts

These tracked artefacts still demonstrate conventions established earlier in M0:

| Area | Current Location | Foundation Use |
| --- | --- | --- |
| Local environment guidance | `docs/local-environment-setup.md` | Records concrete runtime setup notes as dependencies appear. |
| Evidence workflow skill | `skills/module-test-evidence/` | Guides actual Windows screenshot and raw-output evidence capture. |
| File inventory skill | `skills/module-file-inventory/` | Supports later module inventories. |
| File tagging skill | `skills/module-file-tagging/` | Supports requested module comments and traceability tags. |
| Current M0 evidence | `test-results/M0-ArchitectureFoundation/` | Demonstrates project-foundation architecture checks, config-rule checks, raw output, checklist, screenshot index, and actual terminal screenshot evidence. |

## Updated M0 Architecture Test Evidence

| File | Change Type | Description |
| --- | --- | --- |
| `test-results/M0-ArchitectureFoundation/M0-ArchitectureFoundation-test-scenarios.md` | Created | Defines the updated M0 project-foundation scenarios for architecture artefacts, ignore rules, module-spec readiness, and the transitional code note. |
| `test-results/M0-ArchitectureFoundation/M0-ArchitectureFoundation_terminal_check.py` | Created | Runs direct M0 checks for required architecture paths and Git ignore hygiene. |
| `test-results/M0-ArchitectureFoundation/M0-ArchitectureFoundation-test-raw-output-2026-05-23.txt` | Created | Stores the passing raw output from the direct M0 architecture verification command. |
| `test-results/M0-ArchitectureFoundation/M0-ArchitectureFoundation-test-results-2026-05-23.md` | Created | Summarizes the updated M0 architecture scenario results. |
| `test-results/M0-ArchitectureFoundation/M0-ArchitectureFoundation-manual-test-checklist.md` | Created | Records the manual M0 review checks for docs, template readiness, and transitional boundaries. |
| `test-results/M0-ArchitectureFoundation/M0-ArchitectureFoundation-screenshot-evidence-2026-05-23.md` | Created | Indexes the retained actual Windows terminal screenshot and states what it proves. |
| `test-results/M0-ArchitectureFoundation/M0-ArchitectureFoundation-windows-terminal-test-2026-05-23.png` | Created | Cropped actual Windows PowerShell screenshot showing the direct M0 architecture checks passing. |

## Verification Notes

This M0 architecture execution should be checked by:

1. Confirming the target top-level boundaries are visible in the repository.
2. Confirming later module work can start from `docs/specs/module-spec-template.md`.
3. Confirming the runtime configuration rule prevents environment-dependent values and secrets from being hardcoded in source.
4. Confirming the building-block plan and I/O map remain the architecture reference.
5. Confirming ignored caches, local runtime files, and build outputs do not appear as Git changes.

Migrations of active implementation code should be planned in the owning module spec so history and cross-module boundaries remain reviewable.
