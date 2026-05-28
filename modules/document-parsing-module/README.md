<!-- M5 - Document Parsing Module Start -->
<!-- Documents the merged OCR/text extraction and document classification runtime. -->

# Document Parsing Module

This folder is the standalone home for the **M5 Document Parsing Module** runtime.

It owns reusable document parsing behavior:

- direct PDF text extraction
- Tesseract OCR fallback for scanned PDFs and supported images when configured
- document classification as bank statement, receipt, invoice, utility bill, or unknown
- parse quality and evaluation metadata
- redacted evidence previews for ethical data handling

File validation, ingestion records, transaction extraction, Stats persistence, dashboards, and email retrieval remain outside this module.

## Local Runtime

```powershell
cd $env:STATS_DOCUMENT_PARSING_MODULE_DIR
python -m uvicorn app.main:app --host 127.0.0.1 --port 8015
```

## Local Tests

```powershell
cd $env:STATS_DOCUMENT_PARSING_MODULE_DIR
pytest
```

## Testing Boundary (M13)

| Test type | Where to run | Tool |
| --- | --- | --- |
| Unit and contract tests | Host machine | `pytest` in this module directory |
| Acceptance / evidence (OCR end-to-end) | Docker stack | `tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1` |

Local `pytest` runs fast and gives immediate feedback during development. OCR is disabled locally by default (`ALLOW_OCR_FALLBACK=false`), so unit tests run without requiring a Tesseract installation on the host.

Full OCR acceptance evidence (JPEG/PNG → `strategy: tesseract_ocr`, scanned PDF → `method: ocr`) requires the M13 containerized runtime where Tesseract and all dependencies are installed. Run the Docker acceptance script from the project root after building the Stats runtime container.

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Local override values may be placed in `.env`, which should remain uncommitted.

Tesseract is a Stats runtime dependency made available to this module when OCR fallback is enabled. Local development may point to a desktop Tesseract install through `.env`; cloud/runtime portability belongs to the M13 top-level Stats container.

<!-- M5/M6 End -->
