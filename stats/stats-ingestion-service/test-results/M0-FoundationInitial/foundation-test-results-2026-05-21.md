# Foundation Module Test Results

<!-- M0 Foundation: documented direct verification test result. -->

## Test Run Summary

| Field | Result |
| --- | --- |
| Module | Foundation |
| Service | Stats Ingestion Service |
| Test date | 2026-05-21 |
| Test method | Direct Python verification, no pytest |
| Working directory | `C:\000_Capstone\stats\stats-ingestion-service` |
| Overall result | Passed |

## Test Scope

This test run verified the Foundation module behaviours defined in the module specification:

- FastAPI application imports successfully.
- Root service metadata endpoint responds successfully.
- Health endpoint responds successfully.
- Default settings are available.
- Database initialization function is available.

## Test Command

```powershell
python -c "from fastapi.testclient import TestClient; from app.main import app; from app.config import Settings; from app.db import init_db; c=TestClient(app); h=c.get('/health'); r=c.get('/'); s=Settings(); print('FOUNDATION TEST RUN'); print('app_title=' + app.title); print('health_status_code=' + str(h.status_code)); print('health_body=' + str(h.json())); print('root_status_code=' + str(r.status_code)); print('root_body=' + str(r.json())); print('settings_defaults=' + str({'app_name': s.app_name, 'app_version': s.app_version, 'api_prefix': s.api_prefix, 'max_file_size_mb': s.max_file_size_mb, 'allowed_extensions': s.allowed_extensions, 'database_url': s.database_url})); print('init_db_callable=' + str(callable(init_db)))"
```

## Results

| Check | Expected | Actual | Status |
| --- | --- | --- | --- |
| App imports | App loads without import error | App loaded with title `Stats Ingestion Service` | Passed |
| `GET /health` status | `200` | `200` | Passed |
| `GET /health` body | Contains `status`, `service`, `version` | `{'status': 'healthy', 'service': 'Stats Ingestion Service', 'version': '1.0.0'}` | Passed |
| `GET /` status | `200` | `200` | Passed |
| `GET /` body | Contains `service`, `version`, `message` | `{'service': 'Stats Ingestion Service', 'version': '1.0.0', 'message': 'Stats Ingestion Service is running'}` | Passed |
| Settings defaults | Expected Foundation defaults available | Defaults loaded successfully | Passed |
| Database initializer | `init_db` is callable | `True` | Passed |

## Raw Output

```text
FOUNDATION TEST RUN
app_title=Stats Ingestion Service
health_status_code=200
health_body={'status': 'healthy', 'service': 'Stats Ingestion Service', 'version': '1.0.0'}
root_status_code=200
root_body={'service': 'Stats Ingestion Service', 'version': '1.0.0', 'message': 'Stats Ingestion Service is running'}
settings_defaults={'app_name': 'Stats Ingestion Service', 'app_version': '1.0.0', 'api_prefix': '/api/v1', 'max_file_size_mb': 50, 'allowed_extensions': ['pdf'], 'database_url': 'sqlite:///./stats_ingestion.db'}
init_db_callable=True
```

## Environmental Note

PowerShell printed a profile execution policy warning before running the command:

```text
File ... Microsoft.PowerShell_profile.ps1 cannot be loaded because running scripts is disabled on this system.
```

This warning did not prevent the Foundation checks from running and did not affect the application test result.

## Conclusion

The Foundation module passed the direct verification test. The application bootstrap, health route, root route, configuration defaults, and database initialization entry point are ready for later capstone modules to build on.
