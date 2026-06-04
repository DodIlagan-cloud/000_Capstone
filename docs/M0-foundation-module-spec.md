# M0 Project Foundation Specification

<!-- M0 Foundation: project foundation specification aligned with the Stats building-block module plan. -->

## Module Summary

M0 Project Foundation establishes the repository, documentation, evidence, and delivery conventions for the Stats capstone project.

Stats is developed as an integrating product built from reusable building-block modules and encompassing Stats product modules. M0 does not own product features such as authentication, file ingestion, OCR, Stats persistence, or dashboard logic. It provides the rules, templates, and project scaffolding that allow those later modules to be specified, implemented, tested, evidenced, versioned, and composed consistently.

## Architecture Alignment

M0 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/architecture-hardening/current-baseline.md`

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
- Each later module owns its own spec, contract, tests, evidence, configuration sample, runtime instructions, and container wiring. From M13 onward, official module tests and evidence run through the Stats container.

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
- Establish a project-wide configuration and logging convention so environment-dependent runtime values and log behavior are not hardcoded into project source.
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
|-- samples/
|   |-- synthetic/
|   `-- anonymized/
`-- tests/
    `-- integration/
```

### Active-Architecture Rule

Active implementation guidance must use only the current architecture roots: `apps/`, `modules/`, `contracts/`, `config/`, `infrastructure/`, `docs/`, `samples/`, and root `tests/`.

Historical or retired paths may be mentioned only in file inventories, history notes, or evidence context. They must not appear in active module specs as current implementation surfaces or migration guidance.

## Module Standards

Every later standalone module must provide:

1. A module spec with goals, non-goals, tasks, and acceptance criteria.
<!-- M13 - Containerization Start -->
2. A runtime command and test command. From M13 onward, official module acceptance commands must execute through the Stats container; host/local commands are diagnostics only.
<!-- M13 End -->
3. A clear input/output contract.
4. Module-local automated tests.
5. Evidence for acceptance tests.
6. A configuration example with no secrets committed.
7. Container runtime wiring before official module acceptance after M13.
8. Failure behavior visible to callers through explicit errors or status results.
9. Config-driven real-data automated/evidence tests when the module processes realistic files, records, messages, or external-style inputs.

Encompassing Stats modules such as Stats Web and Stats Data must state which reusable module contracts they call or store and must not absorb reusable OCR, parsing, validation, or authentication internals.

<!-- M0 Foundation Start -->
<!-- Defines the spec-first build rule for architecture-aligned implementation. -->
### Spec-First Build Rule

The current module spec is the source of truth for what will be built.

Before implementation starts or changes direction, the owning module spec must be created or updated to reflect the accepted architecture decision, module boundary, contract, runtime path, test plan, and acceptance criteria. Code, tests, UI behavior, and evidence must then align to that current spec.

If an architectural decision changes after implementation has started, the order is:

1. Update the owning spec and file inventory.
2. Review the implementation against the updated spec.
3. Update code and tests only after the spec reflects the decision.
4. Validate through the official container-first test/evidence path from M13 onward.

Implementation must not silently redefine scope outside the spec. If code behavior and the spec disagree, the mismatch is a defect until either the spec is intentionally updated or the code is brought back into alignment.
<!-- M0 Foundation End -->

<!-- M0 Foundation Start -->
<!-- Defines the project-wide rule for config-driven runtime values. -->
## Runtime Configuration Standard

The whole Stats project must use configuration files or supported environment/secret providers for runtime values instead of hardcoding them in source code.

This rule applies to reusable modules, encompassing Stats apps, admin tools, infrastructure scripts, and later cloud deployment work.

The central runtime configuration registry is:

```text
config/stats.runtime.json
```

That registry names the project-wide configuration surface for paths, URLs, ports, database targets, secrets, storage providers, OCR settings, service endpoints, test fixtures, and cloud-ready settings. Module-local config files may still exist, but they should align to this registry rather than inventing unrelated environment variable names.

Module-local configuration files are allowed and required. They preserve standalone module behavior. They must use only centrally registered keys, and module config loaders must follow the configured precedence: central registry metadata, module safe defaults, ignored local overrides, environment variables, and later managed cloud configuration or secret providers.

Examples of runtime values that must be configurable:

- API and service base URLs.
- Hosts, ports, and browser/CORS origins.
- Database targets, connection values, storage targets, and queue/mailbox/resource names.
- Secrets, passwords, tokens, keys, bootstrap credentials, and authentication settings.
- Environment-dependent file paths, feature switches, timeouts, limits, and cloud deployment settings.

Directory paths follow the Stats root-resolution convention:

- `config/stats.paths.json` is the central logical path map for the overall Stats application.
- `STATS_APP_ROOT` supplies the physical runtime root for the current environment.
- Local development, Docker, and cloud deployments may use different physical roots while preserving the same logical project paths.
- Modules must resolve environment-dependent paths from configuration or a storage provider instead of assuming `C:\000_Capstone`, `/app`, or another machine-specific root.
- Durable uploads, OCR outputs, workflow artefacts, and future evidence exports must be able to move from `STATS_STORAGE_PROVIDER=LocalFileSystem` to a cloud provider such as Azure Blob Storage without rewriting module business logic.

Project configuration may include committed safe local defaults, examples, and templates. Real secrets and developer-specific overrides must be excluded from source control and supplied through ignored local config, environment variables, or managed secret providers.

Each module or app spec must name its configuration sample and the runtime values it owns. Consumers must be able to change environment-dependent targets without editing source code.

If a new setting changes by developer machine, container, cloud environment, secret rotation, deployment target, port conflict, or test fixture location, the owning module must add it to the configuration surface before implementation depends on it.
<!-- M0 Foundation End -->

## Logging Standard

The whole Stats project must follow the central logging contract:

```text
config/stats.logging.json
```

Modules may keep module-local logging setup code, but log behavior must be governed centrally. This includes log level, format, stdout/stderr destination, correlation or request context, and redaction behavior.

Logs must not expose passwords, tokens, secret keys, database connection strings, raw OCR text, account numbers, card numbers, or personal identifiers. Container logs must be collectable through stdout/stderr so Docker, CI, and later Azure logging can capture them without file scraping.

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
- Logging configuration and redaction behavior, aligned to `config/stats.logging.json`.
<!-- M0 Foundation End -->
- Automated tests, manual checks, evidence artefacts, and acceptance criteria.
- Real-data test inputs, configuration variables, privacy constraints, and evidence expectations when realistic local datasets are required.
- Deferred items for later modules.

Each module spec must also identify the architectural decisions it depends on and must be updated before those decisions are implemented. Later code reviews, tests, and evidence should verify the implementation against the spec rather than treating the implementation as the authority.

For reusable modules, the starting contract should be derived from `docs/building-block-module-io-map.md` and refined only inside the owning module spec.

## Contract Boundary Rules

M0 establishes these project rules:

- Reusable modules expose explicit contracts instead of depending on another module's internal implementation.
<!-- M0 Foundation Start -->
<!-- Applies the project-wide runtime configuration rule at the contract boundary level. -->
- Runtime values are configured through config files or supported environment/secret providers instead of being embedded in source code.
<!-- M0 Foundation End -->
- Stats Web may call reusable module APIs, but it should not implement reusable validation, extraction, or identity rules.
- File validation and file ingestion remain separate concerns inside the merged intake module boundary.
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
- GitHub history should preserve traceability from spec to implementation to evidence.

### Recommended Commit Grouping

Use separate commits for:

- Module specs and design artefacts.
- Module implementation changes.
- Acceptance-test evidence and regression evidence when produced after implementation.
- Reusable Codex skills or workflow tooling.
- Cross-module integration changes.

## Evidence Standard

All test artefacts must be stored under the repository-root `tests/` folder.

Use these root-owned locations:

- Automated unit tests: `tests/unit/<module>/`
- Automated integration and contract tests: `tests/integration/`
- Test fixtures and real local inputs: `tests/input/`
- Evidence scripts and reusable test helpers: `tests/scripts/`
- Test results, raw output, screenshots, checklists, and evidence summaries: `tests/results/<module-or-session>/`

Do not create module-local `test-results/` folders under `modules/` or `apps/`. Module specs and READMEs may link to root `tests/results/` evidence, but evidence artefacts themselves belong under the root `tests/` tree.

### Required Evidence Types

- Test-result summary.
- Raw test or direct verification output.
- Manual verification checklist when manual checks are used.
- Screenshot evidence index.
- Actual Windows browser screenshots for web/API UI evidence when screenshots are required.
- Actual Windows terminal screenshots for command/test evidence when screenshots are required.
- Real-data automated/evidence test output for modules that process user-like files, extracted text, classifications, transactions, records, emails, or stored workflow artefacts.

### Real-Data Test Standard

Modules that process realistic inputs must use a configurable real-data test path for unit, API, regression, integration, E2E, container, and evidence testing.

- Real-data tests must be automated where practical and runnable from the module test suite or evidence runner.
- Real-data locations must be supplied through configuration or environment variables such as `STATS_TESTDATA_DIR`; personal drive paths must not be hardcoded in source.
- Automated application-flow tests must use configured real application test data. When the configured real-data directory is unavailable, the test should fail or the evidence runner should stop with a clear setup message rather than silently substituting synthetic data.
- Synthetic inline payloads must not be the primary proof of module functionality. If used for a narrow edge case, they must be documented as supplemental to `tests/input` coverage.
- Evidence runs should set the required real-data variables and retain raw output proving the real input was processed.
- From M14 onward, official cloud iteration evidence should repeat applicable tests against the Azure cloud-dev deployment after local container validation passes.
- Tests must assert the business-relevant handoff, not only that the command succeeded. Examples include saved file location under configured storage, extracted text presence, classification label, parsed transaction count, validation findings, or persistence status.
- Private/anonymized source files should remain outside source control unless a safe committed sample dataset is explicitly approved.

### Screenshot Rules

- Prefer actual browser and terminal screenshots over rendered-response images.
- Crop screenshots to the relevant browser or terminal content.
- State what each screenshot proves in the screenshot evidence index.
- Keep regression evidence separate from the initial module evidence.
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

## M0 Verification

M0 verification is primarily project-convention verification.

### Required Checks

- Repository is tracked in Git and published to the intended GitHub repository.
- Architecture documentation identifies the building-block module boundaries.
- Project rules require environment-dependent runtime values to be configurable without source-code edits.
- A later module can start from a spec, contract, acceptance criteria, and evidence plan without inventing a new process.
- A later module can treat its current spec as the build authority and update that spec before changing implementation direction.
- Evidence rules are demonstrated by at least one module evidence set.
- Ignore rules prevent caches, secrets, and obvious local-only outputs from being committed.

<!-- M13 - Containerization Start -->
Current official M0 acceptance evidence must come from the container-first module runner. Host-side evidence can be used only as diagnostic context after M13.
<!-- M13 End -->

## Runtime and Dependencies

M0 itself does not require one application runtime. It governs a repository that may contain multiple runtimes, including:

- `.NET` for the Stats Web encompassing app.
- Python/FastAPI for current backend/API modules where applicable.
- PostgreSQL or other module-specific dependencies defined by later specs.
- Container and cloud tooling when those project modules are reached.

<!-- M13 - Containerization Start -->
Each later module spec must declare its own runtime command, test command, configuration sample, and dependency assumptions. From M13 onward, official runtime and test evidence must identify the container execution path.
<!-- M13 End -->

## Acceptance Criteria

M0 is complete when:

- The building-block architecture direction is documented and used as the boundary for later module work.
- Module order distinguishes Project Foundation, reusable standalone modules, Stats Web encompassing work, Stats Data and Persistence, integration, infrastructure, and evaluation evidence.
- Module spec, contract, file inventory, tagging, GitHub, and evidence conventions are documented.
- The spec-first build rule is documented so implementation follows accepted architecture decisions rather than redefining scope ad hoc.
- Runtime configuration rules prevent environment-dependent values and secrets from being hardcoded into source.
- Logging rules centralize log level, format, redaction, and container/cloud collection behavior.
- Later module specs can define their own owner folders, contracts, tests, and evidence without treating a single backend service as the entire application.
- GitHub stores the capstone repository history and meaningful project artefacts.
- At least one module evidence package demonstrates the required test-result, raw-output, checklist, screenshot-index, and cropped actual screenshot pattern.

## Implementation Notes

- New feature behavior should be specified under the owning building-block module rather than appended to M0.
- Use `docs/building-block-module-plan.md` as the architecture boundary before starting each later module chat.
