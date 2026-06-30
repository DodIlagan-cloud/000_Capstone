<!-- M12 - Email Ingestion Module Start -->

# Email Ingestion Module

This folder is the standalone home for the **M12 Email Ingestion** runtime.

It owns reusable email-source behavior:

- mailbox retrieval request contracts
- attachment candidate filtering
- email source metadata normalization
- automated attachment handoff preparation
- optional handoff into the File Validation and Ingestion API
- duplicate/skipped/failed intake status reporting

Stats-specific UI screens, product persistence, OCR, transaction extraction, dashboards, and mailbox secret management remain outside this module.

## Runtime

```powershell
docker compose --file infrastructure\compose\stats-runtime.compose.yml --env-file infrastructure\compose\.env.container up --build --detach
```

Official runtime verification runs inside the M13 Stats container.

## Tests

```powershell
pytest tests\unit\email_ingestion_module
```

Host-side runs are development diagnostics only after M13.

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Real mailbox tokens, Graph credentials, refresh tokens, and webhook secrets must come from ignored local environment files, Azure Container Apps secrets, or Key Vault. They must not be committed.

<!-- M12 End -->
