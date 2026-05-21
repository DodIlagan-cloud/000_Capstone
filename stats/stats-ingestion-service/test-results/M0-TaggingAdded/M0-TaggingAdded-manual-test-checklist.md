# M0 TaggingAdded Manual Test Checklist

Use this checklist when manually verifying the M0 Foundation module after the TaggingAdded update.

## Setup

- [x] Open PowerShell.
- [x] Change directory to `C:\000_Capstone\stats\stats-ingestion-service`.
- [x] Confirm the application can be imported from `app.main`.

## Automated Verification

Run:

```powershell
pytest
```

Expected:

- [x] `tests/test_foundation.py` passes.
- [x] `tests/test_ingest.py` passes.
- [x] `tests/test_main.py` passes.
- [x] Overall result is `9 passed`.

## Direct Verification

Run:

```powershell
python test-results\M0-TaggingAdded\M0-TaggingAdded_terminal_check.py
```

Expected:

- [x] Application title is `Stats Ingestion Service`.
- [x] `/health` returns status code `200`.
- [x] `/health` returns service status `healthy`.
- [x] `/health` returns service name `Stats Ingestion Service`.
- [x] `/health` returns version `1.0.0`.
- [x] `/` returns status code `200`.
- [x] `/` returns service name `Stats Ingestion Service`.
- [x] `/` returns version `1.0.0`.
- [x] `/` returns message `Stats Ingestion Service is running`.
- [x] Result displays `PASSED`.

## Browser Verification

Run:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
```

Expected:

- [x] `/health` displays the health JSON response.
- [x] `/` displays the root metadata JSON response.
- [x] `/docs` displays the generated FastAPI documentation.

## Evidence Helper Verification

Run from `C:\000_Capstone`:

```powershell
python skills\module-test-evidence\scripts\crop_screenshots.py --help
```

Expected:

- [x] The helper displays CLI usage and options.
