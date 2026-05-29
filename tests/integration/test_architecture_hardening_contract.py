from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CONFIG = REPO_ROOT / "config" / "stats.runtime.json"
PATHS_CONFIG = REPO_ROOT / "config" / "stats.paths.json"
LOGGING_CONFIG = REPO_ROOT / "config" / "stats.logging.json"

ACTIVE_SPEC_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "M0-foundation-module-spec.md",
    REPO_ROOT / "docs" / "M1-user-management-access-control-spec.md",
    REPO_ROOT / "docs" / "M2-stats-web-shell-spec.md",
    REPO_ROOT / "docs" / "M3-file-validation-module-spec.md",
    REPO_ROOT / "docs" / "M5-document-parsing-module-spec.md",
    REPO_ROOT / "docs" / "M7-transaction-extraction-module-spec.md",
    REPO_ROOT / "docs" / "M8-data-validation-module-spec.md",
    REPO_ROOT / "docs" / "M13-containerization-module-spec.md",
    REPO_ROOT / "docs" / "building-block-module-plan.md",
    REPO_ROOT / "docs" / "specs" / "module-spec-template.md",
]

MODULE_DEFAULTS = [
    REPO_ROOT / "modules" / "identity-access-module" / "config" / "defaults.env",
    REPO_ROOT / "modules" / "file-validation-module" / "config" / "defaults.env",
    REPO_ROOT / "modules" / "document-parsing-module" / "config" / "defaults.env",
    REPO_ROOT / "modules" / "transaction-extraction-module" / "config" / "defaults.env",
    REPO_ROOT / "modules" / "data-validation-module" / "config" / "defaults.env",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _registered_runtime_keys(config: dict) -> set[str]:
    keys: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key.isupper() or "__" in key:
                    keys.add(key)
                    keys.add(key.replace("__", ":"))
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(config)
    return keys


def _env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def test_central_config_registries_exist_and_parse():
    runtime = _load_json(RUNTIME_CONFIG)
    paths = _load_json(PATHS_CONFIG)
    logging = _load_json(LOGGING_CONFIG)

    assert runtime["configFiles"]["pathMap"] == "config/stats.paths.json"
    assert runtime["configFiles"]["loggingRegistry"] == "config/stats.logging.json"
    assert paths["runtime"]["rootEnvironmentVariable"] == "STATS_APP_ROOT"
    assert logging["environmentVariables"]["LOG_LEVEL"]["default"] == "INFO"


def test_module_defaults_use_registered_runtime_keys():
    runtime = _load_json(RUNTIME_CONFIG)
    registered = _registered_runtime_keys(runtime)

    missing: dict[str, list[str]] = {}
    for defaults_file in MODULE_DEFAULTS:
        unknown = sorted(_env_keys(defaults_file) - registered)
        if unknown:
            missing[str(defaults_file.relative_to(REPO_ROOT))] = unknown

    assert not missing, f"Module defaults contain keys missing from config/stats.runtime.json: {missing}"


def test_active_specs_do_not_use_retired_architecture_paths():
    retired_terms = [
        "stats/stats",
        "stats\\stats",
        "pre-segregation",
        "transitional implementation",
        "transitional FastAPI",
        "current transitional",
    ]

    matches: dict[str, list[str]] = {}
    for spec_file in ACTIVE_SPEC_FILES:
        text = spec_file.read_text(encoding="utf-8-sig").lower()
        found = [term for term in retired_terms if term.lower() in text]
        if found:
            matches[str(spec_file.relative_to(REPO_ROOT))] = found

    assert not matches, f"Active specs contain retired architecture wording: {matches}"


def test_logging_registry_requires_container_safe_redaction():
    logging = _load_json(LOGGING_CONFIG)
    env = logging["environmentVariables"]

    assert env["LOG_DESTINATION"]["default"] == "stdout"
    assert env["LOG_REDACT_SENSITIVE_VALUES"]["default"] == "true"
    assert "raw OCR text" in logging["redaction"]["neverLogRawValuesFor"]
    assert "container" in logging["containerRule"].lower()
