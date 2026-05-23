<!-- M1 - User Access Management Start -->
<!-- Summarizes the Module 1 config-driven runtime regression evidence. -->

# M1 User Access Management Regression Test Results

## Test Run Summary

| Field | Result |
| --- | --- |
| Module | M1 - User Access Management |
| Regression change | Config-driven runtime values for backend settings and Stats Web API target |
| Parent session | `RegTest-ConfigDrivenRuntime-M0-M1` |
| Test date | 2026-05-23 |
| Working directory | `C:\000_Capstone\modules\identity-access-module` |
| Overall result | Passed |

## M0 Carry-Forward Decision

M0 was reviewed before execution and skipped because `test-results\M0-ArchitectureFoundation` already includes `M0-AF-04 Runtime values must not be hardcoded`, which specifically verifies the project-wide config-driven runtime rule.

## Results

| Check | Expected | Actual | Status |
| --- | --- | --- | --- |
| M1 automated regression slice | Auth, user management, and foundation config tests pass | `29 passed` | Passed |
| Stats Web build | ASP.NET Core Razor Pages frontend builds in Release mode | Build succeeded with 0 warnings and 0 errors | Passed |
| Backend config loading | Runtime database/API/CORS values come from config loader | Direct check reports configured values and `/stats` database target | Passed |
| Stats Web API target | API base URL comes from `appsettings.json` | Direct check reports `http://127.0.0.1:8013` | Passed |
| Visible backend API | Local API health endpoint is reachable | HTTP 200 | Passed |
| Visible Stats Web login | Local `.NET` login page is reachable | HTTP 200 | Passed |
| Protected auth route | Missing bearer token is rejected | Edge shows `Not authenticated` | Passed |
| Bootstrap admin first login | Password change is required before admin actions | Required flag `true`; user creation blocked before password setup | Passed |
| Admin after password setup | Administrator can create user after password change | HTTP 201 | Passed |
| Created user first login | Temporary-password user must change password | Required flag `true` | Passed |
| Focused visual evidence | Edge and terminal screenshots retained | Screenshots saved and reviewed | Passed |

## Saved Output

- Pytest raw output: `M1-UserAccessManagementRegression-test-raw-output-2026-05-23.txt`
- ASP.NET Core build output: `M1-UserAccessManagementRegression-dotnet-build-output-2026-05-23.txt`
- Direct verification output: `M1-UserAccessManagementRegression-direct-check-output-2026-05-23.txt`
- Screenshot index: `M1-UserAccessManagementRegression-screenshot-evidence-2026-05-23.md`

## Conclusion

M1 regression passed after the config-driven runtime refactor. Backend settings, Stats Web API routing, login availability, protected-route rejection, bootstrap admin password setup, and temporary-password user behavior remain working.

<!-- M1 End -->
