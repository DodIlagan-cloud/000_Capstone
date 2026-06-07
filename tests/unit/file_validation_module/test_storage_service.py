"""M3/M4 - File Intake Module Start
Tests configured storage providers for accepted real intake files.
M3/M4 End"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import pytest

from app.services.storage_service import StorageSettings, store_intake_content


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_store_intake_content_uses_local_file_system_with_real_input_fixture(tmp_path):
    fixture_file = _real_input_file()
    content = fixture_file.read_bytes()

    result = store_intake_content(
        content=content,
        ingestion_id=f"ingestion-{fixture_file.stem.lower()}",
        normalized_filename=fixture_file.name,
        content_type=mimetypes.guess_type(fixture_file.name)[0],
        settings=StorageSettings(
            provider="LocalFileSystem",
            storage_root=tmp_path,
        ),
    )

    stored_path = Path(result.content_reference)
    assert stored_path.read_bytes() == content
    assert stored_path.name == fixture_file.name
    assert stored_path.parent.name == f"ingestion-{fixture_file.stem.lower()}"


def test_store_intake_content_uploads_real_input_fixture_to_configured_azure_blob():
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "").strip()
    if not connection_string or not container_name:
        pytest.skip("Set AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER_NAME for live Blob storage test.")

    pytest.importorskip("azure.storage.blob")

    fixture_file = _real_input_file()
    content = fixture_file.read_bytes()
    account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "").strip() or None
    blob_prefix = os.environ.get("AZURE_STORAGE_BLOB_PREFIX", "intake-test").strip()
    ingestion_id = f"ingestion-{fixture_file.stem.lower()}"

    result = store_intake_content(
        content=content,
        ingestion_id=ingestion_id,
        normalized_filename=fixture_file.name,
        content_type=mimetypes.guess_type(fixture_file.name)[0],
        settings=StorageSettings(
            provider="AzureBlobStorage",
            storage_root=REPO_ROOT / "apps" / "stats-data" / "data" / "intake",
            azure_account_name=account_name,
            azure_container_name=container_name,
            azure_connection_string=connection_string,
            azure_blob_prefix=blob_prefix,
        ),
    )

    assert result.content_reference.startswith("azure-blob://")
    assert f"/{container_name}/" in result.content_reference
    assert f"/{blob_prefix}/{ingestion_id}/{fixture_file.name}" in result.content_reference


def _real_input_file() -> Path:
    configured = os.environ.get("STATS_TESTDATA_DIR")
    input_dir = Path(configured) if configured else REPO_ROOT / "tests" / "input"
    if not input_dir.exists():
        pytest.skip(f"Configured real test-data directory does not exist: {input_dir}")

    explicit_fixture = os.environ.get("STATS_STORAGE_TEST_FIXTURE")
    if explicit_fixture:
        fixture_file = Path(explicit_fixture)
        if not fixture_file.is_absolute():
            fixture_file = input_dir / fixture_file
        if not fixture_file.exists():
            pytest.skip(f"Configured STATS_STORAGE_TEST_FIXTURE does not exist: {fixture_file}")
        return fixture_file

    suffixes = {".pdf", ".png", ".jpg", ".jpeg"}
    files = [path for path in sorted(input_dir.iterdir()) if path.is_file() and path.suffix.lower() in suffixes]
    if not files:
        pytest.skip(f"No real document fixtures found in configured test-data directory: {input_dir}")

    return sorted(files, key=lambda path: (path.suffix.lower() != ".pdf", path.name.lower()))[0]
