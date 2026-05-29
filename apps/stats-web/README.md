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

## Configuration

The Identity Access API target is configured in:

```text
appsettings.json
```

`StatsApi:BaseUrl` may also be overridden through the normal ASP.NET Core configuration pipeline or `STATS_API_BASE_URL`.

<!-- M1 End -->
