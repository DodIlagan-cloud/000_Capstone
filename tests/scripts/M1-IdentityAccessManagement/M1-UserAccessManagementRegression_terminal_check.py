"""M13 container-first wrapper for historical M1 terminal checks."""

from pathlib import Path
import subprocess
import sys


repo_root = Path(__file__).resolve().parents[3]
runner = repo_root / "tests" / "scripts" / "regression" / "run_module_unit_tests.ps1"

print("Historical M1 terminal checks now delegate to the M13 container-first module test runner.", flush=True)
completed = subprocess.run(
    [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(runner),
    ],
    cwd=repo_root,
)
sys.exit(completed.returncode)
