<!-- M1 - User Access Management Start -->
<!-- Documents the migrated Stats Web app consumer for Module 1 identity access. -->

# Stats Web

This folder is the migrated Stats Web application surface for the current M1 access flow.

It is an ASP.NET Core Razor Pages app that consumes the Identity Access API for:

- login
- first-login password setup
- authenticated main app landing access
- administrator user management

## Runtime Boundary

From M13 onward, official Stats Web runtime verification and evidence run through the Docker stack at `http://127.0.0.1:8080`. Host-started `dotnet run` is historical diagnostic usage only and must not be recorded as module completion, regression, browser evidence, or capstone evidence.

## Local Page Development

For Razor, CSS, and browser-JS page changes, use the local-development Compose override so the host-started web app can call the real container module APIs without rebuilding the image for each visual edit.

Start or recreate the runtime with module API ports exposed:

```powershell
docker compose --env-file infrastructure\compose\.env.container `
  -f infrastructure\compose\stats-runtime.compose.yml `
  -f infrastructure\compose\stats-runtime.local-dev.override.yml `
  up -d stats
```

Then start Stats Web locally on a separate port:

```powershell
.\apps\stats-web\start-local-dev.ps1
```

Use `http://127.0.0.1:8081` for local page iteration. Rebuild `stats-runtime:local` only after the page changes are approved.

## Configuration

The Identity Access API target is configured in:

```text
appsettings.json
```

`StatsApi:BaseUrl` may also be overridden through the normal ASP.NET Core configuration pipeline or `STATS_API_BASE_URL`.

<!-- M1 End -->
