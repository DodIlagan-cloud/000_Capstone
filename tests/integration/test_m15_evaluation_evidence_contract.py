# M15 - Evaluation and Assessment Evidence Start
# Verifies the M15 external evaluation and assessment evidence contract.

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SPEC = REPO_ROOT / "docs" / "M15-evaluation-assessment-spec.md"
FILE_INVENTORY = REPO_ROOT / "docs" / "M15-evaluation-evidence-file-inventory.md"
EVIDENCE_README = REPO_ROOT / "docs" / "evidence" / "README.md"
SUCCESS_PLAN = REPO_ROOT / "docs" / "M15-project-success-measurement-plan.md"
def read(path):
    return path.read_text(encoding="utf-8")


def test_m15_spec_exists_and_is_outside_stats_app():
    assert SPEC.exists(), f"M15 spec not found at {SPEC}"
    content = read(SPEC)
    assert "M15 Whole-Project Evaluation and Assessment" in content
    assert "not part of the Stats app" in content
    assert "not a buildable module" in content
    assert "logical whole-project evaluation" in content
    assert "Stats is the artefact being evaluated" in content
    assert "does not add product features" in content
    assert "Design Science Research" in content


def test_m15_file_inventory_exists():
    assert FILE_INVENTORY.exists(), f"M15 file inventory not found at {FILE_INVENTORY}"
    content = read(FILE_INVENTORY)
    assert "M15 Evaluation and Assessment Evidence File Inventory" in content
    assert "tests/integration/test_m15_evaluation_evidence_contract.py" in content


def test_m15_success_measurement_plan_exists():
    assert SUCCESS_PLAN.exists(), f"M15 success measurement plan not found at {SUCCESS_PLAN}"
    content = read(SUCCESS_PLAN)
    required_terms = [
        "Did the Stats artefact solve the approved capstone problem",
        "Met",
        "Partially met",
        "Not met",
        "Not measurable",
        "Deferred",
        "RQ1 - Extraction Success",
        "RQ2 - Validation and Data-Quality Success",
        "RQ3 - Workflow, Dashboard, and Reporting Success",
        "Current WIP-Derived Risks",
    ]
    for term in required_terms:
        assert term in content, f"M15 success plan must include {term}"


def test_m15_aligns_to_assessment_3_final_report():
    spec = read(SPEC)
    plan = read(SUCCESS_PLAN)
    required_terms = [
        "Assessment 3 Alignment",
        "LO1",
        "LO3",
        "LO4",
        "LO5",
        "Literature gap to evidence matrix",
        "Software engineering principles assessment table",
        "Ethical and cultural implications matrix",
        "Presentation summary slide outline",
        "Evidence figure list",
    ]
    combined = spec + "\n" + plan
    for term in required_terms:
        assert term in combined, f"M15 must align to Assessment 3 using {term}"


def test_m15_declares_proposal_targets():
    content = read(SPEC)
    required_terms = [
        "At least 85% field-level accuracy",
        "At least 90% complete records",
        "At least 90% successful OCR processing",
        "At least 50% faster than manual entry",
        "At least 90% successful retrieval",
        "At least 90% duplicate detection success",
        "At least 90% successful workflow completion",
        "At least 90% detection of invalid or incomplete records",
        "100% pass for basic access-control test cases",
        "At least 90% accuracy in displayed summaries",
    ]
    for term in required_terms:
        assert term in content, f"M15 proposal targets must mention {term}"


def test_m15_declares_evaluation_owner_folders():
    content = read(SPEC)
    required_paths = [
        "docs/evidence/",
        "tests/results/M15-EvaluationAssessment/",
        "tests/scripts/M15-EvaluationAssessment/",
    ]
    for path in required_paths:
        assert path in content, f"M15 spec must document {path}"


def test_m15_blocks_stats_app_implementation_scope():
    content = read(SPEC)
    forbidden_scope_terms = [
        "Stats Web page",
        "API endpoint",
        "database schema",
        "cloud resource",
        "user workflow",
    ]
    for term in forbidden_scope_terms:
        assert term in content, f"M15 must exclude {term}"


def test_m15_maps_research_questions_to_evaluation():
    content = read(SPEC)
    required_terms = [
        "RQ1",
        "RQ2",
        "RQ3",
        "Research-question answer table",
    ]
    for term in required_terms:
        assert term in content, f"M15 must map research questions using {term}"


def test_m15_integrates_assessment_1_feedback():
    content = read(SPEC)
    required_terms = [
        "Assessment 1 Feedback Integration",
        "Every final evaluation table must be introduced",
        "mixed-methods",
        "qualitative",
        "quantitative",
        "actual Stats Reports page",
        "methodological limitations",
        "Metric rationale",
        "future improvements",
        "broader applications",
    ]
    for term in required_terms:
        assert term in content, f"M15 must integrate Assessment 1 feedback using {term}"


def test_m15_dataset_contract_requires_redaction_and_ground_truth():
    content = read(SPEC)
    required_terms = [
        "fixture_id",
        "source_filename_redacted",
        "fixture_type",
        "document_family",
        "privacy_classification",
        "Ground-truth answer key",
        "expected_dashboard_values",
        "manual_processing_seconds",
    ]
    for term in required_terms:
        assert term in content, f"M15 dataset contract must mention {term}"


def test_m15_defines_proposal_formulas():
    content = read(SPEC)
    required_formulas = [
        "Correctly extracted fields / Total expected fields",
        "Records with all required fields / Total processed records",
        "Documents processed without OCR failure / Total documents processed",
        "Average manual processing time - Average automated processing time",
        "Valid attachments retrieved and queued / Total valid attachments available",
        "Documents completed from ingestion to dashboard display / Total documents tested",
        "Invalid or incomplete records correctly detected / Total invalid or incomplete records",
        "Duplicate documents correctly identified / Total duplicate documents",
        "Correct dashboard summary values / Total expected dashboard summary values",
    ]
    for formula in required_formulas:
        assert formula in content, f"M15 formulas must include {formula}"


def test_m15_privacy_and_copyright_rules_block_sensitive_evidence():
    content = read(SPEC)
    required_terms = [
        "Do not include long excerpts from research papers",
        "full OCR text",
        "full transaction descriptions",
        "account numbers",
        "tokens",
        "database connection strings",
        "cloud secret values",
    ]
    for term in required_terms:
        assert term in content, f"M15 privacy rules must mention {term}"


def test_m15_report_requires_table_discussion_and_visual_evidence():
    content = read(SPEC)
    required_terms = [
        "Discussion text for every table",
        "what the table means",
        "Actual Stats Reports page screenshot",
        "upload/review/reporting screenshots",
        "Future-improvement discussion",
        "scalability",
        "sustainability",
        "deployment",
    ]
    for term in required_terms:
        assert term in content, f"M15 report structure must include {term}"


def test_evidence_readme_points_to_m15():
    content = read(EVIDENCE_README)
    assert "M15 Evaluation and Assessment Evidence" in content
    assert "Design Science Research whole-project evaluation lane" in content
    assert "proposal criteria" in content

# M15 - Evaluation and Assessment Evidence End
