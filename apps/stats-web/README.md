<!-- M1 - User Access Management Start -->
<!-- Documents the migrated Stats Web app consumer for Module 1 identity access. -->

# Stats Web

This folder is the migrated Stats Web application surface for the current M1 access flow.

It is an ASP.NET Core Razor Pages app that consumes the Identity Access API for:

- login
- first-login password setup
- authenticated main app landing access
- administrator user management

## Local Runtime

```powershell
cd C:\000_Capstone\apps\stats-web
dotnet run --urls "http://127.0.0.1:5013"
```

## Configuration

The Identity Access API target is configured in:

```text
appsettings.json
```

`StatsApi:BaseUrl` may also be overridden through the normal ASP.NET Core configuration pipeline or `STATS_API_BASE_URL`.

<!-- M1 End -->
