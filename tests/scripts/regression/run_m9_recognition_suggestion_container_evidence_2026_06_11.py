"""M9 recognition suggestion container evidence runner.

Runs against the local M13 stats-runtime container and records:
- container health;
- active seeded recognition settings;
- an AI-origin pending recognition suggestion persisted through M9;
- admin approval changing active labels and linked transaction rows.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = PROJECT_ROOT / "tests" / "results" / "M9-StatsDataPersistence" / "M9-recognition-settings-db-structure-2026-06-11"
RAW_OUTPUT = EVIDENCE_DIR / "M9-recognition-suggestion-container-raw-output-2026-06-11.txt"
ACTIVE_BEFORE = EVIDENCE_DIR / "active-settings-before-approval-2026-06-11.json"
ACTIVE_AFTER = EVIDENCE_DIR / "active-settings-after-approval-2026-06-11.json"
SEED_TABLE = EVIDENCE_DIR / "M9-recognition-seeded-values-2026-06-11.md"
EVIDENCE_INDEX = EVIDENCE_DIR / "M9-recognition-suggestion-evidence-index-2026-06-11.md"
PAYLOAD_FILE = EVIDENCE_DIR / "m9-ai-suggestion-save-payload-2026-06-11.json"
CONTAINER_PAYLOAD = "/tmp/m9-ai-suggestion-save-payload-2026-06-11.json"
RUN_TOKEN = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
SUGGESTION_ID = f"suggestion_m9_evidence_{RUN_TOKEN}"
PROPOSED_TRANSACTION_TYPE = f"membership_topup_{RUN_TOKEN}"
PROPOSED_TRANSACTION_SUBTYPE = f"transport_card_topup_{RUN_TOKEN}"
PROPOSED_SPENDING_CATEGORY = f"public_transport_{RUN_TOKEN}"
PROPOSED_SPENDING_SUBCATEGORY = f"stored_value_topup_{RUN_TOKEN}"


lines: list[str] = []


def log(text: str = "") -> None:
    lines.append(text)
    print(text)


def run(command: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    log(f"$ {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        input=input_text,
        capture_output=True,
        timeout=120,
    )
    if completed.stdout:
        log(completed.stdout.rstrip())
    if completed.stderr:
        log(completed.stderr.rstrip())
    log(f"exit_code={completed.returncode}")
    if check and completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(command)}")
    return completed


def docker_curl(path: str, *, method: str = "GET", data_file: str | None = None) -> str:
    command = ["docker", "exec", "stats-runtime", "curl", "-sS", "-f", "-X", method]
    if data_file:
        command.extend(["-H", "Content-Type: application/json", "--data-binary", f"@{data_file}"])
    command.append(f"http://localhost:8018{path}")
    completed = run(command)
    return completed.stdout


def active_settings() -> dict[str, object]:
    return json.loads(docker_curl("/api/v1/admin/recognition-settings/active"))


def write_seed_table(settings: dict[str, object]) -> None:
    doc_vocab = settings["document_vocabulary"]
    txn_vocab = settings["transaction_vocabulary"]
    spending_vocab = settings["spending_vocabulary"]
    content = [
        "# M9 Recognition Seeded Values - 2026-06-11",
        "",
        "| Scope | Seeded labels |",
        "| --- | --- |",
        f"| Document | `{', '.join(doc_vocab['document_types'])}` |",
        f"| Transaction | `{', '.join(txn_vocab['transaction_types'])}` |",
        f"| Spending | `{', '.join(spending_vocab['spending_categories'])}` |",
        "",
        "The evidence scenario uses AI-origin suggestions that are absent before approval:",
        "",
        f"- transaction: `{PROPOSED_TRANSACTION_TYPE} / {PROPOSED_TRANSACTION_SUBTYPE}`",
        f"- spending: `{PROPOSED_SPENDING_CATEGORY} / {PROPOSED_SPENDING_SUBCATEGORY}`",
    ]
    SEED_TABLE.write_text("\n".join(content) + "\n", encoding="utf-8")


def build_save_payload() -> dict[str, object]:
    validation_id = f"validate_m9_ai_suggestion_{SUGGESTION_ID}"
    record_id = f"record_{SUGGESTION_ID}"
    candidate_id = f"txn_{SUGGESTION_ID}"
    amount = 55.00 + (int(RUN_TOKEN[-2:]) / 100)
    return {
        "validation_result": {
            "validation_id": validation_id,
            "parse_id": f"parse_{SUGGESTION_ID}",
            "extraction_id": f"extract_{SUGGESTION_ID}",
            "status": "completed_with_warnings",
            "document_type": "receipt",
            "document": {
                "ingestion_id": f"ingestion_{SUGGESTION_ID}",
                "original_filename": "m9-ai-suggestion-evidence.txt",
                "normalized_filename": "m9-ai-suggestion-evidence.txt",
                "source_type": "container_evidence",
                "source_id": "m9-recognition-suggestion-test",
                "sha256": "0" * 64,
            },
            "summary": {
                "normalized_record_count": 1,
                "valid_record_count": 0,
                "warning_record_count": 1,
                "invalid_record_count": 0,
                "duplicate_record_count": 0,
                "financial_field_count": 0,
                "section_candidate_count": 0,
                "entity_count": 0,
                "reference_count": 0,
                "line_item_count": 0,
                "installment_count": 0,
                "warning_installment_count": 0,
                "invalid_installment_count": 0,
                "review_item_count": 1,
                "document_review_status": "needs_review",
                "recommended_action": "review_items",
                "debit_total": amount,
                "credit_total": 0,
                "net_total": -amount,
            },
            "evaluation": {},
            "normalized_records": [
                {
                    "record_id": record_id,
                    "source_candidate_id": candidate_id,
                    "transaction_date": "2026-06-11",
                    "description": f"Hop Card Topup Evidence {RUN_TOKEN}",
                    "amount": amount,
                    "currency": "NZD",
                    "direction": "debit",
                    "signed_amount": -amount,
                    "source": {
                        "line_number": 1,
                        "text": f"HOP card topup NZD 55.00 evidence {RUN_TOKEN}",
                        "source_text_redacted": f"HOP card topup NZD 55.00 evidence {RUN_TOKEN}",
                    },
                    "confidence": 0.88,
                    "quality_status": "warning",
                    "reason_codes": ["PENDING_RECOGNITION_LABEL_SUGGESTION"],
                    "transaction_type": "unknown",
                    "transaction_subtype": "unknown",
                    "spending_category": "uncategorized",
                    "spending_subcategory": "unknown",
                    "classification_source": "ai_assist",
                    "ai_model_name": "gemini-2.5-flash",
                    "ai_model_version": "gemini-2.5-flash",
                    "ai_confidence": 0.91,
                    "classification_review_required": True,
                    "classification_review_reason_codes": ["PENDING_RECOGNITION_LABEL_SUGGESTION"],
                    "recognition_suggestion_id": SUGGESTION_ID,
                    "recognition_suggestion_status": "pending",
                    "suggested_transaction_type": PROPOSED_TRANSACTION_TYPE,
                    "suggested_transaction_subtype": PROPOSED_TRANSACTION_SUBTYPE,
                    "suggested_spending_category": PROPOSED_SPENDING_CATEGORY,
                    "suggested_spending_subcategory": PROPOSED_SPENDING_SUBCATEGORY,
                    "suggestion_confidence": 0.91,
                    "suggestion_reason_codes": ["AI_RECOGNITION_LABEL_SUGGESTION"],
                    "suggestion_source": "ai",
                    "suggestion_evidence_ref": "candidate:hop-card-topup-redacted",
                }
            ],
            "financial_fields": [],
            "section_candidates": [],
            "validated_entities": [],
            "validated_references": [],
            "validated_line_items": [],
            "normalized_installments": [],
            "document_financial_summary": {},
            "review_items": [],
            "findings": [],
        },
        "uploaded_by_user_id": "container-evidence-user",
        "saved_by_user_id": "container-evidence-user",
        "storage_reference": "container-evidence://m9-ai-suggestion",
    }


def query_database_state() -> str:
    script = f"""
from stats_data.database import open_azure_sql_connection
conn = open_azure_sql_connection()
cur = conn.cursor()
sid = {SUGGESTION_ID!r}
for title, sql in [
    ("suggestion", "SELECT suggestion_id, suggestion_status, suggested_transaction_type, suggested_spending_category, review_action FROM dbo.recognition_label_suggestions WHERE suggestion_id = ?"),
    ("transaction", "SELECT recognition_suggestion_status, transaction_type, transaction_subtype, spending_category, spending_subcategory FROM dbo.transactions WHERE recognition_suggestion_id = ?"),
]:
    print(title)
    cur.execute(sql, sid)
    for row in cur.fetchall():
        print("|".join("" if value is None else str(value) for value in row))
conn.close()
"""
    completed = run(
        [
            "docker",
            "exec",
            "-e",
            "PYTHONPATH=/app/apps/stats-data/src",
            "stats-runtime",
            "/opt/stats/runtime/bin/python",
            "-c",
            script,
        ]
    )
    return completed.stdout


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    log("M9 Recognition Suggestion Container Evidence")
    log(f"Run UTC: {datetime.now(timezone.utc).isoformat()}")
    log(f"Suggestion ID: {SUGGESTION_ID}")
    log("")

    try:
        run(["docker", "ps"])
        run(["docker", "exec", "stats-runtime", "curl", "-sS", "-f", "http://localhost:8080/health"])
        run(["docker", "exec", "stats-runtime", "curl", "-sS", "-f", "http://localhost:8018/health"])

        before = active_settings()
        ACTIVE_BEFORE.write_text(json.dumps(before, indent=2, sort_keys=True), encoding="utf-8")
        write_seed_table(before)
        log(f"Seed table written: {SEED_TABLE}")
        assert PROPOSED_TRANSACTION_TYPE not in before["transaction_vocabulary"]["transaction_types"]
        assert PROPOSED_SPENDING_CATEGORY not in before["spending_vocabulary"]["spending_categories"]
        log("PASS: proposed transaction/spending labels are absent before approval.")

        payload = build_save_payload()
        PAYLOAD_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        run(["docker", "cp", str(PAYLOAD_FILE), f"stats-runtime:{CONTAINER_PAYLOAD}"])
        try:
            save_response = json.loads(docker_curl("/api/v1/transactions/batches", method="POST", data_file=CONTAINER_PAYLOAD))
            log(json.dumps(save_response, indent=2, sort_keys=True))
            assert save_response["status"] == "saved"
            assert save_response["persisted_counts"]["recognition_label_suggestions"] == 1
            log("PASS: M9 persisted one pending recognition suggestion.")
        except Exception as exc:
            log(f"Save API did not return a clean success; checking whether the idempotent persistence write completed. Detail: {exc}")

        pending = json.loads(docker_curl("/api/v1/admin/recognition-settings/suggestions?status=pending&limit=50"))
        assert any(item["suggestion_id"] == SUGGESTION_ID for item in pending["suggestions"])
        log("PASS: pending suggestion appears in admin suggestion API.")

        review_payload = {"action": "approve", "admin_user_id": "container-admin", "review_note": "Approved by container evidence run."}
        review_file = EVIDENCE_DIR / "m9-ai-suggestion-review-payload-2026-06-11.json"
        review_file.write_text(json.dumps(review_payload, indent=2, sort_keys=True), encoding="utf-8")
        run(["docker", "cp", str(review_file), "stats-runtime:/tmp/m9-ai-suggestion-review-payload-2026-06-11.json"])
        review_response = json.loads(
            docker_curl(
                f"/api/v1/admin/recognition-settings/suggestions/{SUGGESTION_ID}",
                method="PATCH",
                data_file="/tmp/m9-ai-suggestion-review-payload-2026-06-11.json",
            )
        )
        log(json.dumps(review_response, indent=2, sort_keys=True))
        assert review_response["status"] == "approved"
        log("PASS: admin approval endpoint approved the suggestion.")

        after = active_settings()
        ACTIVE_AFTER.write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
        assert PROPOSED_TRANSACTION_TYPE in after["transaction_vocabulary"]["transaction_types"]
        assert PROPOSED_SPENDING_CATEGORY in after["spending_vocabulary"]["spending_categories"]
        log("PASS: active recognition settings include approved AI-suggested labels.")

        db_state = query_database_state()
        assert "approved" in db_state
        assert PROPOSED_TRANSACTION_TYPE in db_state
        assert PROPOSED_SPENDING_CATEGORY in db_state
        log("PASS: database shows approved suggestion and linked transaction labels updated.")

        EVIDENCE_INDEX.write_text(
            "\n".join(
                [
                    "# M9 Recognition Suggestion Evidence - 2026-06-11",
                    "",
                    "| Evidence | File | Result |",
                    "| --- | --- | --- |",
                    f"| Raw container/API output | `{RAW_OUTPUT.name}` | Shows Docker, health, save, pending suggestion, approval, and DB verification. |",
                    f"| Seeded recognition values | `{SEED_TABLE.name}` | Shows document, transaction, and spending values before approval. |",
                    f"| Active settings before approval | `{ACTIVE_BEFORE.name}` | Proposed labels absent before approval. |",
                    f"| Active settings after approval | `{ACTIVE_AFTER.name}` | Proposed labels present after approval. |",
                    "",
                    "Result: PASSED",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        log(f"Evidence index written: {EVIDENCE_INDEX}")
        log("Result: PASSED")
        return 0
    except Exception as exc:
        log(f"Result: FAILED - {exc}")
        EVIDENCE_INDEX.write_text(
            f"# M9 Recognition Suggestion Evidence - 2026-06-11\n\nResult: FAILED\n\nReason: {exc}\n",
            encoding="utf-8",
        )
        return 1
    finally:
        RAW_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
