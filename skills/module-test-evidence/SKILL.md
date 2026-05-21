---
name: module-test-evidence
description: Create assessment-ready test evidence for local software modules. Use when Codex needs to document module test results with actual Windows browser screenshots, actual Windows terminal screenshots, cropped relevant evidence, raw output logs, manual test checklists, and an evidence index for capstone or assessment artefacts.
---

# Module Test Evidence

<!-- M0 Foundation: reusable evidence workflow created during M0 for future modules. -->

Use this skill to produce reusable, assessment-friendly test artefacts for a completed module. The preferred evidence standard is actual Windows browser and terminal screenshots, cropped to the relevant content.

## Evidence Standard

- Store artefacts in a module-local `test-results/` directory.
- Use actual visible Windows browser screenshots for endpoint/UI evidence.
- Use actual visible Windows terminal screenshots for command/test output evidence.
- Crop screenshots to the relevant browser or terminal area before final delivery.
- Keep filenames stable and dated: `<module>-windows-browser-<target>-YYYY-MM-DD.png`.
- Maintain a Markdown evidence index that lists every retained screenshot and what it proves.
- Remove or avoid rendered-response screenshots unless the user explicitly asks for them.
- Include the exact command used for terminal verification in a test-results script or report.

## Workflow

1. Identify module name, working directory, service start command, and test targets.
2. Create `test-results/` under the module root.
3. Start the service in a visible Windows terminal when browser evidence is needed.
4. Confirm the service is ready with a direct local HTTP check before opening browser pages.
5. Open each target in a visible Windows browser window or tab.
6. Capture screenshots with `PIL.ImageGrab.grab()` and save them under `test-results/`.
7. Capture a visible Windows terminal screenshot showing test output and a clear passed/failed result.
8. Crop the screenshots to relevant browser or terminal content.
9. Create or update an evidence index Markdown file.
10. Stop any local server process started for evidence capture unless the user wants it left running.

## Recommended Artefacts

For a module named `foundation`, create:

- `test-results/foundation-test-results-YYYY-MM-DD.md`
- `test-results/foundation-test-raw-output-YYYY-MM-DD.txt`
- `test-results/foundation-manual-test-checklist.md`
- `test-results/foundation-screenshot-evidence-YYYY-MM-DD.md`
- `test-results/foundation-windows-browser-health-YYYY-MM-DD.png`
- `test-results/foundation-windows-browser-root-YYYY-MM-DD.png`
- `test-results/foundation-windows-browser-docs-YYYY-MM-DD.png`
- `test-results/foundation-windows-terminal-test-YYYY-MM-DD.png`

Adapt target names to the module, such as `ingest-upload`, `transactions-list`, or `database-init`.

## Windows Screenshot Capture

Use visible Windows apps for evidence. Commands that open browsers, terminals, or capture the desktop usually require approval outside the sandbox.

Example visible service terminal:

```powershell
Start-Process -FilePath powershell.exe -ArgumentList @(
  '-NoExit',
  '-Command',
  'cd "C:\path\to\module"; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
)
```

Example readiness check:

```powershell
python -c "import urllib.request, time; url='http://127.0.0.1:8000/health';
for i in range(30):
    try:
        print(urllib.request.urlopen(url, timeout=2).read().decode()); break
    except Exception:
        time.sleep(0.5)
else:
    raise SystemExit('server did not become ready')"
```

Example screenshot capture:

```powershell
python -c "from PIL import ImageGrab; p='test-results/module-windows-browser-health-YYYY-MM-DD.png'; ImageGrab.grab().save(p); print(p)"
```

## Terminal Evidence

Prefer a short module-specific script under `test-results/` when PowerShell quoting would be fragile. The script should print:

- Module/test name.
- Command or API checks performed.
- HTTP status codes or test assertions.
- A final `Result: PASSED` or `Result: FAILED`.

If the script lives under `test-results/`, add the module root to `sys.path` before importing local packages:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

Then open it in a visible terminal:

```powershell
Start-Process -FilePath powershell.exe -ArgumentList @(
  '-NoExit',
  '-Command',
  'cd "C:\path\to\module"; python test-results\module_terminal_check.py'
)
```

## Cropping

Crop screenshots after capture so they contain only the relevant browser or terminal content.

Use `scripts/crop_screenshots.py` when crop boxes are known:

```powershell
python "<skill-path>\scripts\crop_screenshots.py" --base "C:\path\to\module\test-results" --crop "file.png=left,top,right,bottom"
```

Preview screenshots before and after cropping when possible. If a crop is wrong, restore from the original capture if available or retake the screenshot.

## Evidence Index

Create or update `<module>-screenshot-evidence-YYYY-MM-DD.md` with:

- Local service URL.
- Screenshot file table.
- What each screenshot proves.
- Note that evidence uses actual Windows browser/terminal screenshots.
- Note that screenshots are cropped to relevant content.

Example table:

```markdown
| Evidence | File | Result |
| --- | --- | --- |
| Windows browser health evidence | `module-windows-browser-health-YYYY-MM-DD.png` | Browser opened `GET /health` from the local service |
| Windows terminal test evidence | `module-windows-terminal-test-YYYY-MM-DD.png` | PowerShell displayed direct module test output with passed result |
```

## Cleanup

- Stop any local server process started for evidence capture.
- Delete incorrect screenshots after replacement.
- Remove rendered-response screenshots if the evidence standard is actual Windows screenshots only.
- Keep helper scripts if they support repeatable evidence generation for the module.
