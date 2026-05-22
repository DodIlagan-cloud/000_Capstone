---
name: module-test-evidence
description: Create assessment-ready test evidence for local software modules. Use when Codex needs to document module test results with actual Windows browser screenshots, actual Windows terminal screenshots, cropped relevant evidence, raw output logs, manual test checklists, and an evidence index for capstone or assessment artefacts.
---

# Module Test Evidence

<!-- M0 Foundation: reusable evidence workflow created during M0 for future modules. -->

Use this skill to produce reusable, assessment-friendly test artefacts for a completed module. The preferred evidence standard is actual Windows browser and terminal screenshots, cropped to the relevant content.

## Evidence Standard

- Store artefacts in a module-local `test-results/` directory.
- Treat every completed prior module test set as regression coverage for later modules.
- When a new module is tested, run and retain evidence for the new module tests and the relevant regression tests for every earlier completed module.
- Do not drop earlier module checks from a later module test session unless the user explicitly narrows the test scope or the earlier check has been formally replaced and documented.
- Use actual visible Windows Edge browser screenshots for endpoint/UI evidence.
- Keep the Edge address bar visible so the local URL/path is part of the browser evidence.
- Use normal Edge browser windows, not Edge `--app` mode, because app mode hides browser chrome and may show a site/app icon instead of the normal Edge presentation.
- Use actual visible Windows terminal screenshots for command/test output evidence.
- Reuse one visible terminal window for a test evidence session when its output is still valid.
- Crop screenshots to the relevant browser or terminal area before final delivery.
- Position visible browser windows away from the Windows toast notification area before capture to avoid unrelated notification evidence and retakes.
- Keep filenames stable and dated: `<module>-windows-browser-<target>-YYYY-MM-DD.png`.
- Maintain a Markdown evidence index that lists every retained screenshot and what it proves.
- Remove or avoid rendered-response screenshots unless the user explicitly asks for them.
- Include the exact command used for terminal verification in a test-results script or report.

## Workflow

1. Identify module name, working directory, service start command, and test targets.
2. Identify every completed earlier module whose tests must be carried into the regression pass.
3. Create `test-results/` under the module root.
4. Start the service in a visible Windows terminal when browser evidence is needed.
5. Confirm the service is ready with a direct local HTTP check before opening browser pages.
6. Run the current module verification and the carried-forward prior-module regression verification.
7. Open each target in a visible Windows Edge browser window or tab and position the window away from the Windows toast notification area.
8. Capture screenshots with `PIL.ImageGrab.grab()` and save them under `test-results/`.
9. Find and activate the existing test terminal window, then capture a visible Windows terminal screenshot showing test output and a clear passed/failed result.
10. Crop the screenshots to relevant browser or terminal content.
11. Create or update an evidence index Markdown file.
12. Stop any local server process started for evidence capture unless the user wants it left running.

## Carry-Forward Regression Rule

Each module adds to the project test baseline.

- Module 0 establishes the first test set.
- Module 1 testing must include Module 1 checks and Module 0 regression checks.
- Module 2 testing must include Module 2 checks plus Module 0 and Module 1 regression checks.
- Continue the same pattern for every succeeding module.

When the project has one command that runs all automated checks, use it as the automated regression baseline and still record which modules the run covers. When module-specific manual or evidence-driven checks exist, carry those checks forward when they protect behavior that later modules could break.

For a multi-module regression evidence session, store the module folders under one parent folder using:

```text
RegTest-<ShortChange>-M0-M1
```

Extend the module suffix as coverage grows, for example `RegTest-UploadFlow-M0-M1-M2`.

Each child module folder should keep its own module evidence files so a reviewer can see both the new module result and the earlier-module regression results from the same session.

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

Use visible Windows apps for evidence. Use Microsoft Edge for browser screenshots unless the user explicitly requests another browser. Commands that open browsers, terminals, or capture the desktop usually require approval outside the sandbox.

Before capturing Edge evidence:

- Place the Edge window away from the Windows toast notification area.
- Prefer a stable window position that keeps the endpoint content fully visible.
- Keep the browser address bar in the screenshot unless the user explicitly asks for content-only UI captures.
- Check for notification overlays before retaining the screenshot.

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

Keep that terminal window for the screenshot step when its displayed output is still correct. Approval prompts or desktop focus changes may place another window in front of it; do not open a second PowerShell window just to recover focus.

Before capturing terminal evidence:

- Find the existing visible PowerShell or Windows Terminal window used for the test.
- Activate or bring that same window to the foreground.
- Wait briefly after activation so the focus change settles before `ImageGrab.grab()`.
- Retake with the same terminal window when possible if the first capture shows another app in front.
- Open a new terminal only when the original window is gone, the output is stale, or the test must be rerun.

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
