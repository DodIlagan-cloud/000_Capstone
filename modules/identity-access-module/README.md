<!-- M1 - User Access Management Start -->
<!-- Documents the migrated standalone Identity Access Module runtime and verification commands. -->

# Identity Access Module

This folder is the migrated standalone home for **M1 - User Access Management**.

It owns reusable identity behavior:

- email/password login
- bearer token creation and validation
- current-user profile access
- first-login password-change enforcement
- role-based administrator checks
- administrator user creation, listing, reading, and updating

Stats-specific Razor Pages remain outside this module in `apps/stats-web/`.

## Local Runtime

```powershell
cd C:\000_Capstone\modules\identity-access-module
python -m uvicorn app.main:app --host 127.0.0.1 --port 8013
```

## Local Tests

```powershell
cd C:\000_Capstone\modules\identity-access-module
pytest
```

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Local secret/developer overrides may be placed in `.env`, which is ignored by repository rules.

<!-- M1 End -->
