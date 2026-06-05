# Azure SQL Migrations

<!-- M9 - Stats Data and Persistence Start -->

This folder contains Azure SQL Database migrations for the Stats-owned M9 persistence layer.

The migration set is:

```text
001_initial_stats_data_schema.sql
002_validation_reporting_schema.sql
```

The first migration creates the dashboard-ready product tables for documents, validation staging, processing runs, transaction batches, transactions, financial summaries, line items, reconciliation links, findings, and review items.

The second migration brings the schema into line with the evolved validation handoff. It adds validation summary counts, source-section/source-confidence fields, reason-code JSON, and promoted tables for document sections, validated entities, validated references, and installments.

These migrations are written in Azure SQL/T-SQL and must avoid PostgreSQL-only syntax.

Do not store real Azure SQL credentials in this folder.

<!-- M9 End -->
