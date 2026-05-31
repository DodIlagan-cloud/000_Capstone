<!-- M8 - Data Validation Module Start -->
<!-- Documents the transaction data validation runtime. -->

# Data Validation Module

This folder is the standalone home for the **M8 Data Validation Module** runtime.

It owns reusable transaction validation behavior:

- consuming transaction and financial field candidates from M7
- normalizing transaction dates, descriptions, currencies, and signed amounts
- checking incomplete, invalid, low-confidence, and duplicate records
- returning explicit data-quality findings and evaluation metadata
- returning validation-ready records for later Stats persistence

Transaction extraction, OCR, document parsing, Stats persistence, dashboards, workflow orchestration, and email retrieval remain outside this module.

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

<!-- M8 End -->
