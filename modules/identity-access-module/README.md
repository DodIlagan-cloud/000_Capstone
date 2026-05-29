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

## Runtime

```powershell
docker compose --file infrastructure\compose\stats-runtime.compose.yml --env-file infrastructure\compose\.env.container up --build --detach
```

Official runtime verification runs inside the M13 Stats container.

## Tests

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

Host-side runs are development diagnostics only after M13.

## Configuration

Committed local defaults are stored in:

```text
config/defaults.env
```

Local secret/developer overrides may be placed in `.env`, which is ignored by repository rules.

<!-- M1 End -->
