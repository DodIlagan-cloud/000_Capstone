<!-- M0 Foundation / M13 Containerization Start -->
<!-- Formalizes the project-wide rule that tests are part of the build loop, not an end-of-project activity. -->

# Testing Build Loop Policy

## Purpose

Testing in the Stats project must live inside the build loop. Tests are not an afterthought added after a module is implemented; they are part of how each module is specified, built, reviewed, and accepted.

This policy applies to Codex, Claude Code, Claude Cowork, browser agents, manual developer testing, and future CI/CD automation.

## Core Rule

Every feature or module change must define its test path while it is being designed or implemented.

No module is considered complete until the relevant unit, API, integration, E2E/browser, container, and evidence checks have passed at the correct level for that module.

When a test exercises Stats functionality, it must use the configured project test-data directory, `tests/input`, as the source of input data. This applies to unit, API, regression, integration, E2E, container, and evidence tests. Synthetic inline payloads are allowed only for narrow edge cases that cannot be represented safely from the real fixture set, and those tests must complement, not replace, real-data coverage from `tests/input`.

## Tool-Matched Testing

Testing must match the tool and workflow being used.

| Tool / Build Style | Required Testing Behavior |
| --- | --- |
| Codex / Claude Code / agentic coding | Use clear test instructions, runnable scripts, contract checks, and regression commands as part of the implementation loop. |
| Claude Cowork | Follow the module spec, update or add tests with the change, and report exactly what was run and what remains unverified. |
| Browser-based tools | Generate feature test cases and validate them with a browser agent or manual click-through before accepting the feature. |
| Stats Web UI work | Include browser or E2E validation for user-visible flows, not only backend or unit tests. |
| Python module work | Include module unit/API tests and contract-shaped input/output checks. |
| Database, OCR, or cross-module work | Include integration/container validation because unit tests cannot prove runtime wiring. |

## Test Types In The Build Loop

| Test Type | Purpose | When Required |
| --- | --- | --- |
| Unit tests | Validate module rules and edge cases in isolation using `tests/input`-derived data where the function processes real documents, OCR text, extraction candidates, validation records, or workflow artefacts. | Any module logic change. |
| API tests | Validate FastAPI or web endpoint behavior and response contracts using `tests/input` files or payloads produced from them. | Any module API or contract change. |
| Integration tests | Validate configuration, orchestration, and module handoffs using configured project fixtures. | Any cross-module, config, or workflow change. |
| E2E/browser tests | Validate real user flows through Stats Web using actual files from `tests/input`. | Any frontend or upload/workflow experience change. |
| Container tests | Validate the production-like runtime, Tesseract, DB, and service health using `tests/input` copied into the container. | Required for official acceptance from M13 onward. |
| Evidence tests | Produce raw output, screenshots, JSON summaries, and checklists from actual configured project fixtures. | Required for module completion and Capstone assessment support. |

## Build Loop Sequence

Each module should follow this sequence:

1. Confirm or create the module spec.
2. Confirm inputs, outputs, contracts, acceptance criteria, and non-goals.
3. Identify the required tests before implementation grows.
4. Implement the smallest coherent task.
5. Run the matching test set.
6. Fix issues immediately while the context is fresh.
7. Capture evidence for acceptance-level behavior.
8. Update file inventory, roadmap notes, and evidence references.
9. Commit or open a PR only after tests and evidence are in an acceptable state.

## Container-First Official Acceptance

From M13 onward, official acceptance evidence must run through the Stats container runtime.

Host-side test runs are allowed during editing, but they are development diagnostics only. If a result is used for module completion, regression proof, OCR validation, database validation, browser-flow validation, or Capstone assessment evidence, it must be repeated through the container stack.

## Cloud-Dev Official Evidence

From M14 onward, the Azure cloud-dev deployment becomes the official evidence target where practical. Local Docker remains the pre-cloud safety gate, but completion, MVP iteration, cloud-readiness, user-facing workflow, and assessment evidence should be repeated against the live cloud-dev Stats deployment.

Cloud-dev tests must still use approved project fixtures from `tests/input`. Evidence should record the cloud endpoint, tested fixture names, redacted response summaries, processing status, screenshots where useful, and any Azure runtime observations that are safe to disclose. Evidence must never include real secrets, full connection strings, full OCR text, passwords, subscription identifiers that are not intentionally documented, or unredacted sensitive financial content.

Practical cloud-dev targets include live `/health`, `/Login`, and `/Upload` checks, upload of approved `tests/input` fixtures through the cloud Stats Web URL, redacted API/result summaries, Container App revision status, redacted logs, and Azure SQL connectivity or migration status when the tested workflow depends on persistence.

The detailed container-first policy is defined in:

- `docs/M13-container-first-testing-policy.md`
- `tests/scripts/README.md`

## Claude And Codex Collaboration Rule

When Claude and Codex are both involved, both agents must follow the same testing loop:

- Work from the accepted module spec and roadmap.
- Do not introduce new architecture or testing conventions without asking the user first.
- Add or update tests as part of the change.
- Prefer explicit test commands over vague statements such as "should work".
- State whether tests were run on host only or through the M13 container.
- Treat host-only results after M13 as provisional until repeated in the container.
- Keep evidence under `tests/results`.
- Keep reusable runners under `tests/scripts`.
- Keep real fixture files under `tests/input`, with sensitive source files uncommitted.
- Do not present synthetic fixture runs as module completion, regression, or assessment evidence.

## E2E Expectation

Because Stats combines a frontend, Python APIs, database-backed identity, file ingestion, OCR/Tesseract, and downstream extraction modules, E2E/browser checks are required for user-facing workflows.

At minimum, E2E evidence should cover:

- Login and authenticated access.
- Upload page access.
- File validation.
- File ingestion.
- Document parsing through M5.
- OCR/Tesseract path when the input requires OCR.
- Visible result or JSON output shown through Stats Web.

Unit tests are still required, but they are not sufficient for workflows where client, server, database, OCR, and container runtime are tightly coupled.

## Evidence Standard

Evidence must be generated during module work, not after the project is otherwise complete.

Evidence should include:

- Raw terminal output.
- JSON result summaries for APIs and workflows.
- Screenshots for browser-visible behavior where applicable.
- Manual checklists for review-only expectations.
- Notes about any test not run and why.

Evidence summaries must avoid copying full sensitive financial text from real documents. Use redacted previews, counts, metadata, and result summaries instead.

Testing evidence must also follow the privacy, security, and data-governance policy in `docs/privacy-security-data-governance-policy.md`.

## WIP Report Rationale

This policy formalizes the testing practice that emerged during the project: module work is accepted through specification, implementation, test execution, and evidence capture as a single loop. It also reflects the shift to M13 container-first testing, where the same runtime used for OCR and service composition becomes the source of truth for future acceptance evidence.

<!-- M0 Foundation / M13 Containerization End -->
