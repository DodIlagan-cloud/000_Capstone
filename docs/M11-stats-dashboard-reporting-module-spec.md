<!-- M11 - Stats Dashboard and Reporting Start -->
<!-- Defines the Stats Web dashboard and reporting boundary over M9 persisted financial data. -->

# Module 11 Stats Dashboard and Reporting Module Specification

## Module Summary

Module 11 turns persisted Stats financial data into an evidence-backed dashboard and reporting workspace.

M11 is an encompassing Stats Web module. It presents financial summaries, obligations, document status, transactions, reconciliation, review queues, and reporting views over the M9 Stats Data query layer. M11 must help users understand what they owe, what they paid, what needs review, and which source document supports each number.

M11 does not parse documents, extract transactions, validate records, persist data, run migrations, deploy cloud resources, or manage secrets. Those responsibilities remain with M5, M7, M8, M9, M13, and M14.

## Architecture Alignment

| Field | M11 Direction |
| --- | --- |
| Build order | `11` |
| Module | Stats Dashboard and Reporting |
| Type | Encompassing `.NET` app module |
| Owner folder | `apps/stats-web/` |
| Primary input | M9 Stats Data query APIs and authenticated user context |
| Primary output | Dashboard, report, review, and evidence-backed financial views |
| Cloud analytics target | Microsoft Fabric and Power BI over curated M9 data |

## Goals

- Show an operational dashboard for saved financial data from M9.
- Make document and transaction quality visible before users trust dashboard totals.
- Surface upcoming obligations from statements, bills, invoices, and outstanding balances.
- Show spending, income/credits, net movement, categories, merchants, and recent transactions.
- Show reconciliation status for invoices, receipts, EFTPOS slips, transfers, statement rows, and proof documents.
- Provide report views that can later be backed by Power BI/Fabric without replacing the native Stats Web workflow dashboard.
- Keep every displayed financial number traceable to a document, page/line when available, and redacted evidence snippet.
- Use controlled empty, loading, error, and not-configured states when M9 query APIs or reporting embeds are unavailable.

## Non-Goals

- Creating M9 schema, Azure SQL migrations, persistence adapters, or duplicate-check logic.
- Calling M3, M5, M7, or M8 directly for dashboard numbers.
- Rerunning OCR, parsing, extraction, or validation from dashboard/report pages.
- Owning Power BI workspace provisioning, Fabric capacity setup, semantic model refresh, or embed-token secret handling.
- Storing report snapshots, raw documents, full OCR text, passwords, tokens, or database connection strings.
- Replacing the Stats Web operational workflow with Power BI.

## Dashboard Product Principle

The M11 dashboard should be an evidence-backed financial control room, not just a chart gallery.

Every important number should answer:

- What happened financially?
- What document or transaction proves it?
- Is the data trusted or does it need review?
- What should the user do next?

## User Questions M11 Must Answer

| Question | Dashboard Area |
| --- | --- |
| What do I owe soon? | Upcoming obligations |
| What did I spend this month? | Financial snapshot and spending trends |
| What payments have proof? | Reconciliation and evidence links |
| Which invoices, receipts, statements, or transfers are unmatched? | Reconciliation queue |
| Which documents or transactions need review? | Data quality and review backlog |
| Can every number trace back to source evidence? | Drilldown and evidence preview |
| How much credit-card debt or installment exposure exists? | Credit exposure |
| Which documents were processed, saved, failed, or deferred? | Document status |

## First Dashboard Views

### Overview

The Overview is the first screen after authentication once M11 is active.

Expected content:

- Financial snapshot cards.
- Upcoming obligations.
- Recent saved transactions.
- Documents needing review.
- Reconciliation summary.
- Data-quality alerts.

The Overview should prioritize actions and trust status over dense analytics.

### Transactions

The Transactions view shows saved M9 transaction rows.

Expected filters:

- Date range.
- Currency.
- Direction.
- Category.
- Merchant or counterparty.
- Source institution.
- Payment method.
- Quality status.
- Review required.

Expected columns:

- Transaction date.
- Posted date when available.
- Description.
- Merchant/counterparty.
- Category.
- Amount.
- Currency.
- Direction.
- Payment method.
- Source document.
- Confidence or quality status.
- Review state.

### Documents

The Documents view shows persisted document workflow status and dashboard readiness.

Expected filters:

- Document type.
- Source type.
- Source institution.
- Workflow status.
- OCR quality status.
- Review required.

Expected fields:

- Original filename.
- Document type.
- Source institution or merchant.
- Status.
- OCR quality status.
- Redaction applied.
- Created/saved timestamps.
- Linked validation, extraction, parse, and ingestion identifiers when appropriate.

### Obligations

The Obligations view focuses on statement summaries, bills, invoices, and installment exposure.

Expected content:

- Payment due date.
- Minimum amount due.
- Total amount due.
- Outstanding balance.
- Credit limit.
- Available credit.
- Installment balance.
- Invoice total.
- Paid amount.
- Owing amount.
- Payment status.
- Quality status.

### Reconciliation

The Reconciliation view shows whether financial evidence connects.

Expected queues:

- Invoice paid by proof.
- Receipt paid by EFTPOS.
- Statement contains transaction.
- Transfer proof matched to payment.
- Possible duplicate.
- Unmatched invoice.
- Unmatched payment proof.

Expected fields:

- Link type.
- Match status.
- Match confidence.
- Match reason.
- Reference or masked reference.
- Source document/transaction.
- Target document/transaction.

### Reports

The Reports view contains native report summaries first and Power BI embed areas later.

Initial native report sections:

- Financial overview.
- Spending categories.
- Credit-card obligations.
- Invoice and payment matching.
- Document processing quality.
- Review backlog.

When Power BI is not configured, the Reports page must show a clear not-configured state and keep native dashboard views usable.

## First Dashboard Cards

| Card | Purpose | M9 Source |
| --- | --- | --- |
| Spending this period | Total debits for the selected period | `transactions` |
| Credits this period | Total credits for the selected period | `transactions` |
| Net movement | Credits minus debits | `transactions` |
| Upcoming due | Nearest due obligation and amount | `statement_summaries`, `document_financial_summaries` |
| Outstanding obligations | Total due or owing amount | `statement_summaries`, `document_financial_summaries` |
| Review backlog | Open review items/findings | `review_items`, `findings` |
| Document quality | Saved, warning, failed, review counts | `stats_documents`, `processing_runs` |
| Reconciliation | Matched, suggested, unmatched evidence | `financial_evidence_links` |

## Required M9 Query APIs

M11 should read from M9 APIs, not direct database connections.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/dashboard/summary` | Summary cards, trends, obligations, reconciliation, and review counts |
| `GET /api/v1/transactions` | Transaction table and transaction trends |
| `GET /api/v1/documents` | Document status and dashboard readiness |
| `GET /api/v1/documents/{document_id}` | Document drilldown and source traceability |
| `GET /api/v1/statements` | Statement obligations and credit exposure |
| `GET /api/v1/document-financial-summaries` | Invoice, receipt, and payment-proof totals |
| `GET /api/v1/reconciliation-links` | Matched and unmatched evidence links |
| `GET /api/v1/findings` | Open system/module findings |
| `GET /api/v1/review-items` | User-facing review queue |

If an endpoint is unavailable, M11 should show a controlled deferred state rather than calling upstream processing modules.

## Suggested Reporting Data Shapes

M9 may expose these as API response groups, SQL views, or later curated reporting tables.

```text
dashboard_summary
monthly_cashflow
category_spending
upcoming_obligations
credit_exposure
recent_transactions
document_processing_status
review_backlog
reconciliation_status
merchant_counterparty_summary
```

M11 should treat these as read models. M9 owns how they are derived.

## Fabric And Power BI Boundary

Fabric and Power BI are the analytics/reporting layer, not the operational source of truth.

Recommended flow:

```text
M3-M8 extract and validate data
        |
        v
M9 persists trusted financial data in Azure SQL
        |
        v
M11 native dashboard reads M9 APIs for operational workflow
        |
        v
Fabric / Power BI consumes curated M9 data for analytical reports
```

### Native Stats Web Dashboard

Use the native M11 dashboard for daily workflow:

- Review queues.
- Upload/document status.
- Upcoming obligations.
- Recent saved transactions.
- Reconciliation status.
- Evidence drilldowns.
- Empty/loading/error states.

### Power BI Reports

Use Power BI for richer analytical reporting:

- Monthly spending trends.
- Category and merchant analysis.
- Credit-card exposure.
- Payment history.
- Document processing KPIs.
- Quality and review backlog trends.
- Export-ready report pages.

### Fabric

Use Fabric later for curated analytical modelling:

- Lakehouse, warehouse, or semantic model fed from approved M9 data.
- Business-friendly measures and dimensions.
- Power BI report hosting and modelling.

M11 should not require Fabric/Power BI to be configured before the native dashboard is useful.

## Power BI Embed Direction

The planned default embed mode is `AppOwnsData`, consistent with the existing Stats Web configuration placeholder.

M11 should use a backend embed-config endpoint when Power BI is enabled:

```text
StatsWeb:Downstream:ReportingEmbedConfigUrl
```

The backend embed-config endpoint should return only short-lived embed configuration needed by the browser. Secrets, tenant credentials, service principal credentials, and real resource identifiers must come from Azure Container Apps secrets or Key Vault through the owning cloud/runtime boundary. They must not be committed.

When embed config is missing or unavailable, M11 should show:

```text
Power BI reporting is not connected yet.
Stats can still show saved financial data through the native dashboard.
```

## Configuration

Existing safe placeholders:

| Setting | Purpose |
| --- | --- |
| `StatsWeb:Downstream:StatsDataBaseUrl` | Future M9 API target for dashboard data |
| `StatsWeb:Downstream:ReportingEmbedConfigUrl` | Future backend embed-config endpoint |
| `StatsWeb:PowerBi:TenantId` | Future tenant identifier, never a secret |
| `StatsWeb:PowerBi:WorkspaceId` | Future Power BI/Fabric workspace identifier |
| `StatsWeb:PowerBi:DashboardReportId` | Future report identifier |
| `StatsWeb:PowerBi:DatasetId` | Future semantic model/dataset identifier |
| `StatsWeb:PowerBi:EmbedMode` | Planned embed mode, default `AppOwnsData` |
| `StatsWeb:Fabric:CapacityName` | Future capacity name or identifier |
| `StatsWeb:Fabric:WorkspaceName` | Future workspace display name |
| `StatsWeb:Fabric:LakehouseName` | Future lakehouse or warehouse display name |
| `StatsWeb:Fabric:SemanticModelName` | Future semantic model display name |

Committed values must remain safe placeholders. Real connection strings, tenant IDs, subscription IDs, passwords, and secret values must not be committed.

## UX States

M11 views must define these states:

| State | Required Behavior |
| --- | --- |
| No saved data | Show upload/review guidance and do not fake totals |
| M9 unavailable | Show dashboard temporarily unavailable and preserve navigation |
| Partial data | Show available sections and flag missing query groups |
| Review required | Mark totals or records with warning/review status |
| Low OCR quality | Show source quality warning before trusting values |
| Power BI not configured | Keep native dashboard usable and show reporting not connected |
| Power BI unavailable | Show embed error without breaking native report summaries |

## Drilldown And Evidence Requirements

M11 should let users move from dashboard number to evidence:

- Summary card to filtered transaction/document list.
- Transaction to source document and redacted source snippet.
- Obligation to statement or invoice summary.
- Reconciliation item to both linked evidence records.
- Finding/review item to affected document, transaction, field, or source section.

M11 should display masked account/card/reference values only. Full sensitive values should not appear in ordinary dashboard views.

## Security And Data Governance

- Use authenticated user context for all M9 queries.
- Scope ordinary users to their own documents and transactions.
- Allow administrator cross-user visibility only through explicit role-aware M9 APIs.
- Do not expose raw OCR text, full uploaded file bytes, passwords, tokens, connection strings, or secret values.
- Show redacted evidence snippets only when M9 supplies them.
- Treat dashboard screenshots, report exports, and evidence views as sensitive financial artefacts.
- Do not store report snapshots until retention and privacy requirements are explicit.

## Implementation Phases

### Phase 1: Native Dashboard Contract

- Define M11 dashboard views and API expectations.
- Implement Overview with deferred/empty M9 states.
- Show static shell sections only when M9 APIs are not wired.
- Keep Power BI as a not-configured report area.

### Phase 2: M9 API Integration

- Call M9 dashboard and list endpoints.
- Render real summary cards, obligations, recent transactions, review backlog, and reconciliation status.
- Add filters and drilldowns.
- Add user-facing error and partial-data states.

### Phase 3: Reporting Views

- Add native reports for financial overview, categories, obligations, reconciliation, quality, and backlog.
- Add export-ready view structure when output requirements are approved.
- Keep Power BI optional.

### Phase 4: Fabric And Power BI

- Create curated M9 reporting views or exports.
- Build a Fabric semantic model or compatible Power BI dataset over approved M9 data.
- Build first Power BI report pages.
- Add embed config endpoint through the appropriate backend/cloud boundary.
- Embed reports in the M11 Reports page when configured.

## Test Plan

| Test Type | Required Coverage |
| --- | --- |
| Unit tests | View models, formatting, empty states, query parameter construction |
| Integration tests | M9 API contract handling and same-origin proxy behavior |
| Browser tests | Dashboard navigation, reports navigation, empty states, filters, drilldowns |
| Security tests | No secret/config leakage; user-scoped query behavior |
| Regression tests | M1 login, M2 shell navigation, upload/save flow, M9 save still work |
| Evidence tests | Container-first screenshots and terminal/API evidence from M13 onward |

## Acceptance Criteria

- M11 spec exists and defines dashboard/reporting goals, boundaries, views, data sources, and test plan.
- M11 reads operational dashboard data from M9 APIs or controlled deferred states only.
- M11 does not call processing modules directly for report totals.
- Dashboard views show financial snapshot, obligations, transactions, documents, reconciliation, and review/data-quality status.
- Each displayed financial number can trace to M9 source document/transaction/evidence metadata when available.
- Power BI/Fabric are treated as optional analytics/reporting layers over curated M9 data.
- Missing Power BI/Fabric configuration does not block the native dashboard.
- No secrets, real connection strings, tenant IDs, subscription IDs, passwords, or secret values are committed.

<!-- M11 End -->
