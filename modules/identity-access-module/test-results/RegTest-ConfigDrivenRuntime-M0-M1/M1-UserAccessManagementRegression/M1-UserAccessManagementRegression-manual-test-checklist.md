<!-- M1 - User Access Management Start -->
<!-- Records the manual checklist for the Module 1 config-driven runtime regression pass. -->

# M1 User Access Management Regression Manual Test Checklist

| Check | Evidence | Result |
| --- | --- | --- |
| Review M0 config evidence before rerun decision | `C:\000_Capstone\test-results\M0-ArchitectureFoundation\M0-ArchitectureFoundation-test-results-2026-05-23.md` | Passed; M0 rerun skipped |
| Run M1 automated regression slice | `M1-UserAccessManagementRegression-test-raw-output-2026-05-23.txt` | Passed |
| Build Stats Web frontend | `M1-UserAccessManagementRegression-dotnet-build-output-2026-05-23.txt` | Passed |
| Verify backend config-driven runtime values | `M1-UserAccessManagementRegression-direct-check-output-2026-05-23.txt` | Passed |
| Verify Stats Web configured API target | `M1-UserAccessManagementRegression-direct-check-output-2026-05-23.txt` | Passed |
| Verify visible API health endpoint | Direct output and Edge/API evidence | Passed |
| Verify visible Stats Web login page | Edge screenshot | Passed |
| Verify protected current-user endpoint rejects missing token | Edge screenshot | Passed |
| Verify first-login password change gating | Direct output | Passed |
| Verify admin can add user after password change | Direct output | Passed |
| Verify created user must change password on first login | Direct output | Passed |

<!-- M1 End -->
