# Local Test Fixtures

Place local PDF, PNG, JPG, or JPEG fixtures here for Docker evidence and module test runs.

This directory is the required source for Stats module test data. Unit, API, regression, acceptance, and evidence tests that exercise document, OCR, extraction, validation, ingestion, storage, or workflow functionality must use files from this directory through the configured path, normally `STATS_TESTDATA_DIR`.

Synthetic inline data should not be used as the primary proof of module functionality. If a narrow edge-case test needs a controlled payload, the test must state that it is derived from or complements the real `tests/input` fixture behavior and must not replace the real-data test.

The real fixture files in this folder are ignored by Git. Keep only this README in source control.
