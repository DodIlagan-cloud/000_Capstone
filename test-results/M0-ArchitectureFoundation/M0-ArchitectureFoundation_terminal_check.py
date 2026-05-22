"""Direct M0 architecture foundation checks for terminal evidence."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PATHS = (
    "README.md",
    "apps/README.md",
    "modules/README.md",
    "contracts/README.md",
    "infrastructure/README.md",
    "samples/README.md",
    "tests/integration/README.md",
    "docs/M0-foundation-module-spec.md",
    "docs/M0-foundation-file-inventory.md",
    "docs/building-block-module-plan.md",
    "docs/building-block-module-io-map.md",
    "docs/specs/module-spec-template.md",
    "docs/evidence/README.md",
    "docs/module-plans/README.md",
    "stats/README.md",
)

IGNORE_TARGETS = (
    "docx_render_check",
    "stats/stats.Web/bin",
    "stats/stats.Web/obj",
    "stats/stats-ingestion-service/stats_ingestion.db",
)


def display_path_check(path_text: str) -> bool:
    exists = (REPO_ROOT / path_text).exists()
    print(f"[{'PASS' if exists else 'FAIL'}] required path: {path_text}")
    return exists


def display_ignore_check(path_text: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", "-q", path_text],
        cwd=REPO_ROOT,
        check=False,
    )
    ignored = completed.returncode == 0
    print(f"[{'PASS' if ignored else 'FAIL'}] ignored local/build path: {path_text}")
    return ignored


def main() -> int:
    print("M0 Architecture Foundation Direct Verification")
    print("Command: python test-results\\M0-ArchitectureFoundation\\M0-ArchitectureFoundation_terminal_check.py")
    print(f"Repository: {REPO_ROOT}")
    print()
    print("Scenario M0-AF-01: required architecture artefacts")
    path_results = [display_path_check(path_text) for path_text in REQUIRED_PATHS]
    print()
    print("Scenario M0-AF-02: repository hygiene ignore rules")
    ignore_results = [display_ignore_check(path_text) for path_text in IGNORE_TARGETS]
    print()

    passed = all(path_results) and all(ignore_results)
    print(f"Required artefacts passed: {sum(path_results)}/{len(path_results)}")
    print(f"Ignore-rule checks passed: {sum(ignore_results)}/{len(ignore_results)}")
    print(f"Result: {'PASSED' if passed else 'FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
