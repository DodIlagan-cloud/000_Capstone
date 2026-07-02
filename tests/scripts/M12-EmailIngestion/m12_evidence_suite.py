"""M12 Email Ingestion one-command evidence suite.

Runs the whole M12 evidence chain in order, auto-discovers the latest import run,
and writes every transcript into one timestamped evidence folder so a single
command produces the complete capture package:

    1. unit          - pytest tests/unit/email_ingestion_module (automated test signal)
    2. runtime       - m12_email_ingestion_runtime_evidence_check.py
    3. run_history   - m12_email_ingestion_run_history_evidence_check.py (SQL rows)
    4. blob          - m12_email_ingestion_blob_evidence_check.py (per handoff id)
    5. database      - m12_email_ingestion_database_evidence_check.py (per handoff id)
    6. visual        - manifest of the manually captured screenshot set

The suite only READS evidence of runs that already happened; it never triggers a
mailbox import or a database ingest, so it cannot mutate data or spoil evidence.
Steps whose prerequisites are missing are reported as SKIPPED with the reason,
matching the failure-stop rule (a FAILED step stops the suite).

ACCEPTANCE GATE: by default every core proof (unit, runtime, run_history, blob,
database, visual) must actually run and pass - a SKIPPED core step downgrades the
final result to INCOMPLETE (exit code 2), so the suite cannot report acceptance
success without proving mailbox PDF -> Blob -> database plus the visual set.
Pass --prep for a terminal-only diagnostic run where skips are allowed.

Visual proof (before/after data-state model): screenshots prove the STATE of the
acted-upon data before and after a step, and are only required where that state
lives on a surface this suite cannot query - the external mailbox (PDF in the
inbox BEFORE import), the Azure Portal (blob row AFTER import), and the app UI
(Documents/Reports AFTER database ingest). Every machine-queryable state (run
history, blob listing, SQL rows) is proven by this suite's transcripts instead.
Pass --visual-evidence-dir <folder> containing the captures plus
visual-evidence-manifest.json. The manifest must bind the whole set to ONE run
(top-level run_id + subject_file, checked against the discovered run and its
candidates) and each item must name a real file whose filename contains its
proof_key, set synthetic=false, live_capture=true, and use the capture_method
allowed for that proof. Synthetic/mock/sample-style names are rejected, and each
capture's sha256 is recorded as a permanent text integrity anchor.

Targets:
- local: host-running Stats Web + module APIs. API calls go through the local
  Stats Web proxy (default http://127.0.0.1:8080, override --web-base-url),
  matching cloud ingress behavior. The internal key and SQL connection string
  come from the LOCAL environment.
- container (default): local stats-runtime container.
- cloud: the deployed Azure Container Apps runtime. All API calls go through the
  Stats Web public URL, the internal key and AZURE_SQL_CONNECTIONSTRING come from
  the LOCAL environment, and the SQL proofs run from this workstation against
  Azure SQL (requires local pyodbc + ODBC Driver 18 and a SQL firewall rule).

Usage (from C:\\000_Capstone, runtime container up):

    python tests\\scripts\\M12-EmailIngestion\\m12_evidence_suite.py --visual-evidence-dir <screenshots>
    python tests\\scripts\\M12-EmailIngestion\\m12_evidence_suite.py --run-id email_run_abc123 --prep
    python tests\\scripts\\M12-EmailIngestion\\m12_evidence_suite.py --prep --skip-unit --skip-blob

Local-proxy usage (host-running app, same proxy shape as cloud):

    python tests\\scripts\\M12-EmailIngestion\\m12_evidence_suite.py --target local \\
        --web-base-url http://127.0.0.1:8080 --prep --skip-blob --skip-database

Cloud usage (az login done; STATS_INTERNAL_API_KEY and AZURE_SQL_CONNECTIONSTRING
set in this shell):

    python tests\\scripts\\M12-EmailIngestion\\m12_evidence_suite.py --target cloud \\
        --web-base-url https://ca-stats-dev-001.<env>.azurecontainerapps.io \\
        --visual-evidence-dir <screenshots>

No secrets are printed or written to the evidence folder.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
RESULTS_DIR = REPO_ROOT / "tests" / "results" / "M12-EmailIngestion"
LOCAL_EMAIL_BASE = "http://127.0.0.1:8019"
CONTAINER = "stats-runtime"

# Core proofs that must actually run and pass for acceptance evidence. A SKIPPED
# entry in this set downgrades the final result to INCOMPLETE unless --prep.
REQUIRED_STEPS = ("unit", "runtime", "run_history", "blob", "database", "visual")

# Visual evidence = BEFORE/AFTER data-state proofs bound to one import run.
# Pixels are required only where the state lives on a surface this suite cannot
# query (external mailbox, Azure Portal, app UI). Machine-queryable states (run
# history, blob listing, SQL rows) are proven by the transcript steps - a
# screenshot of queryable text adds cost, not evidence. Each proof is matched by
# filename keyword (case-insensitive), e.g. "01-mailbox-before.png".
# Tuples: (key, transition, phase, label)
VISUAL_PROOF_SET = (
    ("mailbox-before", "mailbox_to_blob", "before", "mailbox message showing the subject PDF before import"),
    ("blob-after", "mailbox_to_blob", "after", "Blob row under intake/<ingestion_id> after import"),
    ("documents-view", "database_to_app", "after", "Documents/Reports showing the ingested document"),
)
# Accepted when present, never required for the gate.
OPTIONAL_VISUAL_PROOFS = (
    ("run-status", "mailbox_to_blob", "action", "Email Setup run status (run history transcript is authoritative)"),
    ("mailbox-after", "post_process", "after", "mailbox message read/moved after import (post-process policy runs)"),
    ("db-proof", "blob_to_database", "after", "database terminal capture (redundant with the database transcript)"),
)
_VISUAL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
_VISUAL_MANIFEST = "visual-evidence-manifest.json"
_SYNTHETIC_NAME_MARKERS = (
    "synthetic",
    "mock",
    "placeholder",
    "sample",
    "generated",
    "fake",
    "fixture",
    "demo",
)
# Where each proof may legitimately be captured from.
_CAPTURE_METHODS_BY_KEY = {
    "mailbox-before": {"mailbox_browser"},
    "mailbox-after": {"mailbox_browser"},
    "blob-after": {"azure_portal", "storage_browser"},
    "documents-view": {"windows_browser"},
    "run-status": {"windows_browser"},
    "db-proof": {"windows_terminal"},
}


class StepFailure(RuntimeError):
    pass


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _docker_container_env(name: str) -> str:
    result = subprocess.run(
        ["docker", "exec", CONTAINER, "/opt/stats/runtime/bin/python", "-c",
         f"import os; print(os.environ.get({name!r}, ''))"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _http_get_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _container_email_get_json(path: str) -> dict:
    code = (
        "import os, urllib.request\n"
        f"url = 'http://127.0.0.1:8019{path}'\n"
        "headers = {'X-Stats-Internal-Key': os.environ.get('STATS_INTERNAL_API_KEY', '')}\n"
        "request = urllib.request.Request(url, headers=headers, method='GET')\n"
        "with urllib.request.urlopen(request, timeout=30) as response:\n"
        "    print(response.read().decode('utf-8', errors='replace'))\n"
    )
    result = subprocess.run(
        ["docker", "exec", CONTAINER, "/opt/stats/runtime/bin/python", "-c", code],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise urllib.error.URLError(result.stderr.strip() or "container-local M12 API request failed")
    return json.loads(result.stdout)


def _discover_latest_run(target: str, email_base: str, internal_key: str, run_id: str, source_id: str) -> dict | None:
    def get_json(path: str) -> dict:
        if target in {"local", "cloud"}:
            # Through the Stats Web proxy: local host proxy or cloud public ingress.
            return _http_get_json(f"{email_base}{path}", {"X-Stats-Internal-Key": internal_key})
        return _container_email_get_json(path)

    if not run_id:
        query = "?limit=10" + (f"&source_id={source_id}" if source_id else "")
        runs = get_json(f"/api/v1/email-ingestions/runs{query}").get("runs", [])
        if not runs:
            return None
        # Prefer the newest run that actually handed files off; fall back to newest.
        chosen = next((run for run in runs if (run.get("summary") or {}).get("handed_off_count", 0) > 0), runs[0])
        run_id = chosen.get("run_id", "")
        if not run_id:
            return None
    return get_json(f"/api/v1/email-ingestions/runs/{run_id}")


class Suite:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.rows: list[tuple[str, str, str]] = []  # (step, status, note/transcript)

    def record(self, step: str, status: str, note: str) -> None:
        self.rows.append((step, status, note))
        print(f"[{status}] {step} - {note}")

    def run_step(self, step: str, command: list[str], cwd: Path | None = None) -> None:
        transcript = self.output_dir / f"{step}.txt"
        print(f"\n=== {step} ===")
        print("Command:", " ".join(str(part) for part in command))
        result = subprocess.run(command, check=False, capture_output=True, text=True, cwd=cwd)
        output = (result.stdout or "") + (("\n[stderr]\n" + result.stderr) if result.stderr.strip() else "")
        transcript.write_text(output, encoding="utf-8")
        tail = "\n".join(output.strip().splitlines()[-15:])
        print(tail)
        if result.returncode != 0:
            self.record(step, "FAILED", f"see {transcript.name}")
            raise StepFailure(step)
        self.record(step, "PASSED", transcript.name)

    def summary(self, mode: str, verdict: str) -> str:
        lines = [
            "# M12 Evidence Suite Summary",
            "",
            f"Captured: {_dt.datetime.now().isoformat(timespec='seconds')}",
            f"Folder: {self.output_dir.name}",
            f"Mode: {mode}",
            f"Verdict: {verdict}",
            "",
            "| Step | Result | Transcript / Note |",
            "| --- | --- | --- |",
        ]
        lines += [f"| {step} | {status} | {note} |" for step, status, note in self.rows]
        lines += [
            "",
            "Required visual proofs (run-bound before/after data states): "
            + "; ".join(f"{key} = {label}" for key, _t, _p, label in VISUAL_PROOF_SET)
            + ". Machine-queryable states (run history, blob listing, SQL rows) are proven by the transcripts.",
            "",
        ]
        return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full M12 evidence chain with one command.")
    parser.add_argument("--run-id", default="", help="Import run id to prove. Default: newest handed-off run.")
    parser.add_argument("--source-id", default="", help="Optional source filter for run discovery.")
    parser.add_argument("--ingestion-id", default="", help="Override the handoff ingestion id for blob/database proof.")
    parser.add_argument("--skip-unit", action="store_true", help="Skip the pytest unit evidence step.")
    parser.add_argument("--skip-blob", action="store_true", help="Skip the Azure Blob listing step (needs az login).")
    parser.add_argument("--skip-database", action="store_true", help="Skip the Azure SQL database proof step.")
    parser.add_argument(
        "--prep",
        action="store_true",
        help="Diagnostic mode: skipped core proofs do not downgrade the result. NOT valid for acceptance evidence.",
    )
    parser.add_argument(
        "--visual-evidence-dir",
        default="",
        help="Folder holding the captured screenshot set and visual-evidence-manifest.json. Required for acceptance.",
    )
    parser.add_argument(
        "--allow-legacy-storage-reference",
        action="store_true",
        help="Pass through to the database proof: tolerate empty stats_documents.storage_reference for pre-fix ingests.",
    )
    parser.add_argument(
        "--target",
        choices=["local", "container", "cloud"],
        default="container",
        help=(
            "local: host Stats Web proxy. container: local stats-runtime. "
            "cloud: deployed Azure Container Apps runtime."
        ),
    )
    parser.add_argument(
        "--web-base-url",
        default="",
        help=(
            "Stats Web base URL. Required for --target cloud; defaults to "
            "http://127.0.0.1:8080 for --target local."
        ),
    )
    parser.add_argument("--output-dir", default="", help="Evidence output folder. Default: timestamped folder here.")
    args = parser.parse_args()

    if args.target == "cloud" and not args.web_base_url:
        print("FAIL: --web-base-url is required for --target cloud (the Container App public URL).")
        return 1
    web_base = (args.web_base_url or ("http://127.0.0.1:8080" if args.target == "local" else "")).rstrip("/")
    email_base = web_base if args.target in {"local", "cloud"} else LOCAL_EMAIL_BASE

    output_dir = Path(args.output_dir) if args.output_dir else RESULTS_DIR / f"m12-evidence-suite-{_timestamp()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    suite = Suite(output_dir)
    print("M12 Email Ingestion evidence suite")
    print(f"Target: {args.target}")
    if args.target in {"local", "cloud"}:
        print(f"Stats Web base URL: {web_base}")
    print(f"Evidence folder: {output_dir}")

    try:
        # 1. Automated test signal.
        if args.skip_unit:
            suite.record("unit", "SKIPPED", "--skip-unit")
        else:
            suite.run_step(
                "unit",
                [sys.executable, "-m", "pytest", "tests/unit/email_ingestion_module", "-q"],
                cwd=REPO_ROOT,
            )

        # 2. Runtime + UI privacy checks.
        runtime_command = [sys.executable, str(SCRIPT_DIR / "m12_email_ingestion_runtime_evidence_check.py")]
        if args.target in {"local", "cloud"}:
            runtime_command += ["--target", args.target, "--web-base-url", web_base]
        suite.run_step("runtime", runtime_command)

        # Discover the run to prove.
        if args.target in {"local", "cloud"}:
            internal_key = os.environ.get("STATS_INTERNAL_API_KEY") or os.environ.get("M12_INTERNAL_API_KEY") or ""
            key_note = f"set STATS_INTERNAL_API_KEY in this shell for the {args.target} run"
        else:
            internal_key = _docker_container_env("STATS_INTERNAL_API_KEY")
            key_note = "runtime container / internal key unavailable"
        run_detail = None
        if not internal_key:
            suite.record("discovery", "SKIPPED", key_note)
        else:
            try:
                run_detail = _discover_latest_run(args.target, email_base, internal_key, args.run_id, args.source_id)
            except (urllib.error.URLError, OSError) as exc:
                suite.record("discovery", "SKIPPED", f"run lookup failed: {exc}")
        if run_detail:
            run_id = run_detail.get("run_id", "")
            handoff_ids = [
                candidate.get("handoff_ingestion_id")
                for candidate in run_detail.get("candidates", [])
                if candidate.get("status") == "handed_off" and candidate.get("handoff_ingestion_id")
            ]
            suite.record("discovery", "PASSED", f"run_id={run_id}; handed_off={len(handoff_ids)}")
        else:
            run_id = args.run_id
            handoff_ids = []
        ingestion_id = args.ingestion_id or (handoff_ids[0] if handoff_ids else "")

        # 3. Run-history SQL evidence (works even for dry runs).
        history_command = [sys.executable, str(SCRIPT_DIR / "m12_email_ingestion_run_history_evidence_check.py")]
        if run_id:
            history_command += ["--run-id", run_id]
        elif args.source_id:
            history_command += ["--source-id", args.source_id]
        if args.target in {"local", "cloud"}:
            history_command += ["--target", args.target]
        suite.run_step("run_history", history_command)

        # 4. Blob after-proof for the imported PDF.
        if args.skip_blob:
            suite.record("blob", "SKIPPED", "--skip-blob")
        elif not ingestion_id:
            suite.record("blob", "SKIPPED", "no handed-off ingestion id found (dry run only?)")
        else:
            if args.target in {"local", "cloud"}:
                # az CLI runs locally either way; account/container come from the
                # local environment for host/cloud targets.
                account = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "")
                container = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "")
            else:
                account = _docker_container_env("AZURE_STORAGE_ACCOUNT_NAME")
                container = _docker_container_env("AZURE_STORAGE_CONTAINER_NAME")
            blob_command = [
                sys.executable, str(SCRIPT_DIR / "m12_email_ingestion_blob_evidence_check.py"),
                "--ingestion-id", ingestion_id,
            ]
            if account:
                blob_command += ["--account", account]
            if container:
                blob_command += ["--container", container]
            suite.run_step("blob", blob_command)

        # 5. Database proof for the same ingestion id.
        if args.skip_database:
            suite.record("database", "SKIPPED", "--skip-database")
        elif not ingestion_id:
            suite.record("database", "SKIPPED", "no handed-off ingestion id found (dry run only?)")
        else:
            database_command = [
                sys.executable, str(SCRIPT_DIR / "m12_email_ingestion_database_evidence_check.py"),
                "--ingestion-id", ingestion_id,
            ]
            if args.allow_legacy_storage_reference:
                database_command.append("--allow-legacy-storage-reference")
            if args.target in {"local", "cloud"}:
                database_command += ["--target", args.target]
            suite.run_step("database", database_command)

        # 6. Visual proof manifest (screenshots are captured manually but gated
        # here, bound to the run this suite just proved).
        _record_visual_evidence(suite, args.visual_evidence_dir, output_dir, run_id, run_detail)
    except StepFailure as failure:
        # Failure-stop rule: do not run later steps against a broken state.
        print(f"\nStopped at failed step: {failure} (see transcript in {output_dir.name})")
        mode = ("prep" if args.prep else "acceptance") + f" ({args.target})"
        (output_dir / "summary.md").write_text(suite.summary(mode, "FAILED"), encoding="utf-8")
        print("\n" + suite.summary(mode, "FAILED"))
        print("Result: FAILED")
        return 1

    mode = ("prep" if args.prep else "acceptance") + f" ({args.target})"
    failed = any(status == "FAILED" for _, status, _ in suite.rows)
    skipped_required = [step for step, status, _ in suite.rows if status == "SKIPPED" and step in REQUIRED_STEPS]
    if failed:
        verdict = "FAILED"
        exit_code = 1
    elif skipped_required and not args.prep:
        # Acceptance gate: core proof that never ran is not proof. The suite must
        # not report success without mailbox->Blob->database + visual evidence.
        verdict = "INCOMPLETE"
        exit_code = 2
    else:
        verdict = "PASSED"
        exit_code = 0
    (output_dir / "summary.md").write_text(suite.summary(mode, verdict), encoding="utf-8")
    print("\n" + suite.summary(mode, verdict))
    if verdict == "INCOMPLETE":
        print(
            "Core proof steps were skipped: " + ", ".join(skipped_required) + ". "
            "Provide the missing prerequisites (handed-off run, az login, --visual-evidence-dir) "
            "or re-run with --prep for a non-acceptance diagnostic."
        )
    print(f"Result: {verdict}")
    return exit_code


def _record_visual_evidence(
    suite: "Suite",
    visual_dir_arg: str,
    output_dir: Path,
    run_id: str = "",
    run_detail: dict | None = None,
) -> None:
    if not visual_dir_arg:
        suite.record("visual", "SKIPPED", "no --visual-evidence-dir provided")
        return
    visual_dir = Path(visual_dir_arg)
    if not visual_dir.is_dir():
        suite.record("visual", "FAILED", f"visual evidence folder not found: {visual_dir}")
        raise StepFailure("visual")
    visual_files = {
        entry.name: entry for entry in visual_dir.iterdir()
        if entry.is_file() and entry.suffix.lower() in _VISUAL_EXTENSIONS
    }
    manifest_path = visual_dir / _VISUAL_MANIFEST
    if not manifest_path.is_file():
        suite.record("visual", "FAILED", f"missing {_VISUAL_MANIFEST}; synthetic screenshots cannot be excluded")
        raise StepFailure("visual")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        suite.record("visual", "FAILED", f"invalid {_VISUAL_MANIFEST}: {exc}")
        raise StepFailure("visual")

    items = manifest.get("items")
    if not isinstance(items, list):
        suite.record("visual", "FAILED", f"{_VISUAL_MANIFEST} must contain an items array")
        raise StepFailure("visual")

    errors: list[str] = []

    # Run binding: before/after captures are only evidence when they provably
    # refer to the SAME import run and the same acted-upon file.
    manifest_run_id = str(manifest.get("run_id", "")).strip()
    subject_file = str(manifest.get("subject_file", "")).strip()
    if not manifest_run_id:
        errors.append("manifest must declare run_id (the import run these captures belong to)")
    elif run_id and manifest_run_id != run_id:
        errors.append(f"manifest run_id={manifest_run_id} does not match the proven run {run_id}")
    if not subject_file:
        errors.append("manifest must declare subject_file (the acted-upon PDF filename)")

    candidate_by_name: dict[str, dict] = {}
    if run_detail:
        for candidate in run_detail.get("candidates", []):
            name = candidate.get("filename")
            if name:
                candidate_by_name[name] = candidate
    if subject_file and candidate_by_name and subject_file not in candidate_by_name:
        errors.append(
            f"subject_file={subject_file} is not a candidate of the proven run "
            f"(run candidates: {', '.join(sorted(candidate_by_name))})"
        )
    manifest_sha = str(manifest.get("subject_sha256", "")).strip().lower()
    if manifest_sha and subject_file in candidate_by_name:
        candidate_sha = str(candidate_by_name[subject_file].get("sha256") or "").lower()
        if candidate_sha and manifest_sha != candidate_sha:
            errors.append("subject_sha256 does not match the run candidate's recorded content hash")

    required_keys = {key for key, _t, _p, _l in VISUAL_PROOF_SET}
    optional_keys = {key for key, _t, _p, _l in OPTIONAL_VISUAL_PROOFS}
    matched: dict[str, list[str]] = {key: [] for key in required_keys | optional_keys}
    declared_files: set[str] = set()
    file_hashes: dict[str, str] = {}

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"item {index} is not an object")
            continue
        proof_key = str(item.get("proof_key", "")).strip()
        filename = str(item.get("file", "")).strip()
        capture_method = str(item.get("capture_method", "")).strip()
        if proof_key not in required_keys | optional_keys:
            errors.append(f"item {index} has invalid proof_key={proof_key!r}")
        if not filename:
            errors.append(f"item {index} is missing file")
            continue
        declared_files.add(filename)
        file_path = visual_files.get(filename)
        if file_path is None:
            errors.append(f"item {index} file does not exist or is not an allowed visual file: {filename}")
        else:
            # Permanent text integrity anchor: nobody needs to re-open the image
            # to confirm it has not changed.
            file_hashes[filename] = hashlib.sha256(file_path.read_bytes()).hexdigest()
        lower_name = filename.lower()
        marker = next((token for token in _SYNTHETIC_NAME_MARKERS if token in lower_name), "")
        if marker:
            errors.append(f"item {index} file name looks synthetic ({marker}): {filename}")
        if item.get("synthetic") is not False:
            errors.append(f"item {index} must set synthetic=false")
        if item.get("live_capture") is not True:
            errors.append(f"item {index} must set live_capture=true")
        allowed_methods = _CAPTURE_METHODS_BY_KEY.get(proof_key, set())
        if allowed_methods and capture_method not in allowed_methods:
            errors.append(
                f"item {index} capture_method for {proof_key} must be one of " + ", ".join(sorted(allowed_methods))
            )
        if proof_key in matched:
            matched[proof_key].append(filename)

    undeclared_visuals = sorted(name for name in visual_files if name not in declared_files)
    if undeclared_visuals:
        errors.append(
            "all visual files must be listed in the manifest; undeclared file(s): "
            + ", ".join(undeclared_visuals)
        )
    for key, _transition, _phase, label in VISUAL_PROOF_SET:
        if not matched[key]:
            errors.append(f"missing required proof {key} ({label})")

    manifest_lines = [
        "Visual evidence manifest (run-bound before/after data-state proofs)",
        f"Folder: {visual_dir}",
        f"Manifest: {manifest_path}",
        f"Run binding: run_id={manifest_run_id or 'MISSING'} subject_file={subject_file or 'MISSING'}",
        "",
        "Required proofs (state surfaces this suite cannot query):",
    ]
    for key, transition, phase, label in VISUAL_PROOF_SET:
        status = ", ".join(matched[key]) if matched[key] else "MISSING"
        manifest_lines.append(f"- {key} [{transition}/{phase}] ({label}): {status}")
    optional_present = [(k, t, p, l) for k, t, p, l in OPTIONAL_VISUAL_PROOFS if matched[k]]
    if optional_present:
        manifest_lines += ["", "Optional proofs present:"]
        for key, transition, phase, label in optional_present:
            manifest_lines.append(f"- {key} [{transition}/{phase}] ({label}): {', '.join(matched[key])}")
    if file_hashes:
        manifest_lines += ["", "Capture integrity anchors (sha256):"]
        manifest_lines += [f"- {name}: {digest}" for name, digest in sorted(file_hashes.items())]
    if errors:
        manifest_lines += ["", "Validation errors:"]
        manifest_lines += [f"- {error}" for error in errors]
    (output_dir / "visual.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    if errors:
        suite.record(
            "visual", "FAILED",
            "visual evidence rejected (run binding / coverage / attestation - see visual.txt)",
        )
        raise StepFailure("visual")
    suite.record(
        "visual", "PASSED",
        f"run-bound before/after proofs complete ({len(required_keys)} required); manifest in visual.txt",
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Result: INTERRUPTED")
        sys.exit(130)


