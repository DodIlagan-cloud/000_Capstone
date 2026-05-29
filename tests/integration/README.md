# Integration Tests

<!-- M13 - Containerization Start -->
<!-- Documents the container-first integration test boundary. -->

Cross-module Stats workflow tests belong here.

From M13 onward, official integration and contract checks must run inside the Stats runtime container through:

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

Host-side execution of these tests is a development diagnostic only. Any result used for module completion, regression, or assessment evidence must be repeated inside `stats-runtime`.

## Current Integration Checks

| Test | Purpose |
| --- | --- |
| `test_stats_web_orchestration_config.py` | Verifies Stats Web orchestration and downstream service configuration. |
| `test_live_identity_database.py` | Historical live database diagnostic; official DB verification runs through Docker/Compose. |
| `test_m13_containerization_contract.py` | Verifies the containerization contract and container-first testing policy. |

<!-- M13 End -->
