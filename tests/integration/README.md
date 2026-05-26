# Integration Tests

<!-- M0 Foundation: cross-module test boundary. -->

Cross-module Stats workflow tests belong here.

Module-local tests should stay with the app or reusable module that owns the behavior. Integration tests should focus on contract handoffs, orchestration behavior, and end-to-end Stats workflows.
<<<<<<< Updated upstream
=======

<!-- M2 - Stats Web Shell Start -->
<!-- Documents the Stats Web local orchestration configuration checks. -->

## Stats Web Local Orchestration Tests

`test_stats_web_orchestration_config.py` verifies that the Stats Web shell registers the local sibling-service orchestrator and declares the Identity Access API plus the merged File Validation and Ingestion API as local services.

Run it with:

```powershell
pytest tests\integration\test_stats_web_orchestration_config.py
```

This test is intentionally configuration-focused. It proves the shell owns the local "one app" startup contract without leaving long-running API processes behind during ordinary automated test runs.

<!-- M2 End -->

<!-- M1/M3 Regression Start -->
<!-- Documents the live Stats database integration test switch. -->

## Live Database Tests

`test_live_identity_database.py` verifies the Identity Access Module against the configured live Stats database instead of the isolated SQLite unit-test database.

Run it only when the local PostgreSQL `stats` database is available:

```powershell
$env:RUN_LIVE_DATABASE_TESTS="1"
pytest tests\integration\test_live_identity_database.py
```

The test creates one uniquely named temporary user, authenticates that user, and deletes only that temporary user during cleanup. It does not drop tables or clear existing users.

<!-- M1/M3 Regression End -->
>>>>>>> Stashed changes
