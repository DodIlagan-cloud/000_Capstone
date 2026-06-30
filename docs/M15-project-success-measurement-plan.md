<!-- M15 - Project Success Measurement Plan Start -->
<!-- Defines how the whole Stats project should be measured for final evaluation. -->

# M15 Project Success Measurement Plan

## Purpose

This plan defines how to measure whether the Stats project is successful. M15 is not a Stats app feature and not a buildable module. It is the logical whole-project evaluation layer that turns the proposal, WIP report, research questions, technical evidence, and final test outputs into an assessment-ready conclusion.

The success question is:

> Did the Stats artefact solve the approved capstone problem well enough, on the approved evaluation dataset, to show that unstructured household financial documents can be converted into structured, validated, reportable financial records with less manual effort?

## Evaluation Sources

M15 measures success using:

- Assessment 1 research proposal evaluation plan and target outcomes.
- Assessment 2 WIP report refined research design, current progress, risks, and pending work.
- Assessment 3 final research project report and presentation brief, including LO1, LO3, LO4, and LO5 rubric requirements.
- Local, container, cloud-dev, database, browser, and dashboard evidence already produced by the project.
- Final M15 evaluation runs over a redacted/anonymized/synthetic fixture set.
- Manually prepared ground-truth records for each evaluation fixture.

## Assessment 3 Final Report Alignment

Assessment 3 is worth 40% of the course and requires a final research report plus presentation file and recording. M15 must therefore create evidence that can be used directly in the final report and presentation, not only internal engineering notes.

| Assessment 3 Area | Weight | M15 Alignment |
| --- | --- | --- |
| LO1 Literature Review | 20% | The final evaluation must connect results back to the literature gap: personal finance tools assume structured data, while OCR/document extraction research often stops before household dashboard use. M15 should provide a concise literature-to-evidence synthesis. |
| LO3 Research-Informed Report | 40% | M15 must supply the main evidence base for analysing and assessing the importance and potential applications of the software engineering principles used in Stats: modular boundaries, API contracts, container-first testing, cloud deployment, persistence, reporting, privacy controls, and evidence-driven development. |
| LO4 Ethical and Cultural Issues | 20% | M15 must include privacy, security, cultural, linguistic, accessibility, responsible AI/classification, data-governance, and cloud/resource limitations as evaluation findings, not just background discussion. |
| LO5 Presentation | 20% | M15 must produce presentation-ready summary material: target/result table, RQ1/RQ2/RQ3 answer table, architecture/evidence visuals, key screenshots, limitations, and final success conclusion. |

Assessment 3 also requires clear identification, professional formatting, consistent citations, proofreading, and relevant diagrams, tables, or figures. The final M15 evidence pack should therefore include report-ready tables with captions, a figure/screenshot list, and short explanatory text for each visual or table.

## Assessment 3 Evidence Outputs

M15 should produce these outputs for final report assembly:

| Output | Supports |
| --- | --- |
| Literature gap to evidence matrix | LO1 |
| Software engineering principles assessment table | LO3 |
| Project success target/result table | LO3 |
| RQ1/RQ2/RQ3 answer table | LO3 |
| Ethical and cultural implications matrix | LO4 |
| Privacy/security/governance checklist | LO4 |
| Presentation summary slide outline | LO5 |
| Evidence figure list and screenshot captions | LO3 and LO5 |
| Limitations and future work register | LO3 and LO4 |

## Success Verdicts

Each metric and research question should be reported using one of these statuses:

| Status | Meaning |
| --- | --- |
| Met | The measured result reaches the proposal target with acceptable evidence. |
| Partially met | The result is directionally successful but misses a threshold, has limited fixture coverage, or only passes in one runtime path. |
| Not met | The result is measured and does not satisfy the target. |
| Not measurable | The required evidence, ground truth, or fixture coverage is missing. |
| Deferred | The item is valid future work but outside the final MVP success claim. |

## Evidence Preconditions

Before final scoring, M15 needs:

| Evidence Item | Purpose |
| --- | --- |
| Evaluation dataset manifest | Lists fixture IDs, document family, language/currency context, privacy class, and whether timing/dashboard/email/duplicate checks apply. |
| Ground-truth answer key | Stores expected fields, transactions, validation findings, duplicate cases, dashboard values, and manual processing baseline times. |
| Proposal target matrix | Captures each proposal target and formula. |
| Literature alignment notes | Records where research papers support the choice of metrics without overclaiming benchmark equivalence. |
| Evidence index | Maps every claim to raw output, JSON, screenshot, database proof, or checklist evidence. |
| Gap register | Separates missing evidence, failed checks, post-MVP defects, and future enhancements. |

## Research-Question Measurement

### RQ1 - Extraction Success

**Question:** How accurately can OCR and parsing extract key financial fields from heterogeneous household financial documents?

| Metric | Target | Measurement |
| --- | --- | --- |
| Field-level extraction accuracy | At least 85% | Correctly extracted expected fields divided by total expected fields. |
| OCR reliability | At least 90% | Documents processed without OCR failure divided by total documents processed. |
| Processing efficiency | At least 50% faster than manual entry | Manual baseline time compared with automated document-to-structured-output time. |
| Document-family coverage | Reported, not pass/fail alone | Results split by statement, receipt, invoice, bill, and email attachment. |
| Cultural/language/currency coverage | Reported as limitation unless deliberately tested | Results split where possible by PHP/NZD/AUD/USD, mixed-language, non-Latin, or unusual layouts. |

**Evidence:** M5 parse output, M7 extraction output, timing logs, OCR findings, redacted fixture comparisons, screenshots only when useful.

### RQ2 - Validation and Data-Quality Success

**Question:** How effectively do validation, duplicate checks, review gates, and data-cleaning rules improve extracted records before storage?

| Metric | Target | Measurement |
| --- | --- | --- |
| Data completeness | At least 90% | Records with all required fields divided by total processed records. |
| Validation detection rate | At least 90% | Invalid/incomplete records correctly detected divided by invalid/incomplete ground-truth cases. |
| Duplicate detection success | At least 90% | Duplicate documents or attachments correctly identified divided by total duplicate cases. |
| Save readiness | Reported | Records that pass review and can be saved without unresolved critical findings. |
| Classification governance quality | Reported | Unknown labels, pending suggestions, approved suggestions, and review impact counts. |

**Evidence:** M8 validation output, M9 persistence proof, duplicate regression evidence, review-state screenshots, recognition governance evidence, database query summaries.

### RQ3 - Workflow, Dashboard, and Reporting Success

**Question:** How well can the prototype support household financial review through dashboards and reports?

| Metric | Target | Measurement |
| --- | --- | --- |
| Workflow completion | At least 90% | Documents completed from ingestion to dashboard display divided by tested documents. |
| Dashboard summary accuracy | At least 90% | Correct displayed summary values divided by expected dashboard summary values. |
| Dashboard performance | Acceptable time for sample dataset | Load and response times for dashboard/report pages. |
| Dashboard scalability | Remains usable as data volume increases | Response-time increase from baseline to larger dataset. |
| Reporting usefulness | Qualitative with evidence | Screenshots and discussion showing document status, financial summaries, classification quality, and spending reports are understandable. |

**Evidence:** Stats Web cloud screenshots, M11 reporting evidence, Azure SQL reporting views/read models, Fabric/Power BI semantic model evidence, native Reports/Documents/Home page evidence.

## Cross-Cutting Success Criteria

| Area | Target | Measurement |
| --- | --- | --- |
| Email ingestion | At least 90% valid attachment retrieval and queueing | Valid attachments retrieved and queued divided by total valid attachments available. |
| Blob-backed durability | Evidence required before claiming durable cloud intake | Accepted document and email attachment references persist through the configured storage provider. |
| Access control | 100% basic access-control pass | Unauthenticated access blocked; authenticated users can access their workflow; restricted records are not visible without permission. |
| Privacy and governance | Must pass checklist | No committed secrets, no private financial documents, no full OCR text in evidence, screenshots redacted. |
| Responsible AI/classification | Must be reviewable | AI/rule suggestions remain advisory, confidence-aware, auditable, and reviewed before affecting saved records or reporting labels. |
| Cultural/accessibility coverage | Reported as evidence or limitation | Performance by document family/language/currency/context where available; limitations clearly stated where coverage is weak. |

## Current WIP-Derived Risks to Separate From Success Claims

The WIP report identifies areas that must be separated from final success claims:

- Duplicate document-row regression must be closed or reported as a known gap.
- Cloud mailbox ingestion evidence must be completed or marked not measurable/deferred.
- Blob-backed document and email attachment durability must be validated before claiming durable cloud storage success.
- Challenging photographic receipt OCR should be measured honestly; poor cases should inform improvement recommendations.
- MVP evidence must be distinguished from post-MVP defects and future enhancements.
- Cloud-dev and Fabric/Power BI evidence should be included only where the environment is available and the result is current.

## Final Report Structure

The final M15 report should use this order:

1. Evaluation objective and methodology.
2. Literature gap to evaluation mapping.
3. Dataset and ground-truth summary.
4. Proposal target matrix.
5. RQ1 extraction results.
6. RQ2 validation and data-quality results.
7. RQ3 workflow, dashboard, and reporting results.
8. Software engineering principles assessment.
9. Ethical and cultural issues assessment.
10. Cross-cutting results: email, Blob durability, access control, privacy, governance, cultural/accessibility coverage.
11. Target comparison table with Met/Partially met/Not met/Not measurable/Deferred status.
12. Evidence index and figure/table list.
13. Presentation summary and audience-ready findings.
14. Limitations, risks, and future improvements.
15. Final success conclusion.

## Final Success Statement Template

Use this template for the final conclusion:

```text
The Stats artefact [met / partially met / did not meet] the approved project success criteria.
It [did / did not] demonstrate an end-to-end document-first workflow from intake through OCR,
extraction, validation, persistence, and reporting. RQ1 was [status] because [evidence].
RQ2 was [status] because [evidence]. RQ3 was [status] because [evidence].
The main limitations are [limitations]. The next improvements are [improvements].
```

<!-- M15 - Project Success Measurement Plan End -->
