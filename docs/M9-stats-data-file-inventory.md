<!-- M9 - Stats Data and Persistence Start -->
<!-- Documents files created or modified for M9 Stats Data and Azure SQL. -->

# M9 Stats Data File Inventory

## Summary

M9 owns the Stats product persistence layer. The current cloud-dev direction is Azure SQL Database.

## Files

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M9-stats-data-persistence-module-spec.md` | Created / Updated | Defines M9 schema, persistence boundaries, Azure SQL migration requirements, API contract, config, testing, and acceptance criteria. |
| `docs/M9-stats-data-erd.md` | Created | Draft ERD for Stats-owned product tables and the M1 user reference boundary. |
| `docs/M9-stats-data-file-inventory.md` | Created | This file. Tracks M9 persistence and Azure SQL assets. |
| `apps/stats-data/migrations/azure-sql/README.md` | Created | Documents the Azure SQL migration folder and no-secret boundary. |
| `apps/stats-data/migrations/azure-sql/001_initial_stats_data_schema.sql` | Created | Initial Azure SQL schema for M9 product data tables, indexes, JSON checks, migration tracking, and dashboard-ready query fields. |
| `infrastructure/cloud/cloud-dev-azure-sql-evidence.md` | Created | Records the created cloud-dev Azure SQL, Key Vault, firewall, Entra admin, and secret names without secret values. |
| `tests/integration/test_m9_azure_sql_contract.py` | Created / Updated | Verifies the Azure SQL migration, cloud config, identity database provider boundary, startup readiness script, Compose runtime shape, and container driver dependencies without requiring live credentials. |

## Verification

Run:

```powershell
pytest tests/integration/test_m9_azure_sql_contract.py
```

<!-- M9 End -->
