<!-- M9 - Stats Data and Persistence Start -->
<!-- Evidence summary for cloud-dev Azure SQL resources. -->

# Cloud-Dev Azure SQL Evidence

## Summary

Azure SQL resources have been created for the `cloud-dev` Stats Data and Persistence path.

These resources are for development integration and M9 implementation work. They are not production resources.

## Resources

| Resource | Value |
| --- | --- |
| Resource group | `rg-stats-dev` |
| Region | `australiaeast` |
| Key Vault | `kv-stats-dev-001` |
| Azure SQL logical server | `sql-stats-dev-001` |
| Azure SQL host | `sql-stats-dev-001.database.windows.net` |
| Azure SQL database | `sqldb-stats-dev` |
| Database tier | General Purpose serverless, `GP_S_Gen5_1` |
| Database max size | 32 GB |
| Auto-pause delay | 60 minutes |
| Backup storage redundancy | Local |
| SQL admin login | `statsadmin` |
| Microsoft Entra admin | `Dod Ilagan` |

## Applied Schema

The initial M9 Azure SQL schema migration has been applied:

```text
apps/stats-data/migrations/azure-sql/001_initial_stats_data_schema.sql
```

The migration record exists in:

```text
dbo.schema_migrations
```

Applied migration:

```text
001_initial_stats_data_schema
```

Created tables:

```text
dbo.document_financial_summaries
dbo.financial_evidence_links
dbo.financial_fields
dbo.findings
dbo.line_items
dbo.m8_validation_results
dbo.processing_runs
dbo.review_items
dbo.schema_migrations
dbo.statement_summaries
dbo.stats_documents
dbo.transaction_batches
dbo.transactions
```

## Runtime Verification

The migrated Stats runtime image was built locally as:

```text
stats-runtime:azure-sql-migration
```

The image includes Microsoft ODBC Driver 18 for SQL Server, `unixodbc`, and Python `pyodbc`.

Live runtime checks completed against `sqldb-stats-dev` using Key Vault secrets without printing secret values:

```text
Azure SQL connected: sqldb-stats-dev
Identity Azure SQL init complete
dbo.users exists: True
```

The Identity module now uses `DATABASE_PROVIDER=AzureSql` and `AZURE_SQL_CONNECTIONSTRING` for active runtime persistence. SQLite remains available for isolated unit tests.

The runtime normalizes Azure portal-style connection string fields to ODBC-compatible fields before connecting:

```text
Initial Catalog -> Database
User ID -> UID
Password -> PWD
Encrypt=True/False -> Encrypt=yes/no
TrustServerCertificate=True/False -> TrustServerCertificate=yes/no
```

## Secrets

Secret values were not printed or committed.

The following secret names exist in Key Vault:

| Secret Name | Purpose |
| --- | --- |
| `stats-sql-admin-password` | SQL admin password for initial development/bootstrap access. |
| `stats-azure-sql-connectionstring` | Azure SQL connection string for later Container Apps secret wiring. |

## Network

The SQL server has an `AllowAzureServices` firewall rule:

```text
start-ip: 0.0.0.0
end-ip:   0.0.0.0
```

This supports future Azure Container Apps connectivity. Production-style network restriction belongs to `prod-sim` hardening.

A temporary `CodexCurrentClient` firewall rule was added to apply and verify the first migration from the current development workstation. Review or remove this rule when cloud-dev deployment is fully automated from Azure-hosted runners.

## Implementation Notes

- M9 migrations should target Azure SQL/T-SQL.
- Runtime code should prefer `DATABASE_PROVIDER=AzureSql` and `AZURE_SQL_CONNECTIONSTRING`.
- Real credentials must stay in Key Vault or Container Apps secrets.
- Managed identity should replace SQL admin credential use when the cloud runtime identity is ready.

<!-- M9 End -->
