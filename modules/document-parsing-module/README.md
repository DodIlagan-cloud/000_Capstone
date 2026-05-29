<!-- M5 - Document Parsing Module Start -->
<!-- Documents the merged OCR/text extraction and document classification runtime. -->

# Document Parsing Module

This folder is the standalone home for the **M5 Document Parsing Module** runtime.

It owns reusable document parsing behavior:

- direct PDF text extraction
- Tesseract OCR fallback for scanned PDFs and supported images when configured
- EXIF-aware image normalization, orientation retry, OCR preprocessing, and OCR quality scoring
- document classification as bank statement, receipt, invoice, utility bill, or unknown
- parse quality and evaluation metadata
- redacted evidence previews for ethical data handling

File validation, ingestion records, transaction extraction, Stats persistence, dashboards, and email retrieval remain outside this module.

## Runtime

```powershell
docker compose --file infrastructure\compose\stats-runtime.compose.yml --env-file infrastructure\compose\.env.container up --build --detach
```

M5 runs inside the M13 Stats runtime container for official verification.

## Tests

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

## Testing Boundary (M13)

| Test type | Where to run | Tool |
| --- | --- | --- |
| Unit and contract tests | Stats runtime container | `tests\scripts\regression\run_module_unit_tests.ps1` |
| Acceptance / evidence (OCR end-to-end) | Docker stack | `tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1` |

Host-side runs are development diagnostics only. Full OCR acceptance evidence for image files and scanned PDFs requires the M13 containerized runtime where Tesseract and all dependencies are installed.

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Local override values may be placed in `.env`, which should remain uncommitted.

Tesseract is a Stats runtime dependency made available to this module when OCR fallback is enabled. Cloud/runtime portability belongs to the M13 top-level Stats container.

Image OCR can be tuned through `OCR_PSM_VALUES`, `OCR_RETRY_ORIENTATIONS`, `OCR_MIN_CONFIDENCE`, `OCR_MIN_QUALITY_SCORE`, and `OCR_MIN_ALNUM_RATIO`. M5 records the selected orientation, selected PSM, attempt count, mean confidence, and quality score in parse metadata so downstream modules can evaluate OCR reliability.

<!-- M5/M6 End -->
