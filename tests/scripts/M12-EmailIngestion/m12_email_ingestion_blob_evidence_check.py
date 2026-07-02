"""M12 Email Ingestion Blob evidence check.

Run after a real Email Setup "Run import" to prove accepted email PDFs reached
the configured Azure Blob intake container. The script prints blob metadata only;
it does not print storage connection strings, keys, tokens, or file contents.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def run_az(args: list[str]) -> str:
    result = subprocess.run(["az", *args], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        fail(f"az {' '.join(args[:2])} failed: {stderr or result.stdout.strip()}")
    return result.stdout.strip()


def env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="List imported M12 email blobs for screenshot evidence.")
    parser.add_argument("--account", default=env_value("AZURE_STORAGE_ACCOUNT_NAME"), help="Azure Storage account name.")
    parser.add_argument("--container", default=env_value("AZURE_STORAGE_CONTAINER_NAME"), help="Blob container name.")
    parser.add_argument(
        "--prefix",
        default=env_value("AZURE_STORAGE_BLOB_PREFIX") or "intake",
        help="Blob prefix used by the file intake storage provider.",
    )
    parser.add_argument(
        "--ingestion-id",
        default="",
        help="Optional M3/M4 ingestion id from the Email Setup run result or handoff log.",
    )
    parser.add_argument(
        "--expected-filename",
        default="",
        help="Optional imported PDF filename to require in the blob list.",
    )
    parser.add_argument("--max-results", type=int, default=20, help="Maximum blobs to print.")
    args = parser.parse_args()

    if not args.account:
        fail("AZURE_STORAGE_ACCOUNT_NAME or --account is required.")
    if not args.container:
        fail("AZURE_STORAGE_CONTAINER_NAME or --container is required.")

    prefix = args.prefix.strip("/")
    if args.ingestion_id:
        prefix = f"{prefix}/{args.ingestion_id.strip('/')}"

    print("M12 Email Ingestion Blob evidence check")
    print(f"Storage account: {args.account}")
    print(f"Container: {args.container}")
    print(f"Blob prefix: {prefix}")
    if args.expected_filename:
        print(f"Expected filename: {args.expected_filename}")

    account_text = run_az(
        [
            "storage",
            "account",
            "show",
            "--name",
            args.account,
            "--query",
            "{name:name,resourceGroup:resourceGroup,location:primaryLocation,kind:kind}",
            "--output",
            "json",
        ]
    )
    account = json.loads(account_text)
    print(
        "Account proof: "
        f"name={account.get('name')} resourceGroup={account.get('resourceGroup')} "
        f"location={account.get('location')} kind={account.get('kind')}"
    )

    blobs_text = run_az(
        [
            "storage",
            "blob",
            "list",
            "--account-name",
            args.account,
            "--container-name",
            args.container,
            "--prefix",
            prefix,
            "--auth-mode",
            "login",
            "--num-results",
            str(max(1, args.max_results)),
            "--query",
            "[].{name:name,size:properties.contentLength,contentType:properties.contentSettings.contentType,lastModified:properties.lastModified}",
            "--output",
            "json",
        ]
    )
    blobs = json.loads(blobs_text or "[]")

    if not blobs:
        fail("No blobs were found for the configured prefix. Check the Run import handoff content_reference.")

    print(f"Blob rows: {len(blobs)}")
    for index, blob in enumerate(blobs, start=1):
        print(
            f"{index}. name={blob.get('name')} size={blob.get('size')} "
            f"contentType={blob.get('contentType')} lastModified={blob.get('lastModified')}"
        )

    if args.expected_filename:
        expected = args.expected_filename.lower()
        if not any(str(blob.get("name", "")).lower().endswith(expected) for blob in blobs):
            fail(f"Expected filename was not found under prefix: {args.expected_filename}")

    print("Result: PASSED")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Result: INTERRUPTED")
        sys.exit(130)
