# Foundation Manual Test Checklist

Use this checklist when manually verifying the Foundation module without pytest.

## Setup

- [x] Open PowerShell.
- [x] Change directory to `C:\000_Capstone\stats\stats-ingestion-service`.
- [x] Confirm the application can be imported from `app.main`.

## Direct Verification

Run:

```powershell
python -c "from fastapi.testclient import TestClient; from app.main import app; from app.config import Settings; from app.db import init_db; c=TestClient(app); h=c.get('/health'); r=c.get('/'); s=Settings(); print('FOUNDATION TEST RUN'); print('app_title=' + app.title); print('health_status_code=' + str(h.status_code)); print('health_body=' + str(h.json())); print('root_status_code=' + str(r.status_code)); print('root_body=' + str(r.json())); print('settings_defaults=' + str({'app_name': s.app_name, 'app_version': s.app_version, 'api_prefix': s.api_prefix, 'max_file_size_mb': s.max_file_size_mb, 'allowed_extensions': s.allowed_extensions, 'database_url': s.database_url})); print('init_db_callable=' + str(callable(init_db)))"
```

## Expected Results

- [x] Application title is `Stats Ingestion Service`.
- [x] `/health` returns status code `200`.
- [x] `/health` returns service status `healthy`.
- [x] `/health` returns service name `Stats Ingestion Service`.
- [x] `/health` returns version `1.0.0`.
- [x] `/` returns status code `200`.
- [x] `/` returns service name `Stats Ingestion Service`.
- [x] `/` returns version `1.0.0`.
- [x] `/` returns message `Stats Ingestion Service is running`.
- [x] Settings defaults are loaded.
- [x] `init_db` is callable.

## Optional Browser Verification

Run:

```powershell
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
```

Expected outcome:

- [ ] `/health` displays the health response.
- [ ] `/` displays the root metadata response.
- [ ] `/docs` displays the generated FastAPI documentation.
