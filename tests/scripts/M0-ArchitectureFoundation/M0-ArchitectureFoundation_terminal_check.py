"""Direct M0 architecture foundation checks for terminal evidence."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

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

REQUIRED_CONTENT = {
    "apps/README.md": ("stats-web/", "stats-data/"),
    "modules/README.md": ("identity-access-module/", "data-validation-module/"),
    "docs/M0-foundation-module-spec.md": ("Stats Data and Persistence", "|   |-- stats-data/"),
}

FORBIDDEN_CONTENT = {
    "modules/README.md": ("records-storage-module/",),
    "docs/M0-foundation-module-spec.md": ("records-storage-module/",),
}

REQUIRED_CONFIGURATION_CONTENT = {
    "README.md": ("instead of being hardcoded in application code",),
    "docs/building-block-module-plan.md": ("instead of being hardcoded in source code",),
    "docs/M0-foundation-module-spec.md": ("## Runtime Configuration Standard", "without editing source code"),
    "docs/specs/module-spec-template.md": ("Config override path or provider", "Hardcoded runtime values allowed in source"),
    "apps/README.md": ("rather than hardcoding them in source",),
    "modules/README.md": ("do not require source-code edits",),
}


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


def display_content_check(path_text: str, expected_text: str) -> bool:
    content = (REPO_ROOT / path_text).read_text(encoding="utf-8")
    present = expected_text in content
    print(f"[{'PASS' if present else 'FAIL'}] required content in {path_text}: {expected_text}")
    return present


def display_absence_check(path_text: str, forbidden_text: str) -> bool:
    content = (REPO_ROOT / path_text).read_text(encoding="utf-8")
    absent = forbidden_text not in content
    print(f"[{'PASS' if absent else 'FAIL'}] absent obsolete content in {path_text}: {forbidden_text}")
    return absent


def main() -> int:
    print("M0 Architecture Foundation Direct Verification")
    print("Command: python tests\scripts\\M0-ArchitectureFoundation\\M0-ArchitectureFoundation_terminal_check.py")
    print(f"Repository: {REPO_ROOT}")
    print()
    print("Scenario M0-AF-01: required architecture artefacts")
    path_results = [display_path_check(path_text) for path_text in REQUIRED_PATHS]
    print()
    print("Scenario M0-AF-02: repository hygiene ignore rules")
    ignore_results = [display_ignore_check(path_text) for path_text in IGNORE_TARGETS]
    print()
    print("Scenario M0-AF-03: Stats Data persistence boundary")
    content_results = [
        display_content_check(path_text, expected_text)
        for path_text, expected_values in REQUIRED_CONTENT.items()
        for expected_text in expected_values
    ]
    absence_results = [
        display_absence_check(path_text, forbidden_text)
        for path_text, forbidden_values in FORBIDDEN_CONTENT.items()
        for forbidden_text in forbidden_values
    ]
    print()
    print("Scenario M0-AF-04: config-driven runtime values")
    configuration_results = [
        display_content_check(path_text, expected_text)
        for path_text, expected_values in REQUIRED_CONFIGURATION_CONTENT.items()
        for expected_text in expected_values
    ]
    print()

    passed = (
        all(path_results)
        and all(ignore_results)
        and all(content_results)
        and all(absence_results)
        and all(configuration_results)
    )
    print(f"Required artefacts passed: {sum(path_results)}/{len(path_results)}")
    print(f"Ignore-rule checks passed: {sum(ignore_results)}/{len(ignore_results)}")
    print(f"Stats Data boundary checks passed: {sum(content_results) + sum(absence_results)}/{len(content_results) + len(absence_results)}")
    print(f"Runtime configuration checks passed: {sum(configuration_results)}/{len(configuration_results)}")
    print(f"Result: {'PASSED' if passed else 'FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
