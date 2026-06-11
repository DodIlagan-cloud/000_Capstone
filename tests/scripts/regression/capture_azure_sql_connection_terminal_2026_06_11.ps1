$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "Stats Azure SQL Connection Evidence"
$Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size(160, 3000)
$Host.UI.RawUI.WindowSize = New-Object Management.Automation.Host.Size(150, 42)
Set-Location "C:\000_Capstone"
Clear-Host

function Run-EvidenceCommand {
    param([string]$Command)
    Write-Host ""
    Write-Host ("PS C:\000_Capstone> " + $Command) -ForegroundColor Cyan
    Invoke-Expression $Command
}

Write-Host "Stats Azure SQL Connection Evidence" -ForegroundColor Yellow
Write-Host "Purpose: prove the query is executed against Azure SQL through the containerized Stats runtime."
Write-Host "Secret policy: connection strings, passwords, and tokens are not printed."

Run-EvidenceCommand 'az account show --query "{user:user.name, tenantId:tenantId}" -o table'
Run-EvidenceCommand 'az sql db show --resource-group rg-stats-dev --server sql-stats-dev-001 --name sqldb-stats-dev --query "{database:name, server:serverName, status:status, location:location}" -o table'
Run-EvidenceCommand 'docker ps --filter "name=stats-runtime" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
Run-EvidenceCommand 'docker cp tests\scripts\regression\azure_sql_connection_query_2026_06_11.py stats-runtime:/tmp/azure_sql_connection_query_2026_06_11.py'
Run-EvidenceCommand 'docker exec --workdir /app/apps/stats-data -e PYTHONPATH=/app/apps/stats-data/src stats-runtime /opt/stats/runtime/bin/python /tmp/azure_sql_connection_query_2026_06_11.py'

Write-Host ""
Write-Host "Evidence result: PASSED when Azure SQL resource metadata and runtime DB_NAME/server output are visible above." -ForegroundColor Green
