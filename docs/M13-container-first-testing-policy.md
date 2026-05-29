<!-- M13 - Containerization Start -->
<!-- Defines the project-wide container-first testing policy from M13 onward. -->

# M13 Container-First Testing Policy

## Policy

From M13 onward, the Stats project is **container-first** for all official module testing.

All acceptance, regression, evidence, runtime, database, OCR, browser-flow, and cross-module tests must execute through the M13 Stats container runtime. This applies to completed modules, current module work, and all future modules.

Host-side commands are development diagnostics only. They must not be used as the official proof that a module is complete after M13 is active.

## DevOps Principle

This policy follows the DevOps/CI-CD principle that the project should build, test, and eventually deploy the same portable runtime image. The local developer machine, future GitHub Actions runner, and future cloud host should all validate the Stats app through the container rather than through machine-specific installations.

```text
code change
-> build Stats container
-> run module and regression tests inside the container
-> collect evidence
-> commit / pull request review
-> future CI/CD deploys the validated container image
```

## Required Official Test Path

| Test Type | Required Execution |
| --- | --- |
| Module acceptance | Inside the Stats container |
| Module regression | Inside the Stats container |
| Cross-module workflow | Inside the Stats container |
| OCR/Tesseract verification | Inside the Stats container |
| Database-backed verification | Inside the Stats container and Compose database |
| Browser/app-flow evidence | Against the container-exposed Stats Web entry point |
| Capstone assessment evidence | Container-generated evidence only |

## Development Diagnostics

Developers may still run host-side commands while editing, but those runs are diagnostic only. Examples include static inspection, formatter checks, and quick local reproductions. Any diagnostic result that matters to module acceptance must be repeated through the container before it is recorded as official evidence.

## Standard Future Module Flow

Every future module should follow this order:

1. Create the analysis/specification document.
2. Create the file inventory.
3. Create the activity flow when the module has meaningful workflow behavior.
4. Implement the module.
5. Add or update container packaging/runtime wiring.
6. Run official tests through the Stats container.
7. Store evidence under `tests/results`.
8. Store reusable runners under `tests/scripts`.

## Artefact Rules

- Official evidence belongs under `tests/results`.
- Reusable test scripts belong under `tests/scripts`.
- Approved fixture files belong under `tests/input`.
- Evidence summaries must avoid copying full sensitive financial text.
- Host-run artefacts created before this policy are historical only unless superseded by container-run evidence.
- Major testing/runtime policy changes must have a dedicated file inventory before commit.

<!-- M13 End -->
