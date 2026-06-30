<!-- M15 - Evaluation and Assessment Evidence Start -->
<!-- Defines the external DSR evaluation pack used to assess Stats against the proposal criteria and literature-aligned targets. -->

# M15 Whole-Project Evaluation and Assessment Specification

## Purpose

M15 is the final **logical whole-project evaluation and assessment evidence pack** for the capstone artefact. Its purpose is to prove whether the Stats prototype addresses the research problem described in the proposal: converting unstructured household financial documents into structured, validated, dashboard-ready financial records with less manual effort.

M15 is **not a buildable module and is not part of the Stats app**. It does not add product features, runtime APIs, database tables, pages, cloud resources, or user workflows. Stats is the artefact being evaluated. M15 is the external measurement layer that collects evidence across the whole project, calculates metrics, compares results against the proposal's target outcomes, and records whether each research question has been answered.

M15 must not create or modify a Stats Web page, API endpoint, database schema, cloud resource, or user workflow. Any Stats behaviour that needs to change remains owned by the relevant Stats component; M15 only measures the result.

## Owner Folders

```text
docs/evidence/
tests/results/M15-EvaluationAssessment/
tests/scripts/M15-EvaluationAssessment/
```

## Proposal Alignment

The proposal defines M15's evaluation purpose through the Design Science Research evaluation step. Evaluation must show the usefulness, reliability, and problem-solving capability of the artefact.

The proposal defines a two-phase evaluation:

| Phase | Purpose |
| --- | --- |
| Technical validation | Test each part of the system individually: upload, email ingestion, OCR, parsing, validation, storage, authentication, and dashboard display. |
| End-to-end evaluation | Test the full workflow from document ingestion to dashboard reporting. |

The proposal also requires a sample set of household financial documents including bank statements, receipts, invoices, utility bills, and email attachments. Each evaluated document needs a manually prepared ground-truth record so the system output can be compared with the true expected values.

## Success Measurement Model

The detailed success measurement plan is `docs/M15-project-success-measurement-plan.md`. That plan is the operational bridge between the proposal, WIP report, project evidence, and final M15 report.

M15 success is measured at the whole-project level, not by checking whether every roadmap item exists. The final judgement must answer:

- RQ1: whether extraction is accurate and reliable enough for the approved document set.
- RQ2: whether validation, duplicate checks, review gates, and data cleaning improve the extracted records before storage.
- RQ3: whether the workflow and dashboard/reporting layer support household financial review with accurate summaries and usable performance.

M15 must report each metric as `met`, `partially met`, `not met`, `not measurable`, or `deferred`. It must also distinguish MVP evidence from post-MVP defects and future improvements.

## Assessment 3 Alignment

The final M15 evidence must align with the Assessment 3 final research project report and presentation brief. This means the evidence pack must support:

- LO1: critical literature gap analysis using Assessment 1 and Assessment 2 literature foundations.
- LO3: research-informed assessment of the importance and potential applications of software engineering principles used in Stats.
- LO4: ethical and cultural issues, with implications and relevant literature.
- LO5: presentation-ready communication for academic and professional software engineering audiences.

The success measurement plan defines the Assessment 3 outputs required for the final report: literature gap to evidence matrix, software engineering principles assessment table, project success target/result table, RQ answer table, ethical/cultural implications matrix, presentation summary slide outline, evidence figure list, and limitations/future work register.

## Assessment 1 Feedback Integration

M15 must address the Assessment 1 feedback before final submission. The final evaluation report should not only calculate metrics; it should explain how the evidence, tables, visuals, and methodology connect to the research findings.

| Feedback Theme | M15 Requirement |
| --- | --- |
| Table discussion and referencing | Every final evaluation table must be introduced, discussed in the surrounding text, and referenced by table number or title. The report must explain what the table shows and how it supports the finding. |
| Literature synthesis | The literature-aligned target notes must synthesize trends, contrasting perspectives, and opportunities for future research rather than listing sources in isolation. |
| Broader significance | The final discussion must connect the household finance problem to practical, industry, and societal implications where evidence supports the claim. |
| Research-question contribution | The RQ answer table must state the practical contribution to household financial document processing and, where appropriate, the contribution to theory, practice, or policy. |
| Methodology clarity | The report must explicitly state whether the project uses qualitative, quantitative, or mixed-methods methodology and justify why that approach fits the research objectives. |
| Methodological limitations | The report must discuss limitations and mitigation strategies, including sample size, document variety, OCR quality, local/private data constraints, usability sample limits, and prototype scope. |
| Product visualisation | The final evidence pack must include the actual Stats Reports page as the final product visual, supported by screenshots showing how users interact with upload, review, and reporting functions. |
| Metric rationale | Each selected evaluation metric must include a short rationale linking it to RQ1, RQ2, RQ3, the proposal target, or the literature-aligned evidence. |
| Findings and future improvements | The final report must explain how the findings inform future improvements or broader applications, including scalability, long-term sustainability, deployment considerations, and real-world use. |
| Presentation reflection | Presentation evidence, if included, should use slides as prompts and summarize the project in the author's own words rather than reproducing scripted notes. |

The methodology should be documented as **mixed-methods** unless the final research report intentionally revises the design. The quantitative component measures accuracy, completeness, reliability, processing time, success rates, dashboard performance, summary accuracy, and access-control pass/fail outcomes. The qualitative component captures usability feedback, interpretation of dashboard clarity, methodological limitations, and reflection on practical usefulness. This hybrid approach fits the project because the artefact must be measured numerically while also being assessed for usefulness in a household financial-review context.

## Research Questions Covered

| Research Question | M15 Evaluation Focus |
| --- | --- |
| RQ1: OCR and parsing accuracy for key financial fields | Field-level extraction accuracy, OCR reliability, transaction/field completeness. |
| RQ2: Validation and cleaning effectiveness | Completeness, duplicate handling, invalid/incomplete record detection, data consistency. |
| RQ3: Dashboard usefulness, scalability, performance, and summary accuracy | Workflow completion, dashboard response/load behavior, displayed summary accuracy, usability. |

## Evaluation Criteria and Proposal Targets

M15 uses the proposal's target outcomes as the acceptance benchmark.

| Evaluation Area | Metric / Method | Target Outcome |
| --- | --- | --- |
| Data extraction accuracy | Correctly extracted fields such as date, description, merchant/biller, amount, and category divided by total expected fields | At least 85% field-level accuracy |
| Data completeness | Records with all required fields divided by total processed records | At least 90% complete records |
| OCR processing reliability | Documents processed without OCR failure divided by total documents processed | At least 90% successful OCR processing |
| Processing efficiency | Automated processing time compared with manual processing time | At least 50% faster than manual entry |
| Email ingestion effectiveness | Valid email attachments retrieved and queued divided by total valid attachments available | At least 90% successful retrieval |
| Duplicate handling | Duplicate documents correctly identified divided by total duplicate documents in the test set | At least 90% duplicate detection success |
| End-to-end integration | Documents completed from ingestion to dashboard display divided by total documents tested | At least 90% successful workflow completion |
| Validation effectiveness | Invalid or incomplete records correctly detected divided by total invalid/incomplete records in the test set | At least 90% detection of invalid or incomplete records |
| Usability | User feedback checklist or short usability questionnaire | Majority positive feedback on upload, review, and dashboard clarity |
| Security and access control | Pass/fail login, restricted access, and document visibility tests | 100% pass for basic access-control test cases |
| Dashboard performance | Dashboard loading time and response time | Loads within acceptable time for the sample dataset |
| Dashboard scalability | Response time comparison across increasing data volumes | Remains usable as the dataset increases |
| Dashboard summary accuracy | Correct dashboard summary values divided by total expected dashboard summary values | At least 90% accuracy in displayed summaries |

## Literature and Research-Paper Alignment

The proposal links the evaluation approach to document-processing and Design Science Research literature. M15 should therefore keep a research target matrix for any paper-specific or literature-derived benchmark used in the final report.

The research target matrix supplements the proposal targets; it does not replace them. If a paper gives a metric that can be compared directly, M15 records it. If the paper context is different from the Stats household-finance dataset, M15 records the target as contextual or not directly comparable.

| Field | Required | Description |
| --- | --- | --- |
| `target_id` | Yes | Stable ID such as `proposal-extraction-accuracy` or `paper-ocr-001`. |
| `source` | Yes | Proposal, literature review, or citation key. |
| `metric_name` | Yes | Accuracy, completeness, OCR reliability, processing time, F1, recall, usability, or another named metric. |
| `target_value` | Yes | Numeric threshold, range, qualitative target, or not specified. |
| `unit` | Yes | Percent, seconds/document, pass/fail, qualitative, or not specified. |
| `stats_metric_mapping` | Yes | Stats metric used for comparison. |
| `comparison_rule` | Yes | Greater-than, less-than, equal/pass-fail, within tolerance, qualitative, or not comparable. |
| `notes` | No | Short paraphrased caveats without long copyrighted excerpts. |

## Inputs and Outputs

| Direction | Contract or Input | Description |
| --- | --- | --- |
| Input | Evaluation dataset manifest | Redacted manifest for sample/anonymized/synthetic household financial documents. |
| Input | Ground-truth answer key | Manually prepared expected labels, fields, transactions, validation findings, dashboard totals, duplicate cases, and timing baselines. |
| Input | Proposal target matrix | Proposal-defined targets and any literature-aligned targets selected for comparison. |
| Input | Stats technical evidence | Redacted component, integration, container, cloud-dev, browser, database, dashboard, and usability evidence produced while testing Stats. |
| Input | WIP risk and gap notes | Current known risks such as duplicate-row regression, cloud mailbox evidence, Blob durability, challenging OCR cases, and post-MVP defects. |
| Output | Evaluation assessment report | Markdown report stating whether each proposal target was met, partially met, missed, or not measurable. |
| Output | Metrics JSON | Machine-readable aggregate and per-fixture results. |
| Output | Research-question answer table | Evidence-backed answer for RQ1, RQ2, and RQ3. |
| Output | Evidence index | Mapping from each assessment claim to its supporting artefact. |
| Output | Gap register | Missing evidence, insufficient dataset coverage, failed checks, not-comparable paper targets, and rerun actions. |

## Evaluation Dataset Contract

The evaluation dataset is defined by metadata and ground truth, not by committed private documents.

| Field | Required | Description |
| --- | --- | --- |
| `fixture_id` | Yes | Stable opaque ID such as `fixture-001`; must not reveal personal or account details. |
| `source_filename_redacted` | Yes | Redacted display name or hash-derived alias. |
| `fixture_type` | Yes | Synthetic, anonymized, or local-private. |
| `document_family` | Yes | Bank statement, receipt, invoice, utility bill, email attachment, or unknown. |
| `expected_required_fields` | No | Required fields such as date, amount, description, direction, merchant, biller, total, category, or due date. |
| `expected_transaction_count` | No | Expected count or range for transaction rows. |
| `expected_validation_findings` | No | Missing, invalid, inconsistent, duplicate, or incomplete records that should be detected. |
| `expected_dashboard_values` | No | Expected totals, counts, categories, balances, or summaries. |
| `manual_processing_seconds` | No | Baseline manual processing time for processing-efficiency comparison. |
| `privacy_classification` | Yes | Redacted, anonymized, synthetic, or local-private. |

Real source files stay in `tests/input/` or another configured ignored local fixture directory. Reports use fixture IDs and redacted aliases only.

## Formulas

M15 uses the formulas stated in the proposal:

| Metric | Formula |
| --- | --- |
| Extraction accuracy | `(Correctly extracted fields / Total expected fields) x 100` |
| Data completeness | `(Records with all required fields / Total processed records) x 100` |
| OCR reliability | `(Documents processed without OCR failure / Total documents processed) x 100` |
| Time reduction | `((Average manual processing time - Average automated processing time) / Average manual processing time) x 100` |
| Email ingestion success | `(Valid attachments retrieved and queued / Total valid attachments available) x 100` |
| Workflow success | `(Documents completed from ingestion to dashboard display / Total documents tested) x 100` |
| Validation detection rate | `(Invalid or incomplete records correctly detected / Total invalid or incomplete records in the test set) x 100` |
| Duplicate detection success | `(Duplicate documents correctly identified / Total duplicate documents in the test set) x 100` |
| Dashboard response time increase | `((Response time at larger dataset - Response time at baseline dataset) / Baseline response time) x 100` |
| Dashboard summary accuracy | `(Correct dashboard summary values / Total expected dashboard summary values) x 100` |

## Report Structure

The final M15 report must contain:

1. Evaluation setup: run date, Stats commit/version when available, environment, dataset size, and commands used.
2. Dataset summary: document families, fixture privacy classification, duplicate and invalid-record cases.
3. Technical validation results: upload, email ingestion, OCR, parsing, validation, storage, authentication, and dashboard display.
4. End-to-end workflow results: ingestion-to-dashboard completion.
5. Proposal target comparison table: target, actual result, status, evidence reference, and notes.
6. Research-question answer table for RQ1, RQ2, and RQ3.
7. Formula-based metric tables and per-fixture comparison rows.
8. Usability checklist or questionnaire summary.
9. Evidence index linking every assessment claim to raw output, JSON, screenshot, log, or checklist artefacts.
10. Limitations, not-measurable items, and gap register.
11. Privacy, security, and copyright checklist.
12. Methodology statement identifying the mixed-methods approach or the intentionally revised alternative.
13. Actual Stats Reports page screenshot, plus upload/review/reporting screenshots where needed to show the final user interaction.
14. Discussion text for every table, including what the table means and how it supports the findings.
15. Future-improvement discussion covering scalability, sustainability, deployment, broader application, and any research opportunities found during evaluation.
16. Success verdict table using `met`, `partially met`, `not met`, `not measurable`, and `deferred`.
17. Assessment 3 alignment section covering LO1, LO3, LO4, and LO5 evidence.

## Privacy, Security, and Copyright Rules

- Do not include long excerpts from research papers; use citation keys and short paraphrased target descriptions.
- Do not include full OCR text, full transaction descriptions, full account numbers, card numbers, addresses, emails, tokens, database connection strings, or cloud secret values.
- Do not commit real financial documents or local-private fixtures.
- Use redacted aliases and fixture IDs in reports.
- Screenshots must avoid secrets and raw private financial details.
- Access-control evidence must prove restricted access without exposing password hashes, tokens, or private records.

## Dependencies and Configuration

- Runtime: external evaluation runner over Stats outputs.
- Stats role: artefact/system under evaluation.
- Official contract test command: `pytest tests/integration/test_m15_evaluation_evidence_contract.py`.
- Planned runner command: `tests\scripts\M15-EvaluationAssessment\run_m15_evaluation_assessment.ps1`.
- Planned evidence root: `tests/results/M15-EvaluationAssessment/`.
- Configuration sample: proposal target matrix, evaluation dataset manifest, and ground-truth answer key with safe placeholders.
- Real-data input variables: use `STATS_TESTDATA_DIR` or ignored local override files when private fixtures are needed.
- Hardcoded runtime values allowed in source: none except stable relative paths, proposal metric names, and target thresholds documented here.

## Tasks

1. Keep M15 outside the Stats app and outside the buildable-module structure while preserving its whole-project evaluation and assessment purpose.
2. Maintain the project success measurement plan.
3. Define the proposal target matrix and paper/literature alignment matrix.
4. Define the redacted evaluation dataset and ground-truth answer-key format.
5. Add a contract test that verifies the evaluation/assessment boundary and proposal targets.
6. Incorporate Assessment 1 feedback into the final report checklist.
7. Create safe templates for target matrix, dataset manifest, and answer key.
8. Implement an optional runner that reads Stats outputs and computes proposal metrics.
9. Generate final assessment evidence under `tests/results/M15-EvaluationAssessment/`.

## Test Plan

| Check | Level | Evidence |
| --- | --- | --- |
| M15 is documented as outside the Stats app and buildable-module structure but still owns final whole-project evaluation and assessment | Integration contract | `pytest tests/integration/test_m15_evaluation_evidence_contract.py` |
| Proposal targets are documented | Integration contract | Contract test output |
| Dataset and ground-truth formats are documented | Integration contract | Contract test output |
| Formula-based metrics are documented | Integration contract | Contract test output |
| Research-question answer table is required | Integration contract | Contract test output |
| Whole-project success measurement plan exists | Integration contract | Contract test output |
| Assessment 3 final report alignment is documented | Integration contract | Contract test output |
| Assessment 1 feedback is represented in the final report contract | Integration contract | Contract test output |
| Privacy/security/copyright rules are documented | Integration contract | Contract test output |
| Final evaluation report can be generated from Stats outputs | Evidence runner | `tests/results/M15-EvaluationAssessment/` report and metrics JSON |

## Acceptance Criteria

M15 is complete when:

- The spec clearly states M15 is not part of the Stats app and not a buildable module, but is the final DSR whole-project evaluation and assessment evidence pack.
- The project success measurement plan exists and separates met, partially met, not met, not measurable, and deferred items.
- The final evidence pack includes Assessment 3 alignment for literature review, research-informed software engineering assessment, ethical/cultural implications, and presentation communication.
- The proposal targets are represented in the target matrix.
- Assessment 1 feedback is addressed through table discussion, methodology clarity, product visualisation, metric rationale, limitations/mitigations, broader impact, and future-improvement discussion.
- The evaluation dataset manifest and ground-truth answer key exist with redacted identifiers.
- The comparison report calculates Stats results against each proposal target where measurable.
- RQ1, RQ2, and RQ3 are answered using evidence.
- Not-measurable targets, failed targets, weak evidence, and dataset limitations are explicitly listed.
- Final artefacts are stored under `tests/results/M15-EvaluationAssessment/`.
- No copyrighted paper excerpts, private documents, unredacted financial data, or secrets are committed.

## Deferred Items

- Filling any paper-specific target matrix entries depends on the final selected research papers and literature-review notes.
- Broader benchmark claims require a larger curated anonymized dataset and are outside the initial capstone evidence pack.
- Live cloud-dev timing should be included only when it is stable enough to compare against the processing-efficiency target.

<!-- M15 - Evaluation and Assessment Evidence End -->
