# Azure SQL Migrations

<!-- M9 - Stats Data and Persistence Start -->

This folder contains Azure SQL Database migrations for the Stats-owned M9 persistence layer.

The first migration is:

```text
001_initial_stats_data_schema.sql
```

It creates the dashboard-ready product tables for documents, validation staging, processing runs, transaction batches, transactions, financial summaries, line items, reconciliation links, findings, and review items.

These migrations are written in Azure SQL/T-SQL and must avoid PostgreSQL-only syntax.

Do not store real Azure SQL credentials in this folder.

<!-- M9 End -->
