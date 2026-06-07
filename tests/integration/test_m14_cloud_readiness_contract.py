# M14 - Cloud Readiness Start
# Verifies the M14 cloud deployment contract documentation.

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SPEC = REPO_ROOT / "docs" / "M14-cloud-readiness-module-spec.md"
FILE_INVENTORY = REPO_ROOT / "docs" / "M14-cloud-readiness-file-inventory.md"
CONTINUATION_PLAN = REPO_ROOT / "docs" / "M14-azure-development-continuation-plan.md"
CLOUD_DIR = REPO_ROOT / "infrastructure" / "cloud"
CLOUD_README = CLOUD_DIR / "README.md"
CLOUD_ENV_EXAMPLE = CLOUD_DIR / "azure-container-apps.env.example"
ADMIN_BOOTSTRAP_JOB = CLOUD_DIR / "bootstrap-stats-admin-containerapp-job.ps1"
PARK_CLOUD_DEV = CLOUD_DIR / "park-cloud-dev.ps1"
RESUME_CLOUD_DEV = CLOUD_DIR / "resume-cloud-dev.ps1"
RUNTIME_CONFIG = REPO_ROOT / "config" / "stats.runtime.json"


def read(path):
    return path.read_text(encoding="utf-8")


def test_m14_spec_exists():
    assert SPEC.exists(), f"M14 spec not found at {SPEC}"
    content = read(SPEC)
    assert "Module 14 Cloud Readiness" in content
    assert "Azure Container Apps" in content


def test_m14_file_inventory_exists():
    assert FILE_INVENTORY.exists(), f"M14 file inventory not found at {FILE_INVENTORY}"
    assert "M14 Cloud Readiness File Inventory" in read(FILE_INVENTORY)


def test_azure_development_continuation_plan_exists():
    assert CONTINUATION_PLAN.exists(), f"Azure continuation plan not found at {CONTINUATION_PLAN}"
    content = read(CONTINUATION_PLAN)
    assert "Azure SQL Database" in content
    assert "Microsoft Fabric" in content
    assert "Power BI" in content
    assert "Continue Development From Azure" in content
    assert "cost-conscious development loop" in content
    assert "Batch related runtime-affecting changes" in content
    assert "Optimize code/config before increasing CPU or memory" in content


def test_cloud_folder_and_notes_exist():
    assert CLOUD_DIR.exists(), f"Cloud folder not found at {CLOUD_DIR}"
    assert CLOUD_README.exists(), f"Cloud README not found at {CLOUD_README}"
    assert CLOUD_ENV_EXAMPLE.exists(), f"Cloud env example not found at {CLOUD_ENV_EXAMPLE}"
    assert ADMIN_BOOTSTRAP_JOB.exists(), f"Admin bootstrap job script not found at {ADMIN_BOOTSTRAP_JOB}"
    assert PARK_CLOUD_DEV.exists(), f"Cloud-dev parking script not found at {PARK_CLOUD_DEV}"
    assert RESUME_CLOUD_DEV.exists(), f"Cloud-dev resume script not found at {RESUME_CLOUD_DEV}"


def test_cloud_notes_document_required_azure_services():
    content = read(CLOUD_README)
    required_terms = [
        "Azure Container Apps",
        "Azure Container Registry",
        "Azure SQL Database",
        "Microsoft Fabric",
        "Power BI",
        "Azure Key Vault",
        "managed identity",
        "AzureBlobStorage",
        "/health",
        "stdout/stderr",
        "Secret Rotation",
    ]
    for term in required_terms:
        assert term in content, f"Cloud README must mention {term}"


def test_cloud_env_example_documents_required_variables():
    content = read(CLOUD_ENV_EXAMPLE)
    required_variables = [
        "STATS_ENVIRONMENT",
        "STATS_APP_ROOT",
        "STATS_RUNTIME_CONFIG",
        "STATS_PATHS_CONFIG",
        "STATS_LOGGING_CONFIG",
        "STATS_STORAGE_PROVIDER",
        "DATABASE_PROVIDER",
        "DATABASE_SCHEMA",
        "AZURE_SQL_CONNECTIONSTRING",
        "AZURE_SQL_SERVER",
        "AZURE_SQL_DATABASE",
        "ACCESS_TOKEN_SECRET_KEY",
        "CORS_ALLOWED_ORIGINS",
        "STATS_WEB_PORT",
        "ALLOW_OCR_FALLBACK",
        "OCR_ENGINE",
        "TESSERACT_CMD",
        "TESSDATA_PREFIX",
        "LOG_REDACT_SENSITIVE_VALUES",
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_STORAGE_CONTAINER_NAME",
        "AZURE_CLIENT_ID",
        "FABRIC_WORKSPACE_ID",
        "FABRIC_LAKEHOUSE_ID",
        "POWERBI_WORKSPACE_ID",
        "POWERBI_REPORT_ID",
        "POWERBI_TENANT_ID",
        "POWERBI_CLIENT_ID",
        "POWERBI_CLIENT_SECRET",
    ]
    for variable in required_variables:
        assert variable in content, f"Cloud env example must document {variable}"


def test_cloud_env_example_documents_azure_blob_storage():
    content = read(CLOUD_ENV_EXAMPLE)

    assert "STATS_STORAGE_PROVIDER=AzureBlobStorage" in content
    assert "Azure SQL for database persistence" in content
    assert "Azure Blob Storage for" in content
    assert "AZURE_STORAGE_CONNECTION_STRING=secretref:stats-storage-connection-string" in content


def test_cloud_env_example_uses_placeholders_not_real_secrets():
    content = read(CLOUD_ENV_EXAMPLE).lower()
    forbidden_fragments = [
        "statspass",
        "your_password",
        "replace-with-a-strong",
        "accountkey=",
        "sharedaccesssignature=",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in content, f"Cloud env example must not contain {fragment}"
    assert "secretref:" in content


def test_spec_documents_secret_boundary_and_live_deployment_limit():
    content = read(SPEC)
    assert "managed outside Git" in content
    assert "Live deployment evidence is intentionally manual" in content
    assert "subscription ownership" in content
    assert "budget approval" in content


def test_runtime_config_names_cloud_environment_example():
    config = json.loads(read(RUNTIME_CONFIG))
    assert config["configFiles"]["cloudEnvironmentExample"] == (
        "infrastructure/cloud/azure-container-apps.env.example"
    )
    assert "cloud" in config
    assert "STATS_ENVIRONMENT" in config["cloud"]


def test_runtime_config_cloud_secrets_are_marked_secret():
    config = json.loads(read(RUNTIME_CONFIG))
    assert config["database"]["DATABASE_PROVIDER"]["secret"] is False
    assert config["database"]["DATABASE_SCHEMA"]["secret"] is False
    assert config["database"]["AZURE_SQL_CONNECTIONSTRING"]["secret"] is True
    assert config["identity"]["ACCESS_TOKEN_SECRET_KEY"]["secret"] is True
    assert config["cloud"]["AZURE_STORAGE_CONNECTION_STRING"]["secret"] is True
    assert config["analytics"]["POWERBI_CLIENT_SECRET"]["secret"] is True


def test_admin_bootstrap_is_manual_container_app_job_not_startup():
    bootstrap = read(ADMIN_BOOTSTRAP_JOB)
    startup = read(REPO_ROOT / "infrastructure" / "containers" / "stats" / "start-stats-runtime.sh")
    runner = read(REPO_ROOT / "infrastructure" / "containers" / "stats" / "run-stats-admin-bootstrap.sh")
    cloud_readme = read(CLOUD_README)

    assert "az containerapp job create" in bootstrap
    assert "trigger-type Manual" in bootstrap
    assert "/app/run-stats-admin-bootstrap.sh" in bootstrap
    assert "app.scripts.create_admin" in runner
    assert "DEFAULT_ADMIN_EMAIL" in bootstrap
    assert "DEFAULT_ADMIN_PASSWORD=secretref:default-admin-password" in bootstrap
    assert "create_admin" not in startup
    assert "First Admin Bootstrap" in cloud_readme
    assert "Run this job only against a fresh database" in cloud_readme


def test_admin_bootstrap_uses_placeholder_subscription_id():
    bootstrap = read(ADMIN_BOOTSTRAP_JOB)

    assert "replace-with-subscription-id" in bootstrap
    assert "a9393569-82cd-48d5-8603-950471fea37a" not in bootstrap


def test_cloud_dev_rules_document_cost_optimized_deployment_controls():
    rules = read(REPO_ROOT / "docs" / "cloud-dev-development-rules.md")
    evidence = read(CLOUD_DIR / "cloud-dev-stage1-evidence.md")

    assert "Cost-Optimized Deployment Rules" in rules
    assert "Build and test the image locally before pushing to ACR" in rules
    assert "Keep `acrstatsdev001` on Basic SKU" in rules
    assert "single active revision" in rules
    assert "scale-to-zero/min-replica" in rules
    assert "Do not increase CPU or memory as a first response" in rules
    assert "prune old non-active tags" in rules
    assert "No new standing Azure resource cost" in rules
    assert "Cost Guardrails" in evidence
    assert "ACR SKU: `Basic`" in evidence
    assert "about 637 MB" in evidence


def test_cloud_dev_parking_scripts_keep_resources_and_control_scale():
    park = read(PARK_CLOUD_DEV)
    resume = read(RESUME_CLOUD_DEV)
    cloud_readme = read(CLOUD_README)

    assert "No resources will be deleted" in park
    assert "[int]$MinReplicas = 0" in park
    assert "[int]$MaxReplicas = 1" in park
    assert "--min-replicas $MinReplicas" in park
    assert "--max-replicas $MaxReplicas" in park

    assert "[int]$MinReplicas = 1" in resume
    assert "[int]$MaxReplicas = 1" in resume
    assert "/health" in resume
    assert "cloud-dev /health is healthy" in resume

    assert "Cloud-Dev Parking" in cloud_readme
    assert "Parking does not delete resources" in cloud_readme
    assert "min replicas: 0" in cloud_readme
    assert "max replicas: 1" in cloud_readme
    assert "Do not use parking scripts to delete" in cloud_readme

# M14 - Cloud Readiness End
