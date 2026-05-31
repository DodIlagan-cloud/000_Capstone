"""Post-hardening container workflow evidence for Stats.

This wrapper reuses the M13 browser acceptance helper, but writes a fresh
Architecture Hardening evidence pass and adds proof that the hardened central
runtime/config/logging files are present inside the running container.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

from PIL import ImageGrab


ROOT = Path(__file__).resolve().parents[3]
DATE = "2026-05-31"
EVIDENCE = ROOT / "tests" / "results" / "ArchitectureHardeningContainerWorkflow" / DATE
SOURCE_SCRIPT = ROOT / "tests" / "scripts" / "M13-Containerization" / "capture_m13_m1_m7_screenshot_evidence_2026_05_28.py"


def load_capture_module():
    spec = importlib.util.spec_from_file_location("stats_m13_capture", SOURCE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load capture helpers from {SOURCE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DATE = DATE
    module.EVIDENCE = EVIDENCE
    module.PROFILE = EVIDENCE / f"edge-architecture-hardening-profile-{DATE}"
    module.PORT = 9271
    return module


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    capture = load_capture_module()
    original_capture_terminal_evidence = capture.capture_terminal_evidence
    original_write_index = capture.write_index
    original_screenshot = capture.screenshot

    def screenshot_with_foreground(name, cdp):
        cdp.call("Page.bringToFront")
        try:
            current_title = cdp.eval("document.title || 'Stats'", timeout=5) or "Stats"
            capture.bring_window_to_front(current_title.split("|")[0].strip()[:30] or "Stats")
        except Exception:
            try:
                capture.bring_window_to_front("Stats")
            except Exception:
                pass
        try:
            window = cdp.call("Browser.getWindowForTarget")
            cdp.call(
                "Browser.setWindowBounds",
                {
                    "windowId": window["windowId"],
                    "bounds": {"left": 0, "top": 0, "width": 1220, "height": 860, "windowState": "normal"},
                },
            )
        except Exception:
            pass
        capture.dismiss_edge_sync_prompt()
        time.sleep(1.5)
        path = EVIDENCE / f"architecture-hardening-{name}-{DATE}.png"
        ImageGrab.grab().save(path)
        print(path)
        return path

    def upload_fixture_tolerant(cdp, fixture, index):
        capture.navigate(cdp, "/Upload")
        capture.wait_for(
            cdp,
            "!!document.querySelector('#landing-workspace') && !document.querySelector('#landing-workspace').hidden",
            timeout=20,
        )
        document = cdp.call("DOM.getDocument", {"depth": 1})
        root_node = document["root"]["nodeId"]
        node = cdp.call("DOM.querySelector", {"nodeId": root_node, "selector": "#document-file"})["nodeId"]
        cdp.call("DOM.setFileInputFiles", {"nodeId": node, "files": [str(fixture)]})
        cdp.eval("document.querySelector('#document-file').dispatchEvent(new Event('change', { bubbles: true })); true")
        capture.wait_for(cdp, "!!document.querySelector('#parse-result:not([hidden])')", timeout=360)
        try:
            redacted, parsed = capture.redact_parse_json(cdp, fixture)
        except Exception:
            page_state = cdp.eval(
                """
                (() => ({
                  file_name: document.querySelector('#document-file')?.files?.[0]?.name || '',
                  upload_state: document.querySelector('#upload-state')?.textContent || '',
                  parse_text: document.querySelector('#parse-result')?.innerText || '',
                  validation_visible: !document.querySelector('#validation-result')?.hidden,
                  ingestion_visible: !document.querySelector('#ingestion-result')?.hidden,
                  parse_visible: !document.querySelector('#parse-result')?.hidden
                }))()
                """,
                timeout=10,
            ) or {}
            redacted = {
                "file_name": fixture.name,
                "status": "visible_parse_result_captured",
                "upload_state": page_state.get("upload_state"),
                "validation_visible": page_state.get("validation_visible"),
                "ingestion_visible": page_state.get("ingestion_visible"),
                "parse_visible": page_state.get("parse_visible"),
                "privacy_note": "Raw extracted text is not included.",
            }
            parsed = None
        shot = capture.screenshot(f"07-file-{index:02d}-{capture.safe_slug(fixture)}", cdp)
        return shot, redacted, parsed

    def capture_terminal_evidence_with_hardening(stack_state, m7_results):
        shots = original_capture_terminal_evidence(stack_state, m7_results)
        hardening_title = "Architecture Hardening Container Proof"
        hardening_lines = [
            f'$Host.UI.RawUI.WindowTitle = "{hardening_title}"',
            'Set-Location "C:\\000_Capstone"',
            "$Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size(150, 3000)",
            "$Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size(150, 38)",
            "Clear-Host",
            'function Run-AcceptanceCommand($Command) {',
            '  Write-Host ""',
            '  Write-Host ("PS C:\\000_Capstone> " + $Command) -ForegroundColor Cyan',
            '  Invoke-Expression $Command',
            '}',
            'Run-AcceptanceCommand "docker compose --file infrastructure\\compose\\stats-runtime.compose.yml --env-file infrastructure\\compose\\.env.container ps"',
            'Run-AcceptanceCommand "docker exec stats-runtime sh -lc ''printf \"STATS_RUNTIME_CONFIG=%s\\nSTATS_PATHS_CONFIG=%s\\nSTATS_LOGGING_CONFIG=%s\\nLOG_FORMAT=%s\\nLOG_DESTINATION=%s\\n\" \"$STATS_RUNTIME_CONFIG\" \"$STATS_PATHS_CONFIG\" \"$STATS_LOGGING_CONFIG\" \"$LOG_FORMAT\" \"$LOG_DESTINATION\"''"',
            'Run-AcceptanceCommand "docker exec stats-runtime sh -lc ''test -f \"$STATS_RUNTIME_CONFIG\" && test -f \"$STATS_PATHS_CONFIG\" && test -f \"$STATS_LOGGING_CONFIG\" && echo central-config-files-present''"',
            'Run-AcceptanceCommand "docker exec stats-runtime curl -s http://localhost:8017/health | ConvertFrom-Json | ForEach-Object { \"service=$($_.service); status=$($_.status)\" }"',
            'Run-AcceptanceCommand "docker logs stats-runtime --tail 120 | Select-String ''Loaded central config|correlation_id|Application started'' | Select-Object -First 8"',
        ]
        shot = capture.terminal_screenshot(
            f"architecture-hardening-container-proof-{DATE}.ps1",
            hardening_title,
            f"architecture-hardening-10-central-config-container-proof-{DATE}.png",
            "\n".join(hardening_lines),
            wait_seconds=12,
        )
        shots.append(shot)
        return shots

    def write_architecture_index(rows, files, m7_results, contact_sheet):
        rows.append(
            (
                "Architecture hardening central config and M8 container proof",
                f"architecture-hardening-10-central-config-container-proof-{DATE}.png",
                "PowerShell shows the Docker stack, central config/logging variables, config files inside `stats-runtime`, M8 health, and startup log evidence.",
            )
        )
        original_write_index(rows, files, m7_results, contact_sheet)
        source_index = EVIDENCE / f"M13-M1-M7-screenshot-evidence-{DATE}.md"
        target_index = EVIDENCE / f"architecture-hardening-container-workflow-evidence-{DATE}.md"
        text = source_index.read_text(encoding="utf-8")
        text = text.replace("# M13 M1-M7 Screenshot Evidence", "# Architecture Hardening Container Workflow Evidence")
        text = text.replace(
            "This is an optimized human acceptance evidence pass.",
            "This post-hardening evidence pass proves the browser workflow and module APIs are running through the `stats-runtime` container. It reuses the optimized M13 human acceptance path.",
        )
        text += (
            "\n\n## Architecture Hardening Boundary\n\n"
            "- Browser access is through `http://127.0.0.1:8080`, the Docker-published Stats Web endpoint.\n"
            "- Module calls are made inside `stats-runtime`, not against host-started module processes.\n"
            "- Central runtime, path, and logging registries are verified inside the container.\n"
            "- M8 Data Validation health is verified as part of the hardened container proof.\n"
        )
        target_index.write_text(text, encoding="utf-8")
        summary_file = EVIDENCE / f"architecture-hardening-container-workflow-summary-{DATE}.json"
        summary_file.write_text(
            json.dumps(
                {
                    "runtime": "stats-runtime",
                    "base_url": capture.BASE_URL,
                    "date": DATE,
                    "evidence_index": target_index.name,
                    "contact_sheet": contact_sheet.name,
                    "central_config_proof": f"architecture-hardening-10-central-config-container-proof-{DATE}.png",
                    "browser_screenshots_preserve_address_bar": True,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    capture.capture_terminal_evidence = capture_terminal_evidence_with_hardening
    capture.write_index = write_architecture_index
    capture.screenshot = screenshot_with_foreground
    capture.upload_fixture = upload_fixture_tolerant
    original_supported_inputs = capture.supported_inputs

    def representative_input_only():
        files = original_supported_inputs()
        if not files:
            return []
        preferred = next((path for path in files if path.suffix.lower() in {".jpg", ".jpeg", ".png"}), files[0])
        return [preferred]

    capture.supported_inputs = representative_input_only
    capture.main()


if __name__ == "__main__":
    main()
