<!-- M15 - Evaluation and Assessment Evidence Start -->
<!-- Documents files created or modified for M15 evaluation and assessment evidence. -->

# M15 Evaluation and Assessment Evidence File Inventory

## Summary

This document lists the files created or modified for **M15 Evaluation and Assessment Evidence**. M15 is not part of the Stats app and is not a buildable module. It is the external DSR whole-project evaluation pack used to assess Stats against the proposal criteria, research questions, and literature-aligned targets.

Current status: **contract and documentation added**. Evidence runner implementation and final run artefacts are pending.

## Specification and Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M15-evaluation-assessment-spec.md` | Created / Updated | Defines M15 as an external whole-project evaluation and assessment evidence pack, not a Stats app feature or buildable module. Documents proposal targets, research-question coverage, literature alignment, Assessment 1 feedback integration, dataset/ground-truth contract, formulas, report structure, privacy/security/copyright rules, tasks, test plan, and acceptance criteria. |
| `docs/M15-project-success-measurement-plan.md` | Created / Updated | Defines how project success should be measured across RQ1, RQ2, RQ3, proposal targets, Assessment 3 LO1/LO3/LO4/LO5 alignment, cross-cutting criteria, WIP-derived risks, evidence preconditions, verdict statuses, and final reporting. |
| `docs/M15-evaluation-evidence-file-inventory.md` | Created | This file. Tracks M15 documentation and contract-test assets. |
| `docs/evidence/README.md` | Updated | Adds M15 as the external evaluation and assessment lane for measuring Stats against proposal criteria and literature-aligned targets. |

## Integration Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/integration/test_m15_evaluation_evidence_contract.py` | Created / Updated | Verifies the M15 spec and inventory exist, declares that M15 is outside the Stats app and buildable-module structure while preserving the final whole-project evaluation/assessment purpose, requires proposal targets, formulas, research-question coverage, Assessment 1 feedback integration, redacted dataset/ground-truth language, and privacy/security/copyright rules. |

## Planned Evidence Assets

| File or Folder | Change Type | Description |
| --- | --- | --- |
| `tests/scripts/M15-EvaluationAssessment/` | Planned | Future M15 evaluation runner and helper scripts. |
| `tests/results/M15-EvaluationAssessment/` | Planned | Future target matrix, final assessment report, metrics JSON, raw output, evidence index, research-question answer table, and gap register. |
| `tests/results/M15-EvaluationAssessment/evaluation-assessment-<date>.md` | Planned | Human-readable assessment of Stats against proposal targets. |
| `tests/results/M15-EvaluationAssessment/evaluation-metrics-<date>.json` | Planned | Machine-readable metric output and per-fixture comparison results. |
| `tests/results/M15-EvaluationAssessment/proposal-target-comparison-<date>.md` | Planned | Proposal target to Stats result comparison table. |
| `tests/results/M15-EvaluationAssessment/gap-register-<date>.md` | Planned | Missing, blocked, skipped, not-measurable, or weak evidence register. |

## Verification

Run:

```powershell
pytest tests/integration/test_m15_evaluation_evidence_contract.py
```

Expected result:

```text
14 passed
```

<!-- M15 - Evaluation and Assessment Evidence End -->
