"""M2 evidence terminal checks for Stats Web shell orchestration."""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tests/scripts" / "common"))
from test_config import configured_path, configured_url

APPSETTINGS_FILE = REPO_ROOT / "apps" / "stats-web" / "appsettings.json"


def run_command(command: list[str]) -> int:
    print(f"\nCommand: {' '.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout, flush=True)
    print(f"Exit code: {completed.returncode}", flush=True)
    return completed.returncode


def read_url(url: str, attempts: int = 20) -> tuple[int, str]:
    last_error = ""
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.status, response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = str(error)
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not become ready: {last_error}")


def main() -> int:
    print("M2 Stats Web Shell orchestration evidence check", flush=True)
    print(f"Repository: {REPO_ROOT}", flush=True)

    appsettings = json.loads(APPSETTINGS_FILE.read_text(encoding="utf-8"))
    orchestration = appsettings["StatsWeb"]["LocalOrchestration"]
    services = orchestration["Services"]

    print(f"Local orchestration enabled: {orchestration['Enabled']}", flush=True)
    print(f"Start missing services: {orchestration['StartMissingServices']}", flush=True)
    for service in services:
        print(f"Configured service: {service['Name']} -> {service['HealthUrl']}", flush=True)

    failures = 0
    build_output = configured_path(__file__, "evidenceFolders", "M2StatsWebOrchestration") / "build-output"
    failures += run_command(["dotnet", "build", "apps\\stats-web\\stats.Web.csproj", f"-p:OutputPath={build_output}\\"])
    failures += run_command(["pytest", "tests\\integration\\test_stats_web_orchestration_config.py"])
    failures += run_command(["pytest", "modules\\identity-access-module\\tests"])

    print("\nRuntime health checks:", flush=True)
    for url in [
        configured_url(__file__, "statsWebBaseUrl"),
        configured_url(__file__, "identityBaseUrl", "health"),
        configured_url(__file__, "fileIntakeBaseUrl", "health"),
    ]:
        status, body = read_url(url)
        print(f"{url} -> HTTP {status}", flush=True)
        print(body[:300].replace("\n", " "), flush=True)

    if failures:
        print("\nResult: FAILED", flush=True)
        return 1

    print("\nResult: PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
