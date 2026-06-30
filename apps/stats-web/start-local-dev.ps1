# M2 - Stats Web Shell Start
# Starts Stats Web from source on port 8081 while proxying API calls to the
# module ports exposed by infrastructure/compose/stats-runtime.local-dev.override.yml.

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$env:STATS_APP_ROOT = $repoRoot.Path
$env:STATS_RUNTIME_CONFIG = Join-Path $repoRoot.Path "config\stats.runtime.json"
$env:STATS_PATHS_CONFIG = Join-Path $repoRoot.Path "config\stats.paths.json"
$env:STATS_LOGGING_CONFIG = Join-Path $repoRoot.Path "config\stats.logging.json"

$env:StatsWeb__Proxy__IdentityBaseUrl = "http://127.0.0.1:8013"
$env:StatsWeb__Proxy__FileValidationBaseUrl = "http://127.0.0.1:8014"
$env:StatsWeb__Proxy__FileIngestionBaseUrl = "http://127.0.0.1:8014"
$env:StatsWeb__Proxy__DocumentParsingBaseUrl = "http://127.0.0.1:8015"
$env:StatsWeb__Proxy__TransactionExtractionBaseUrl = "http://127.0.0.1:8016"
$env:StatsWeb__Proxy__DataValidationBaseUrl = "http://127.0.0.1:8017"
$env:StatsWeb__Proxy__StatsDataBaseUrl = "http://127.0.0.1:8018"
$env:StatsWeb__Proxy__EmailIngestionBaseUrl = "http://127.0.0.1:8019"

dotnet run --project apps\stats-web\stats.Web.csproj --urls http://127.0.0.1:8081
# M2 End
