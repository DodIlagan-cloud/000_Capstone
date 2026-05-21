<!-- Project Environment Setup Start -->
<!-- Documents local developer environment fixes and commands for the capstone workspace. -->

# Local Environment Setup

## Git in PowerShell

Git is installed on this machine, but some PowerShell sessions may not have Git on `PATH`.

Known Git locations:

```text
C:\Program Files\Git\cmd\git.exe
C:\Program Files\Git\bin\git.exe
```

Use Git directly by full path:

```powershell
& "C:\Program Files\Git\cmd\git.exe" status --short
```

Quick fix for the current PowerShell session:

```powershell
$env:Path += ";C:\Program Files\Git\cmd"
git --version
```

Permanent user-level fix:

```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Program Files\Git\cmd",
  "User"
)
```

Restart PowerShell or Codex after applying the permanent fix.

<!-- Project Environment Setup End -->
