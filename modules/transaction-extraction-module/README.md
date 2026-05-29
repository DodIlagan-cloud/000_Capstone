<!-- M7 - Transaction Extraction Module Start -->
<!-- Documents the transaction candidate extraction runtime. -->

# Transaction Extraction Module

This folder is the standalone home for the **M7 Transaction Extraction Module** runtime.

It owns reusable transaction extraction behavior:

- consuming parsed text and classification context from M5
- detecting transaction-like candidate rows
- detecting document-level financial field candidates
- returning source line/page and confidence metadata
- returning explicit findings for missing, ambiguous, unsupported, or low-confidence extraction states
- exposing evaluation metadata for later evidence

OCR, document classification, file validation, ingestion records, record cleaning, duplicate detection, Stats persistence, dashboards, and email retrieval remain outside this module.

## Runtime

```powershell
docker compose --file infrastructure\compose\stats-runtime.compose.yml --env-file infrastructure\compose\.env.container up --build --detach
```

Official runtime verification runs inside the M13 Stats container.

## Tests

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

Host-side runs are development diagnostics only after M13.

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Local override values may be placed in `.env`, which should remain uncommitted.

<!-- M7 End -->
