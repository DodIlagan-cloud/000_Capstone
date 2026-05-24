<!-- M3 - File Validation Module Start -->
<!-- Documents the standalone File Validation Module runtime and verification commands. -->

# File Validation Module

This folder is the standalone home for **M3 - File Validation Module**.

It owns reusable file validation behavior:

- file size checks
- empty file rejection
- filename extension normalization
- content signature detection
- extension/content mismatch findings
- allowed type and extension policy checks
- optional SHA-256 hash generation

Stats-specific upload screens and ingestion workflow state remain outside this module.

## Local Runtime

```powershell
cd C:\000_Capstone\modules\file-validation-module
python -m uvicorn app.main:app --host 127.0.0.1 --port 8014
```

## Local Tests

```powershell
cd C:\000_Capstone\modules\file-validation-module
pytest
```

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Local override values may be placed in `.env`, which is ignored by repository rules.

<!-- M3 End -->
