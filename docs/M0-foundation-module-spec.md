# M0 Project Foundation Specification

<!-- M0 Foundation: project foundation specification aligned with the Stats building-block module plan. -->

## Module Summary

M0 Project Foundation establishes the repository, documentation, evidence, and delivery conventions for the Stats capstone project.

Stats is developed as an integrating product built from reusable building-block modules and encompassing Stats product modules. M0 does not own product features such as authentication, file ingestion, OCR, Stats persistence, or dashboard logic. It provides the rules, templates, and project scaffolding that allow those later modules to be specified, implemented, tested, evidenced, versioned, and composed consistently.

## Architecture Alignment

M0 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`

The building-block plan defines M0 as:

| Field | M0 Direction |
| --- | --- |
| Build order | `0` |
| Module | Project Foundation |
| Type | Project |
| Main responsibility | Repo conventions, module specs, GitHub workflow, evidence standard |
| Reusable output | Module template and repo rules |

The architecture direction established by M0 is:

- Stats Web is the encompassing `.NET` user-facing app and orchestration shell.
- Stats Data and Persistence is the encompassing Stats product module for database schema, migrations, persistence adapters, and stored workflow results.
- Backend capabilities are segregated into standalone modules that can be reused outside Stats.
- Reusable modules communicate through explicit APIs, contracts, files, queues, or events rather than importing each other's internal code.
- Each later module owns its own spec, contract, tests, evidence, configuration sample, runtime instructions, and container path when containerization is reached.

## Goals

- Establish the repository layout direction for apps, reusable modules, contracts, infrastructure, docs, samples, and integration tests.
- Define the standard artefacts every later standalone module or encompassing app module must produce.
- Create a module specification convention that starts with goals, non-goals, contracts, acceptance criteria, and test plan before implementation.
- Establish GitHub/version-control workflow for traceability of code, specs, evidence, and module changes.
- Establish module tagging and file-inventory conventions so module-owned changes are reviewable.
- Establish test-result and screenshot-evidence conventions suitable for capstone assessment.
- Record the initial architecture boundaries that prevent Stats-specific UI flows from leaking into reusable backend apps.
<!-- M0 Foundation Start -->
<!-- Adds the project-wide runtime configuration goal. -->
- Establish a project-wide configuration convention so environment-dependent runtime values are not hardcoded into project source.
<!-- M0 Foundation End -->

## Non-Goals

- Implementing the Identity Access Module.
- Implementing Stats Web pages, navigation, login UI, upload UI, dashboard UI, or reporting UI.
- Implementing file validation, file ingestion, OCR, document classification, transaction extraction, data validation, Stats Data and Persistence, or email ingestion.
- Defining final database schemas for later modules.
- Containerizing modules or deploying them to cloud infrastructure.
- Replacing later module specs with one project-wide feature specification.

## M0 Outputs

M0 must produce or establish these project outputs:

| Output | Purpose |
| --- | --- |
| Building-block module plan | Defines architecture boundaries, module build order, composition view, and BA alignment. |
| Building-block I/O map | Defines starting input/output contracts for reusable modules. |
| M0 project foundation spec | Defines the project standards in this document. |
| Module spec convention | Ensures each module starts from scope, contracts, acceptance criteria, and test plan. |
| Module file inventory convention | Records created and modified files per module or meaningful change set. |
| Module tagging convention | Marks module-owned text/code blocks where requested for traceability. |
| Test evidence convention | Stores test results, raw outputs, checklists, and actual screenshot evidence. |
| GitHub workflow | Preserves specs, implementation, evidence, and commit history. |

## Repository Direction

The repository should move toward the structure defined by the building-block module plan:

```text
000_Capstone/
|-- apps/
|   |-- stats-web/
|   |-- stats-data/
|   `-- stats-admin-tools/
|-- modules/
|   |-- identity-access-module/
|   |-- file-validation-module/
|   |-- file-ingestion-module/
|   |-- ocr-extraction-module/
|   |-- document-classification-module/
|   |-- transaction-extraction-module/
|   |-- data-validation-module/
|   `-- email-ingestion-module/
|-- contracts/
|   |-- identity/
|   |-- documents/
|   |-- extraction/
|   `-- transactions/
|-- infrastructure/
|   |-- compose/
|   |-- containers/
|   `-- cloud/
|-- docs/
|   |-- module-plans/
|   |-- specs/
|   `-- evidence/
|-- test-results/
|   |-- M0-ArchitectureFoundation/
|   |-- RegTest-AdminUserFlow-M0-M1/
|   `-- M2-StatsWebShell-M0-M1/
|-- samples/
|   |-- synthetic/
|   `-- anonymized/
`-- tests/
    `-- integration/
```

### Current-Workspace Note

The repository now uses the target architecture folders directly. M1 identity is under `modules/identity-access-module/`, and the current Stats Web consumer is under `apps/stats-web/`.

Later module work must use the owning architecture folder rather than recreating retired transitional folders.

### Root Project Artefact Rule

Project-wide artefacts must live at the repository root, not inside an individual module or app folder.

| Artefact Type | Required Location |
| --- | --- |
| Module specifications, file inventories, project plans, diagrams, and project documentation | `docs/` |
| Test results, raw command output, manual checklists, screenshot indexes, and evidence screenshots | `test-results/` |
| Cross-module integration tests | `tests/integration/` |
| Shared contracts | `contracts/` |
| Module/app implementation code, module-owned tests, runtime config samples, and local run instructions | Owning `modules/...` or `apps/...` folder |

Module folders should contain only code, module-local automated tests, runtime configuration samples, module README files, and assets needed by that module or app. They must not contain final assessment evidence folders unless a later project-level decision explicitly changes this rule.

## Module Standards

Every later standalone module must provide:

1. A module spec with goals, non-goals, tasks, and acceptance criteria.
2. A local run command and test command.
3. A clear input/output contract.
4. Module-local automated tests under the owning module or app folder.
5. Evidence for acceptance tests under root `test-results/`.
6. A configuration example with no secrets committed.
7. A Dockerfile or container plan before cloud deployment.
8. Failure behavior visible to callers through explicit errors or status results.

Encompassing Stats modules such as Stats Web and Stats Data must state which reusable module contracts they call or store and must not absorb reusable OCR, parsing, validation, or authentication internals.

<!-- M0 Foundation Start -->
<!-- Defines the project-wide rule for config-driven runtime values. -->
## Runtime Configuration Standard

The whole Stats project must use configuration files or supported environment/secret providers for runtime values instead of hardcoding them in source code.

This rule applies to reusable modules, encompassing Stats apps, transitional code, admin tools, infrastructure scripts, and later cloud deployment work.

Examples of runtime values that must be configurable:

- API and service base URLs.
- Hosts, ports, and browser/CORS origins.
- Database targets, connection values, storage targets, and queue/mailbox/resource names.
- Secrets, passwords, tokens, keys, bootstrap credentials, and authentication settings.
- Environment-dependent file paths, feature switches, timeouts, limits, and cloud deployment settings.

Project configuration may include committed safe local defaults, examples, and templates. Real secrets and developer-specific overrides must be excluded from source control and supplied through ignored local config, environment variables, or managed secret providers.

Each module or app spec must name its configuration sample and the runtime values it owns. Consumers must be able to change environment-dependent targets without editing source code.
<!-- M0 Foundation End -->

## Module Specification Convention

Each module spec must identify:

- Module number, name, type, and build order.
- Business-analysis alignment.
- Goals and non-goals.
- Architecture boundary and owner folder.
- Inputs, outputs, contracts, error/status results, and dependencies.
- Local runtime and configuration expectations.
<!-- M0 Foundation Start -->
<!-- Requires each later module spec to name its runtime configuration surface. -->
- Config files, safe examples, override paths, and runtime values that must be changed without source edits.
<!-- M0 Foundation End -->
- Automated tests, manual checks, evidence artefacts, and acceptance criteria.
- Deferred items for later modules.

For reusable modules, the starting contract should be derived from `docs/building-block-module-io-map.md` and refined only inside the owning module spec.

## Contract Boundary Rules

M0 establishes these project rules:

- Reusable modules expose explicit contracts instead of depending on another module's internal implementation.
<!-- M0 Foundation Start -->
<!-- Applies the project-wide runtime configuration rule at the contract boundary level. -->
- Runtime values are configured through config files or supported environment/secret providers instead of being embedded in source code.
<!-- M0 Foundation End -->
- Stats Web may call reusable module APIs, but it should not implement reusable validation, extraction, or identity rules.
- File Validation and File Ingestion remain separate concerns.
- OCR Extraction, Document Classification, and Transaction Extraction remain separate concerns.
- Stats Data and reporting consume results from processing modules; they do not silently become reusable processing modules.
- Integration behavior belongs in Stats workflow integration tests or in the coordinating Stats app layer.

## GitHub and Version-Control Workflow

M0 must establish a GitHub workflow for the capstone repository.

### Requirements

- Source code, specs, inventories, evidence files, and project conventions must be version controlled.
- Commits should group one meaningful change set where practical.
- Module implementation, module test evidence, and reusable skills should be committed separately when they are logically separate.
- Generated caches, local runtime files, local tool state, secrets, and build artefacts must be excluded through ignore rules or module-local ignore files.
- Project-wide specs, inventories, documentation, and evidence should be committed from root `docs/` and root `test-results/` paths even when they describe one module.
- GitHub history should preserve traceability from spec to implementation to evidence.

### Recommended Commit Grouping

Use separate commits for:

- Module specs and design artefacts.
- Module implementation changes.
- Acceptance-test evidence and regression evidence when produced after implementation.
- Reusable Codex skills or workflow tooling.
- Cross-module integration changes.

## Evidence Standard

Each module evidence set must be stored in a named folder under root `test-results/`.

Do not place final assessment evidence under `apps/<app>/test-results/` or `modules/<module>/test-results/`. Those module/app folders are reserved for implementation code, module-local automated tests, runtime configuration samples, and module-specific assets.

### Required Evidence Types

- Test-result summary.
- Raw test or direct verification output.
- Manual verification checklist when manual checks are used.
- Screenshot evidence index.
- Actual Windows browser screenshots for web/API UI evidence when screenshots are required.
- Actual Windows terminal screenshots for command/test evidence when screenshots are required.

### Screenshot Rules

- Prefer actual browser and terminal screenshots over rendered-response images.
- Crop screenshots to the relevant browser or terminal content.
- State what each screenshot proves in the screenshot evidence index.
- Keep regression evidence separate from the initial module evidence when useful, but keep both under root `test-results/`.
- Use clear folder names that start with the tested module prefix, for example `M0-FoundationInitial` or `M1-UserAccessManagement`.

## File Inventory and Tagging Standard

Each module or substantial change set should identify files created or modified and describe why.

Where module tagging is requested:

- Tag text/code files with concise module start/end markers or concise module comments appropriate to the file format.
- Keep tags readable without obscuring implementation logic.
- Do not attempt to inline-tag binary screenshots.
- Retest affected executable code after tagging changes.

## M0 Documentation Artefacts

At minimum, M0 documentation must include:

- This M0 Project Foundation spec.
- The building-block module plan.
- The building-block module I/O map.
- A reusable module spec template for later building blocks.
- File inventories for implemented modules or meaningful module change sets.
- Local environment guidance as project dependencies become concrete.
- Root `test-results/` evidence folders for module verification and regression sessions.

## M0 Verification

M0 verification is primarily project-convention verification.

### Required Checks

- Repository is tracked in Git and published to the intended GitHub repository.
- Architecture documentation identifies the building-block module boundaries.
- Project rules require environment-dependent runtime values to be configurable without source-code edits.
- A later module can start from a spec, contract, acceptance criteria, and evidence plan without inventing a new process.
- Evidence rules are demonstrated by at least one module evidence set.
- Ignore rules prevent caches, secrets, and obvious local-only outputs from being committed.

### Supporting Demonstration

M0 architecture evidence under `test-results/M0-ArchitectureFoundation/` demonstrates the current project-level evidence workflow.

## Runtime and Dependencies

M0 itself does not require one application runtime. It governs a repository that may contain multiple runtimes, including:

- `.NET` for the Stats Web encompassing app.
- Python/FastAPI for current backend/API modules where applicable.
- PostgreSQL or other module-specific dependencies defined by later specs.
- Container and cloud tooling when those project modules are reached.

Each later module spec must declare its own run command, test command, configuration sample, and dependency assumptions.

## Acceptance Criteria

M0 is complete when:

- The building-block architecture direction is documented and used as the boundary for later module work.
- Module order distinguishes Project Foundation, reusable standalone modules, Stats Web encompassing work, Stats Data and Persistence, integration, infrastructure, and evaluation evidence.
- Module spec, contract, file inventory, tagging, GitHub, and evidence conventions are documented.
- Runtime configuration rules prevent environment-dependent values and secrets from being hardcoded into source.
- Later module specs can define their own owner folders, contracts, tests, and evidence without treating a single backend service as the entire application.
- Project-wide documentation and evidence are stored at root `docs/` and root `test-results/`, while module/app folders keep only module-specific code, tests, configuration, runtime files, and assets.
- GitHub stores the capstone repository history and meaningful project artefacts.
- At least one module evidence package demonstrates the required test-result, raw-output, checklist, screenshot-index, and cropped actual screenshot pattern.

## Implementation Notes

- M0 ownership is project-level foundation.
- New feature behavior should be specified under the owning building-block module rather than appended to M0.
- Use `docs/building-block-module-plan.md` as the architecture boundary before starting each later module chat.
