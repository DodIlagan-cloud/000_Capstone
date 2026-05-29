<!-- M3 - File Validation Module Start -->
<!-- Documents the merged File Validation and Ingestion Module runtime and verification commands. -->

# File Validation and Ingestion Module

This folder is the standalone home for the merged **M3 File Validation** and **M4 File Ingestion** runtime.

It owns reusable document intake behavior:

- file size checks
- empty file rejection
- filename extension normalization
- content signature detection
- extension/content mismatch findings
- allowed type and extension policy checks
- optional SHA-256 hash generation
- ingestion record creation for validation-accepted files
- idempotency and duplicate-submission handling
- configured storage handoff references
- ingestion status lookup

Stats-specific upload screens, product persistence, OCR, classification, extraction, and reporting remain outside this module.

## Runtime

<!-- M13 - Containerization Start -->
```powershell
docker compose --file infrastructure\compose\stats-runtime.compose.yml --env-file infrastructure\compose\.env.container up --build --detach
```

Official runtime verification runs inside the M13 Stats container.
<!-- M13 End -->

## Tests

<!-- M13 - Containerization Start -->
```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

Host-side runs are development diagnostics only after M13.
<!-- M13 End -->

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Local override values may be placed in `.env`, which is ignored by repository rules.

Accepted intake files are stored under the configured `STORAGE_ROOT`:

```text
<STORAGE_ROOT>\<ingestion_id>\<normalized_filename>
```

<!-- M3 End -->
