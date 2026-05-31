from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def repo_root(script_file: str | Path) -> Path:
    configured_root = os.environ.get("STATS_APP_ROOT")
    if configured_root:
        return Path(configured_root).resolve()
    return Path(script_file).resolve().parents[3]


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(script_file: str | Path) -> dict[str, Any]:
    root = repo_root(script_file)
    config_dir = root / "tests/scripts" / "config"
    settings = json.loads((config_dir / "test-script-settings.json").read_text(encoding="utf-8"))
    path_config = settings.setdefault("pathConfig", {})
    stats_runtime_config = root / path_config.get("overallStatsRuntimeConfig", "config/stats.runtime.json")
    if stats_runtime_config.exists():
        settings["statsRuntime"] = json.loads(stats_runtime_config.read_text(encoding="utf-8"))

    stats_paths_config = root / path_config.get("overallStatsPathConfig", "config/stats.paths.json")
    if stats_paths_config.exists():
        settings["statsPaths"] = json.loads(stats_paths_config.read_text(encoding="utf-8"))

    local_settings_path = config_dir / "test-script-settings.local.json"
    if local_settings_path.exists():
        settings = _merge(settings, json.loads(local_settings_path.read_text(encoding="utf-8")))

    if os.environ.get("STATS_TESTDATA_DIR"):
        settings.setdefault("localPaths", {})["testDataDir"] = os.environ["STATS_TESTDATA_DIR"]

    return settings


def configured_path(script_file: str | Path, section: str, key: str) -> Path:
    settings = load_settings(script_file)
    value = settings[section][key]
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root(script_file) / path


def configured_url(script_file: str | Path, key: str, suffix: str = "") -> str:
    base_url = str(load_settings(script_file)["runtime"][key]).rstrip("/")
    return f"{base_url}/{suffix.lstrip('/')}" if suffix else base_url
