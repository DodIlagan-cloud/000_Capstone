"""Run content-based classification checks inside stats-runtime.

This script is intentionally container-local: it calls the private M5/M7/M8
module APIs on localhost and compares the same real JPEG bytes under two
different filenames.
"""

from __future__ import annotations

import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


M5_URL = "http://localhost:8015/api/v1/parses"
M7_URL = "http://localhost:8016/api/v1/extractions"
M8_URL = "http://localhost:8017/api/v1/validations"
INPUT_FILE = Path("/app/tests/input/20260603_122232.jpg")
RENAMED_FILE = Path("/tmp/not_a_statement_named_file.jpg")


def main() -> int:
    if not INPUT_FILE.exists():
        print(f"Result: FAILED - input file not found: {INPUT_FILE}")
        return 1

    shutil.copyfile(INPUT_FILE, RENAMED_FILE)
    cases = [
        ("original", INPUT_FILE),
        ("misleading_filename", RENAMED_FILE),
    ]

    results = {}
    for label, path in cases:
        print(f"Running case: {label} -> {path.name}")
        parse_result = post_multipart(M5_URL, path)
        extraction_result = post_json(M7_URL, build_extraction_request(parse_result))
        validation_result = post_json(M8_URL, build_validation_request(extraction_result))
        results[label] = {
            "filename": path.name,
            "parse": parse_result,
            "extraction": extraction_result,
            "validation": validation_result,
        }
        print_summary(label, results[label])

    failures = compare_results(results["original"], results["misleading_filename"])
    print("\nComparison")
    if failures:
        for failure in failures:
            print(f"- FAIL: {failure}")
        print("Result: FAILED")
        return 1

    print("- PASS: Same content produced the same document classification.")
    print("- PASS: Same content produced the same transaction type output.")
    print("- PASS: Same content produced the same spending category output.")
    print("- PASS: Filename text did not drive document, transaction, or spending classification.")
    print("Result: PASSED")
    return 0


def post_multipart(url: str, path: Path) -> dict:
    boundary = f"----stats-boundary-{uuid4().hex}"
    file_bytes = path.read_bytes()
    fields = {
        "allow_ocr_fallback": "true",
        "classification_threshold": "0.1",
    }
    body_parts: list[bytes] = []
    for name, value in fields.items():
        body_parts.append(f"--{boundary}\r\n".encode("ascii"))
        body_parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
        body_parts.append(value.encode("utf-8"))
        body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}\r\n".encode("ascii"))
    body_parts.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode("ascii")
    )
    body_parts.append(file_bytes)
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode("ascii"))
    request = urllib.request.Request(
        url,
        data=b"".join(body_parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return read_json(request, timeout=180)


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return read_json(request, timeout=120)


def read_json(request: urllib.request.Request, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{request.full_url} returned HTTP {error.code}: {body}") from error


def build_extraction_request(parse_result: dict) -> dict:
    document = parse_result.get("document") or {}
    classification = parse_result.get("classification") or {}
    return {
        "parse_id": parse_result.get("parse_id"),
        "document": {
            "original_filename": document.get("original_filename"),
            "normalized_filename": document.get("normalized_filename"),
            "ingestion_id": document.get("ingestion_id"),
            "source_type": document.get("source_type"),
            "source_id": document.get("source_id"),
            "sha256": document.get("sha256"),
        },
        "document_type": classification.get("document_type") or document.get("document_type") or "unknown",
        "classification_confidence": classification.get("confidence"),
        "classification": classification,
        "text": parse_result.get("text") or "",
        "pages": parse_result.get("pages") or [],
        "metadata": parse_result.get("metadata") or {},
        "quality": parse_result.get("quality"),
        "findings": parse_result.get("findings") or [],
    }


def build_validation_request(extraction_result: dict) -> dict:
    classification = extraction_result.get("classification") or {}
    return {
        "extraction_id": extraction_result.get("extraction_id"),
        "parse_id": extraction_result.get("parse_id"),
        "document": extraction_result.get("document"),
        "document_type": extraction_result.get("document_type"),
        "document_type_confidence": classification.get("confidence"),
        "document_type_status": classification.get("status"),
        "document_type_reason_codes": classification.get("reason_codes") or [],
        "document_recognition_suggestion_id": classification.get("recognition_suggestion_id"),
        "document_recognition_suggestion_status": classification.get("recognition_suggestion_status") or "none",
        "suggested_document_type": classification.get("suggested_document_type"),
        "suggested_document_subtype": classification.get("suggested_document_subtype"),
        "document_suggestion_confidence": classification.get("suggestion_confidence"),
        "document_suggestion_reason_codes": classification.get("suggestion_reason_codes") or [],
        "document_suggestion_source": classification.get("suggestion_source"),
        "document_suggestion_evidence_ref": classification.get("suggestion_evidence_ref"),
        "transaction_candidates": extraction_result.get("transaction_candidates") or [],
        "financial_field_candidates": extraction_result.get("financial_field_candidates") or [],
        "section_candidates": extraction_result.get("section_candidates") or [],
        "entity_candidates": extraction_result.get("entity_candidates") or [],
        "reference_candidates": extraction_result.get("reference_candidates") or [],
        "line_item_candidates": extraction_result.get("line_item_candidates") or [],
        "installment_candidates": extraction_result.get("installment_candidates") or [],
        "reconciliation": extraction_result.get("reconciliation"),
        "findings": extraction_result.get("findings") or [],
    }


def print_summary(label: str, result: dict) -> None:
    parse = result["parse"]
    extraction = result["extraction"]
    validation = result["validation"]
    classification = parse.get("classification") or {}
    first_extracted = first_record(extraction.get("transaction_candidates") or [])
    first_validated = first_record(validation.get("normalized_records") or [])
    print(f"  filename: {result['filename']}")
    print(f"  text_length: {len(parse.get('text') or '')}")
    print(
        "  document: "
        f"{classification.get('document_type')} / {classification.get('document_subtype')} "
        f"status={classification.get('status')} source={classification.get('classification_source')}"
    )
    print(
        "  extracted transaction: "
        f"{first_extracted.get('transaction_type')} / {first_extracted.get('transaction_subtype')} "
        f"spending={first_extracted.get('spending_category')} / {first_extracted.get('spending_subcategory')}"
    )
    print(
        "  validated transaction: "
        f"{first_validated.get('transaction_type')} / {first_validated.get('transaction_subtype')} "
        f"spending={first_validated.get('spending_category')} / {first_validated.get('spending_subcategory')}"
    )


def compare_results(original: dict, renamed: dict) -> list[str]:
    failures: list[str] = []
    original_parse = original["parse"]
    renamed_parse = renamed["parse"]
    original_classification = original_parse.get("classification") or {}
    renamed_classification = renamed_parse.get("classification") or {}
    for field in ["document_type", "document_subtype", "status", "classification_source"]:
        if original_classification.get(field) != renamed_classification.get(field):
            failures.append(
                f"document classification field {field} changed: "
                f"{original_classification.get(field)} != {renamed_classification.get(field)}"
            )

    original_txn = first_record(original["extraction"].get("transaction_candidates") or [])
    renamed_txn = first_record(renamed["extraction"].get("transaction_candidates") or [])
    if not original_txn or not renamed_txn:
        failures.append("transaction candidates were not produced for both filenames")
    for field in ["transaction_type", "transaction_subtype", "spending_category", "spending_subcategory"]:
        if original_txn.get(field) != renamed_txn.get(field):
            failures.append(f"extracted {field} changed: {original_txn.get(field)} != {renamed_txn.get(field)}")

    original_record = first_record(original["validation"].get("normalized_records") or [])
    renamed_record = first_record(renamed["validation"].get("normalized_records") or [])
    if not original_record or not renamed_record:
        failures.append("validated transaction records were not produced for both filenames")
    for field in ["transaction_type", "transaction_subtype", "spending_category", "spending_subcategory"]:
        if original_record.get(field) != renamed_record.get(field):
            failures.append(f"validated {field} changed: {original_record.get(field)} != {renamed_record.get(field)}")

    return failures


def first_record(records: list[dict]) -> dict:
    return records[0] if records else {}


if __name__ == "__main__":
    sys.exit(main())
