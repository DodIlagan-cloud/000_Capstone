"""M12 Email Ingestion runtime evidence check.

Targets:
- local: host-running Stats Web + module APIs. API calls go through the Stats Web
  proxy by default, matching cloud ingress behavior. The internal key comes from
  the LOCAL environment (STATS_INTERNAL_API_KEY).
- container (default): local stats-runtime container (Stats Web http://127.0.0.1:8080,
  M12 API http://127.0.0.1:8019). Reads the internal key via docker exec and proves
  central secret resolution in-process.
- cloud: the deployed Azure Container Apps runtime. All calls go through the Stats
  Web public URL (the proxy fronts every module on one ingress), the internal key
  comes from the LOCAL environment (STATS_INTERNAL_API_KEY), and secret proof is
  API-level (secret_ref present + saved-secret test-connection), since there is no
  shell access into the replica.

    python m12_email_ingestion_runtime_evidence_check.py --target cloud \
        --web-base-url https://ca-stats-dev-001.<env>.azurecontainerapps.io

Never prints secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


CONTAINER = "stats-runtime"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def http_get(url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def http_post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def docker_exec_python(code: str) -> str:
    command = ["docker", "exec", CONTAINER, "/opt/stats/runtime/bin/python", "-c", code]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"docker exec failed: {result.stderr.strip()}")
    return result.stdout.strip()


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(f"{label} did not contain expected text: {needle}")
    print(f"PASS: {label} contains {needle!r}")


def assert_not_contains(text: str, needle: str, label: str) -> None:
    if needle in text:
        fail(f"{label} contained forbidden text: {needle}")
    print(f"PASS: {label} does not contain {needle!r}")


def _internal_key(target: str) -> str:
    if target in {"local", "cloud"}:
        key = os.environ.get("STATS_INTERNAL_API_KEY") or os.environ.get("M12_INTERNAL_API_KEY") or ""
        if not key:
            fail(
                f"Set STATS_INTERNAL_API_KEY in the local environment for the {target} evidence run "
                f"(the {target} target has no docker exec path to read it)."
            )
        return key
    key = docker_exec_python("import os; print(os.environ.get('STATS_INTERNAL_API_KEY', ''))")
    if not key:
        fail("runtime container does not expose STATS_INTERNAL_API_KEY for protected M12 evidence calls")
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="M12 runtime/UI/privacy evidence check.")
    parser.add_argument("--target", choices=["local", "container", "cloud"], default="container")
    parser.add_argument(
        "--web-base-url",
        default="",
        help=(
            "Stats Web base URL. Required for --target cloud; defaults to "
            "http://127.0.0.1:8080 for --target local."
        ),
    )
    args = parser.parse_args()

    if args.target == "cloud":
        if not args.web_base_url:
            fail("--web-base-url is required for --target cloud (the Container App public URL).")
        web_base = args.web_base_url.rstrip("/")
        email_base = web_base  # M12 API is reached through the Stats Web proxy.
    elif args.target == "local":
        web_base = (args.web_base_url or "http://127.0.0.1:8080").rstrip("/")
        email_base = web_base  # Match cloud: reach M12 through Stats Web proxy.
    else:
        web_base = "http://127.0.0.1:8080"
        email_base = "http://127.0.0.1:8019"

    print("M12 Email Ingestion runtime evidence check")
    print(f"Target: {args.target}")
    print(f"Stats Web: {web_base}")
    print(f"Email API: {email_base if args.target == 'container' else email_base + ' (via Stats Web proxy)'}")
    if args.target == "container":
        print(f"Runtime container: {CONTAINER}")

    internal_key = _internal_key(args.target)
    email_auth_headers = {"X-Stats-Internal-Key": internal_key}
    # The Stats Web proxy requires the CSRF header on state-changing calls.
    post_headers = {**email_auth_headers, "X-Stats-CSRF": "1"}

    if args.target == "container":
        status, health_text = http_get(f"{email_base}/health")
        if status != 200:
            fail(f"Email health returned HTTP {status}: {health_text[:200]}")
        health = json.loads(health_text)
        if health.get("status") != "healthy":
            fail(f"Email health was not healthy: {health}")
        print("PASS: Email Ingestion health endpoint is healthy")
    # local/cloud: /health is not part of the public Stats Web proxy contract; the
    # authenticated sources call below proves M12 through the same ingress shape.

    status, setup_html = http_get(f"{web_base}/EmailSetup")
    if status != 200:
        fail(f"Email Setup returned HTTP {status}")
    assert_contains(setup_html, "email-app-password-hint", "Email Setup HTML")
    assert_contains(setup_html, "email-sources-pagination", "Email Setup HTML")
    assert_contains(setup_html, "email-run-pagination", "Email Setup HTML")
    assert_contains(setup_html, "email-ingest-db-button", "Email Setup HTML")
    assert_contains(setup_html, "Ingest to database", "Email Setup HTML")
    assert_not_contains(setup_html, "email-imap-port", "Email Setup HTML")
    assert_not_contains(setup_html, "email-imap-ssl", "Email Setup HTML")
    assert_not_contains(setup_html, "Use SSL", "Email Setup HTML")
    assert_not_contains(setup_html, "IMAP port", "Email Setup HTML")

    status, setup_js = http_get(f"{web_base}/js/email-setup.js")
    if status != 200:
        fail(f"Email Setup JS returned HTTP {status}")
    assert_contains(setup_js, "Saved mailbox app password is available", "Email Setup JS")
    assert_contains(setup_js, "SOURCES_PAGE_SIZE = 10", "Email Setup JS")
    assert_contains(setup_js, "RUN_PAGE_SIZE = 10", "Email Setup JS")
    assert_contains(setup_js, 'textContent = "Select"', "Email Setup JS")
    assert_contains(setup_js, "mailbox_folder: sourceForm.elements.folder.value", "Email Setup JS")
    assert_contains(setup_js, "/api/v1/email-ingestions/process-imported", "Email Setup JS")
    assert_contains(setup_js, "latestImportRunId", "Email Setup JS")
    assert_contains(setup_js, "run_id: latestImportRunId", "Email Setup JS")
    assert_not_contains(setup_js, 'textContent = "Edit"', "Email Setup JS")

    status, sources_text = http_get(f"{email_base}/api/v1/email-ingestion-sources", headers=email_auth_headers)
    if status != 200:
        fail(f"Source profile API returned HTTP {status}: {sources_text[:200]}")
    if args.target != "container":
        print(f"PASS: M12 source API reachable through the {args.target} Stats Web ingress with the internal key")
    assert_not_contains(sources_text, "app_password", "Source profile API response")
    sources = json.loads(sources_text).get("sources", [])
    print(f"INFO: source profile count = {len(sources)}")

    if not sources:
        print("SKIP: no configured source profile found for saved-secret connection proof")
    else:
        source = sources[0]
        source_id = source["source_id"]
        folder = source.get("folder") or "Inbox"
        secret_ref = source.get("secret_ref")
        print(f"INFO: selected source = {source_id}")
        print(f"INFO: selected source email = {source.get('email_address')}")
        print(f"INFO: selected source secret_ref = {secret_ref}")
        if not secret_ref:
            fail("selected source has no secret_ref")

        if args.target == "container":
            secret_probe = docker_exec_python(
                "import sys; sys.path.insert(0, '/app/modules/email-ingestion-module'); "
                "from app.services.source_profile_service import list_source_profiles; "
                "from app.services.secret_service import resolve_secret; "
                "sources=list_source_profiles().sources; "
                "print('\\n'.join(f'{s.source_id}|secret_ref={s.secret_ref}|secret_available={bool(resolve_secret(s.secret_ref))}' for s in sources))"
            )
            print("INFO: central secret availability by source")
            print(secret_probe)
            if f"{source_id}|secret_ref={secret_ref}|secret_available=True" not in secret_probe:
                fail("selected source secret did not resolve from the runtime secret provider")
        else:
            print(
                f"INFO: {args.target} target has no in-replica probe; the saved-secret proof is the "
                "blank-password test-connection below resolving the secret by reference."
            )

        status, test_text = http_post_json(
            f"{email_base}/api/v1/email-ingestion-sources/{source_id}/test-connection",
            {"folder": folder},
            headers=post_headers,
        )
        if status != 200:
            fail(f"test connection returned HTTP {status}: {test_text[:300]}")
        test_result = json.loads(test_text)
        if "secret is not available" in test_result.get("message", "").lower():
            fail("test connection reported missing saved secret")
        print(f"PASS: test connection used saved secret path; status={test_result.get('status')}; folder={test_result.get('folder')}")

    print("Result: PASSED")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Result: INTERRUPTED")
        sys.exit(130)
