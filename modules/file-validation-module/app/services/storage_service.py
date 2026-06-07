"""M3/M4 - File Intake Module Start
Stores accepted intake files through the configured Stats storage provider.
M3/M4 End"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LOCAL_FILE_SYSTEM = "localfilesystem"
AZURE_BLOB_STORAGE = "azureblobstorage"


@dataclass(frozen=True)
class StoredContent:
    content_reference: str


@dataclass(frozen=True)
class StorageSettings:
    provider: str
    storage_root: Path
    azure_account_name: str = ""
    azure_container_name: str = ""
    azure_connection_string: str = ""
    azure_blob_prefix: str = "intake"


def store_intake_content(
    *,
    content: bytes,
    ingestion_id: str,
    normalized_filename: str,
    content_type: str | None,
    settings: StorageSettings,
) -> StoredContent:
    """Store accepted intake content and return a durable reference."""
    provider = settings.provider.strip().lower()
    if provider == LOCAL_FILE_SYSTEM:
        return _store_local_file(
            content=content,
            ingestion_id=ingestion_id,
            normalized_filename=normalized_filename,
            storage_root=settings.storage_root,
        )
    if provider == AZURE_BLOB_STORAGE:
        return _store_azure_blob(
            content=content,
            ingestion_id=ingestion_id,
            normalized_filename=normalized_filename,
            content_type=content_type,
            settings=settings,
        )

    raise RuntimeError(f"Unsupported STATS_STORAGE_PROVIDER: {settings.provider}")


def _store_local_file(
    *,
    content: bytes,
    ingestion_id: str,
    normalized_filename: str,
    storage_root: Path,
) -> StoredContent:
    target_directory = storage_root / ingestion_id
    target_directory.mkdir(parents=True, exist_ok=True)
    target_file = target_directory / normalized_filename
    target_file.write_bytes(content)
    return StoredContent(content_reference=str(target_file))


def _store_azure_blob(
    *,
    content: bytes,
    ingestion_id: str,
    normalized_filename: str,
    content_type: str | None,
    settings: StorageSettings,
) -> StoredContent:
    if not settings.azure_container_name:
        raise RuntimeError("AZURE_STORAGE_CONTAINER_NAME is required when STATS_STORAGE_PROVIDER=AzureBlobStorage")
    if not settings.azure_connection_string:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required until managed identity storage auth is implemented")

    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError as exc:
        raise RuntimeError("azure-storage-blob is required when STATS_STORAGE_PROVIDER=AzureBlobStorage") from exc

    blob_prefix = settings.azure_blob_prefix.strip("/ ")
    blob_name = f"{blob_prefix}/{ingestion_id}/{normalized_filename}" if blob_prefix else f"{ingestion_id}/{normalized_filename}"
    service_client = BlobServiceClient.from_connection_string(settings.azure_connection_string)
    container_client = service_client.get_container_client(settings.azure_container_name)
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        content,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type) if content_type else None,
    )

    account_name = settings.azure_account_name or _account_name_from_url(getattr(blob_client, "url", ""))
    if account_name:
        return StoredContent(
            content_reference=f"azure-blob://{account_name}/{settings.azure_container_name}/{blob_name}"
        )

    return StoredContent(content_reference=f"azure-blob://{settings.azure_container_name}/{blob_name}")


def _account_name_from_url(url: str) -> str:
    marker = "https://"
    if not url.startswith(marker):
        return ""
    host = url[len(marker):].split("/", 1)[0]
    return host.split(".", 1)[0]
