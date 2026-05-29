"""M5 - Document Parsing Module Start
Run M5 parser against every file in tests/input.

Intended official use after M13:
    docker exec stats-runtime python3 /app/tests/scripts/M5-DocumentParsing/run_m5_all_inputs_manual_unit_2026_05_28.py
M5/M6 End"""

from __future__ import annotations

import contextlib
import io
import json
import mimetypes
import sys
import traceback
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESULT_DIR = ROOT / "tests" / "results" / "M5-DocumentParsing-AllInputsManualUnit-2026-05-28"
INPUT_DIR = ROOT / "tests" / "input"
MODULE_DIR = ROOT / "modules" / "document-parsing-module"
DATE_STAMP = "2026-05-28"

sys.path.insert(0, str(MODULE_DIR))

from app.services.parsing_service import parse_document_content  # noqa: E402


def model_to_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def main() -> int:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    output_json = RESULT_DIR / f"M5-all-inputs-manual-unit-output-{DATE_STAMP}.json"
    output_summary = RESULT_DIR / f"M5-all-inputs-manual-unit-summary-{DATE_STAMP}.md"
    output_raw = RESULT_DIR / f"M5-all-inputs-manual-unit-raw-output-{DATE_STAMP}.txt"

    rows = []
    full_results = []
    raw_lines = [
        "M5 all-inputs manual unit parser run",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Script: {Path(__file__).resolve()}",
        f"Input directory: {INPUT_DIR}",
        f"Result directory: {RESULT_DIR}",
        "",
    ]

    files = sorted(path for path in INPUT_DIR.rglob("*") if path.is_file())
    for path in files:
        relative_name = path.relative_to(INPUT_DIR).as_posix()
        provided_content_type = mimetypes.guess_type(path.name)[0]
        raw_lines.append(f"--- {relative_name} ---")

        try:
            content = path.read_bytes()
            captured_stdout = io.StringIO()
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stdout):
                result = parse_document_content(
                    content=content,
                    filename=path.name,
                    provided_content_type=provided_content_type,
                    ingestion_id=f"manual-unit-{path.stem}",
                    source_type="manual_unit_test",
                    allow_ocr_fallback=True,
                    classification_threshold=0.2,
                )

            result_dict = model_to_dict(result)
            captured_text = captured_stdout.getvalue().strip()
            codes = [finding["code"] for finding in result_dict.get("findings", [])]
            row = {
                "file": relative_name,
                "size_bytes": path.stat().st_size,
                "provided_content_type": provided_content_type,
                "status": result_dict.get("status"),
                "strategy": result_dict.get("strategy", {}).get("selected_strategy"),
                "document_type": result_dict.get("classification", {}).get("document_type"),
                "classification_confidence": result_dict.get("classification", {}).get("confidence"),
                "text_length": result_dict.get("quality", {}).get("text_length"),
                "ocr_quality_score": result_dict.get("metadata", {}).get("ocr_quality_score"),
                "ocr_mean_confidence": result_dict.get("metadata", {}).get("ocr_mean_confidence"),
                "ocr_selected_orientation": result_dict.get("metadata", {}).get("ocr_selected_orientation"),
                "ocr_selected_psm": result_dict.get("metadata", {}).get("ocr_selected_psm"),
                "ocr_attempt_count": result_dict.get("metadata", {}).get("ocr_attempt_count"),
                "finding_codes": codes,
            }
            rows.append(row)
            full_results.append({"file": relative_name, "result": result_dict})

            raw_lines.extend(
                [
                    f"status={row['status']}",
                    f"strategy={row['strategy']}",
                    f"document_type={row['document_type']}",
                    f"text_length={row['text_length']}",
                    f"ocr_quality_score={row['ocr_quality_score']}",
                    f"ocr_mean_confidence={row['ocr_mean_confidence']}",
                    f"ocr_selected_orientation={row['ocr_selected_orientation']}",
                    f"ocr_selected_psm={row['ocr_selected_psm']}",
                    f"ocr_attempt_count={row['ocr_attempt_count']}",
                    f"finding_codes={','.join(codes) if codes else 'none'}",
                ]
            )
            if captured_text:
                raw_lines.append("captured_parser_output:")
                raw_lines.append(captured_text)
        except Exception as exc:
            row = {
                "file": relative_name,
                "size_bytes": path.stat().st_size,
                "provided_content_type": provided_content_type,
                "status": "script_error",
                "strategy": None,
                "document_type": None,
                "classification_confidence": None,
                "text_length": None,
                "ocr_quality_score": None,
                "ocr_mean_confidence": None,
                "ocr_selected_orientation": None,
                "ocr_selected_psm": None,
                "ocr_attempt_count": None,
                "finding_codes": [type(exc).__name__],
            }
            rows.append(row)
            full_results.append({"file": relative_name, "script_error": traceback.format_exc()})
            raw_lines.append(f"script_error={type(exc).__name__}: {exc}")
        raw_lines.append("")

    output_json.write_text(
        json.dumps(
            {
                "module": "M5 Document Parsing",
                "run_type": "manual_unit_all_test_inputs",
                "script": str(Path(__file__).resolve()),
                "input_directory": str(INPUT_DIR),
                "results": full_results,
                "summary": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    status_counts = {}
    strategy_counts = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        strategy_counts[row["strategy"]] = strategy_counts.get(row["strategy"], 0) + 1

    summary_lines = [
        "# M5 All Inputs Manual Unit Test",
        "",
        f"Date: {DATE_STAMP}",
        f"Script: `{Path(__file__).resolve()}`",
        f"Input directory: `{INPUT_DIR}`",
        f"Result JSON: `{output_json.name}`",
        f"Raw output: `{output_raw.name}`",
        "",
        "## Result Counts",
        "",
        f"- Files processed: {len(rows)}",
        f"- Status counts: `{status_counts}`",
        f"- Strategy counts: `{strategy_counts}`",
        "",
        "## File Results",
        "",
        "| File | Status | Strategy | Type | Text Length | OCR Quality | OCR Orientation | OCR PSM | OCR Attempts | Findings |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        summary_lines.append(
            "| {file} | {status} | {strategy} | {document_type} | {text_length} | {ocr_quality_score} | {ocr_selected_orientation} | {ocr_selected_psm} | {ocr_attempt_count} | {findings} |".format(
                file=row["file"],
                status=row["status"],
                strategy=row["strategy"],
                document_type=row["document_type"],
                text_length=row["text_length"],
                ocr_quality_score=row["ocr_quality_score"],
                ocr_selected_orientation=row["ocr_selected_orientation"],
                ocr_selected_psm=row["ocr_selected_psm"],
                ocr_attempt_count=row["ocr_attempt_count"],
                findings=", ".join(row["finding_codes"]) if row["finding_codes"] else "none",
            )
        )

    summary_lines.extend(
        [
            "",
            "## Ethical Data Note",
            "",
            "The Markdown summary intentionally lists metadata, quality values, and finding codes only. Full JSON output is retained locally for development review and may include extracted document text plus redacted evidence previews.",
            "",
        ]
    )
    output_summary.write_text("\n".join(summary_lines), encoding="utf-8")
    output_raw.write_text("\n".join(raw_lines), encoding="utf-8")

    print("\n".join(raw_lines))
    print(f"Summary: {output_summary}")
    print(f"JSON: {output_json}")
    print(f"Raw: {output_raw}")
    if any(row["status"] == "script_error" for row in rows):
        print("Result: FAILED")
        return 1
    print("Result: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
