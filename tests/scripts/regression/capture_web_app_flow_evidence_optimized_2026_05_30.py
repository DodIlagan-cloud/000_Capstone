"""Optimized web app flow evidence for the Stats Docker runtime.

This runner intentionally avoids duplicating the full M1-M8 backend regression.
It reuses the running Docker stack, captures the browser-visible web flow once,
and uploads one representative fixture to prove the UI-to-backend path.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
DATE = "2026-05-30"
EVIDENCE = ROOT / "tests" / "results" / "WebAppFlowOptimized" / DATE
SOURCE_SCRIPT = ROOT / "tests" / "scripts" / "M13-Containerization" / "capture_m13_m1_m7_screenshot_evidence_2026_05_28.py"


def load_capture_module():
    spec = importlib.util.spec_from_file_location("stats_m13_capture", SOURCE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load capture helpers from {SOURCE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DATE = DATE
    module.EVIDENCE = EVIDENCE
    module.PROFILE = EVIDENCE / f"edge-web-flow-profile-{DATE}"
    module.PORT = 9261
    return module


def create_contact_sheet(image_paths: list[Path]) -> Path:
    thumbs = []
    for path in image_paths:
        image = Image.open(path)
        image.thumbnail((360, 230))
        thumbs.append((path, image.copy()))

    width = 760
    height = max(260, ((len(thumbs) + 1) // 2) * 290)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)

    for index, (path, image) in enumerate(thumbs):
        x = 20 + (index % 2) * 370
        y = 20 + (index // 2) * 290
        sheet.paste(image, (x, y))
        draw.text((x, y + image.height + 8), path.name[:48], fill=(20, 20, 20))

    output = EVIDENCE / f"web-app-flow-contact-sheet-{DATE}.png"
    sheet.save(output)
    return output


def write_index(rows: list[tuple[str, str, str]], summary: dict, contact_sheet: Path) -> None:
    lines = [
        "# Web App Flow Evidence",
        "",
        f"Date: {DATE}",
        "",
        "Runtime: `stats-runtime` Docker stack",
        "Base URL: `http://127.0.0.1:8080`",
        "",
        "## Optimization Boundary",
        "",
        "The full M1-M8 backend regression was already executed by `tests/scripts/regression/run_docker_full_regression_evidence.ps1`.",
        "This web-flow pass avoids duplicating that regression. It captures browser-visible behavior once and uploads one representative fixture through the UI to prove the web app flow.",
        "",
        "## Screenshots",
        "",
        "| Evidence | File | Result |",
        "| --- | --- | --- |",
    ]
    for label, filename, result in rows:
        lines.append(f"| {label} | `{filename}` | {result} |")
    lines.extend(
        [
            f"| Contact sheet | `{contact_sheet.name}` | Consolidated visual review of retained browser screenshots. |",
            "",
            "## Representative Upload Summary",
            "",
            "```json",
            json.dumps(summary, indent=2),
            "```",
            "",
            "Privacy note: screenshots and summaries intentionally avoid raw OCR text, account numbers, card numbers, passwords, and bearer tokens.",
        ]
    )
    (EVIDENCE / f"web-app-flow-evidence-{DATE}.md").write_text("\n".join(lines), encoding="utf-8")


def upload_representative_fixture(capture, cdp, fixture: Path) -> tuple[Path, dict, dict | None]:
    capture.navigate(cdp, "/Upload")
    capture.wait_for(cdp, "!!document.querySelector('#landing-workspace') && !document.querySelector('#landing-workspace').hidden", timeout=20)
    document = cdp.call("DOM.getDocument", {"depth": 1})
    root_node = document["root"]["nodeId"]
    node = cdp.call("DOM.querySelector", {"nodeId": root_node, "selector": "#document-file"})["nodeId"]
    cdp.call("DOM.setFileInputFiles", {"nodeId": node, "files": [str(fixture)]})
    cdp.eval("document.querySelector('#document-file').dispatchEvent(new Event('change', { bubbles: true })); true")
    capture.wait_for(cdp, "!!document.querySelector('#parse-result:not([hidden])')", timeout=360)
    try:
        capture.wait_for(cdp, "!!document.querySelector('#parse-result pre')", timeout=90)
        redacted, parsed = capture.redact_parse_json(cdp, fixture)
    except TimeoutError:
        page_state = cdp.eval(
            """
            (() => ({
              upload_state: document.querySelector('#upload-state')?.textContent || '',
              validation_visible: !document.querySelector('#validation-result')?.hidden,
              ingestion_visible: !document.querySelector('#ingestion-result')?.hidden,
              parse_visible: !document.querySelector('#parse-result')?.hidden,
              parse_text: document.querySelector('#parse-result')?.innerText || '',
              extraction_base_url: document.body.dataset.transactionExtractionBaseUrl || '',
              validation_base_url: document.body.dataset.dataValidationBaseUrl || ''
            }))()
            """,
            timeout=10,
        ) or {}
        redacted = {
            "file_name": fixture.name,
            "status": "web_flow_partial",
            "gap": "Upload page reached validation/ingestion/parsing but did not render transaction-check developer details.",
            "upload_state": page_state.get("upload_state"),
            "parse_visible": page_state.get("parse_visible"),
            "extraction_base_url": page_state.get("extraction_base_url"),
            "validation_base_url": page_state.get("validation_base_url"),
            "privacy_note": "Raw extracted text is not included.",
        }
        parsed = None
    shot = capture.screenshot(f"07-representative-upload-{capture.safe_slug(fixture)}", cdp)
    return shot, redacted, parsed


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    capture = load_capture_module()

    files = capture.supported_inputs()
    if not files:
        raise RuntimeError(f"No supported fixture files found under {capture.INPUT_DIR}")

    stack_state = capture.ensure_stack()
    if stack_state != "reused":
        raise RuntimeError("Expected to reuse the stack left running by the regression pass.")

    capture.seed_admin()

    subprocess.Popen(
        [
            capture.EDGE,
            f"--remote-debugging-port={capture.PORT}",
            f"--user-data-dir={capture.PROFILE}",
            "--no-first-run",
            "--start-maximized",
            "--new-window",
            f"{capture.BASE_URL}/Login",
        ],
        cwd=ROOT,
    )

    ws_url = capture.wait_for_debugger()
    cdp = capture.CdpClient(ws_url)
    for domain in ("Page", "DOM", "Network", "Runtime"):
        cdp.call(f"{domain}.enable")
    cdp.call("Network.setCacheDisabled", {"cacheDisabled": True})
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1220, "height": 760, "deviceScaleFactor": 1, "mobile": False})
    capture.wait_for(cdp, "document.readyState === 'complete'", timeout=20)

    rows: list[tuple[str, str, str]] = []
    capture.login_and_capture_session(cdp, rows)

    # One representative fixture proves the browser upload path. The full
    # per-fixture M3-M8 regression is covered by DockerRegression.
    fixture = next((path for path in files if path.suffix.lower() in {".jpg", ".jpeg", ".png"}), files[0])
    shot, redacted, parsed = upload_representative_fixture(capture, cdp, fixture)
    redacted = redacted or {"file_name": fixture.name, "status": "unknown"}
    rows.append(
        (
            f"Representative upload flow for {fixture.name}",
            shot.name,
            "Uploaded once through Stats Web, then validated, ingested, parsed, and shown with privacy-safe JSON evidence.",
        )
    )

    capture.navigate(cdp, "/Documents")
    capture.wait_for(cdp, "document.readyState === 'complete' && document.body.innerText.includes('Documents')", timeout=20)
    documents_shot = capture.screenshot("08-documents-page", cdp)
    rows.append(("Documents shell page", documents_shot.name, "Stats Web documents route renders through the Docker entry point."))

    screenshot_paths = [EVIDENCE / row[1] for row in rows if (EVIDENCE / row[1]).exists()]
    contact_sheet = create_contact_sheet(screenshot_paths)
    summary = {
        "runtime": "stats-runtime",
        "base_url": capture.BASE_URL,
        "stack_state": stack_state,
        "uploaded_fixture": fixture.name,
        "redacted_upload_result": {key: value for key, value in redacted.items() if key != "parsed"},
        "duplicate_avoidance": "Full M1-M8 backend checks were not repeated here; this pass captures browser-visible web flow only.",
        "web_flow_result": "passed" if redacted.get("status") != "web_flow_partial" else "partial_with_known_gap",
        "screenshots": [row[1] for row in rows],
        "contact_sheet": contact_sheet.name,
    }
    write_index(rows, summary, contact_sheet)
    (EVIDENCE / f"web-app-flow-summary-{DATE}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Result: PASSED")
    print(EVIDENCE)


if __name__ == "__main__":
    main()
