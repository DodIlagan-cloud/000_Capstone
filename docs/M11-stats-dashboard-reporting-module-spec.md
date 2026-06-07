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

## Current Stats App State

This spec is aligned to the current Stats app state as of the M9/M14 work now present in the repository.

### Current Runtime Shape

- M13 provides the single `stats-runtime` container.
- Stats Web is the public browser entry point on port `8080`.
- Module APIs remain internal to the container: M1 identity, M3/M4 file intake, M5 parsing, M7 extraction, and M8 validation.
- M9 Stats Data owns Azure SQL schema, migrations, persistence adapters, and query APIs.
- M14 owns Azure Container Apps, Azure SQL runtime configuration, Key Vault/secret handling, Fabric/Power BI deployment direction, and cloud-readiness evidence.
- M11 must not change persistence logic, cloud deployment wiring, or secret handling.

### Current Stats Web Surface

| Route | Current State | M11 Direction |
| --- | --- | --- |
| `/` | Authenticated dashboard-first shell with static counts for documents, transactions, and warnings | Replace static readiness cards with financial insight cards: last month expenses, current month running expenses, top expense contributor, and upcoming due/payable |
| `/Upload` | Authenticated upload workflow calls M3/M4, M5, M7, M8, and now M9 save endpoint through `StatsDataBaseUrl` | Remains the intake/save source for dashboard data; M11 should link users back to upload when no data exists |
| `/Documents` | Authenticated page lists recent saved M9 document records and supports removal through Stats Data API | Owns data provenance: source summary, document status, document type, source institution, quality, review counts, and drilldown |
| `/Reports` | Authenticated reports shell with deferred reporting state | Becomes native report workspace first, then optional Power BI embed host |
| `/EmailSetup` | Shell placeholder for future email ingestion setup | Can later feed document source filters but is not an M11 dependency |
| `/Users` | Admin user management from M1 | M11 only consumes authenticated user context and role-aware visibility |

### Current M9 API Surface

The current M9 API surface is enough for saved-document visibility but not yet enough for the full M11 dashboard.

| Endpoint | Current Status | M11 Use |
| --- | --- | --- |
| `POST /api/v1/transactions/batches` | Implemented for saving validated upload results into Stats Data | Source of persisted dashboard data after upload review |
| `GET /api/v1/documents?limit=25` | Implemented for recent saved documents | Current foundation for document status and saved-data evidence |
| `DELETE /api/v1/documents/{document_id}` | Implemented for removing saved document records | Current document management action, not a dashboard metric endpoint |
| `GET /api/v1/dashboard/summary` | Not implemented yet | Needed for M11 financial insight cards and trends |
| `GET /api/v1/documents/summary` | Not implemented yet | Needed for Documents provenance summary |
| `GET /api/v1/transactions` | Not implemented yet | Needed for transaction table and trends |
| `GET /api/v1/statements` | Not implemented yet | Needed for obligations and credit exposure |
| `GET /api/v1/document-financial-summaries` | Not implemented yet | Needed for invoice/receipt/payment-proof totals |
| `GET /api/v1/reconciliation-links` | Not implemented yet | Needed for matched/unmatched evidence |
| `GET /api/v1/findings` / `GET /api/v1/review-items` | Not implemented yet as first-class M11 APIs | Needed for review backlog and trust indicators |

### Current Data Foundation

M9 now has Azure SQL migration planning and implementation assets for dashboard-ready tables, including:

- `validation_results`
- `stats_documents`
- `processing_runs`
- `transaction_batches`
- `transactions`
- `financial_fields`
- `document_sections`
- `validated_entities`
- `validated_references`
- `installments`
- `statement_summaries`
- `document_financial_summaries`
- `line_items`
- `financial_evidence_links`
- `findings`
- `review_items`

M11 should read promoted M9 records through APIs or controlled read models. It should not parse `validation_results.payload_json` directly in the browser.

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

The Home dashboard should prioritize financial outcomes over processing counters. Document counts, saved-row counts, and review counts belong primarily on the Documents provenance tab, not as primary Home cards. Home may show small trust warnings only when data quality materially affects a financial insight.

## User Questions M11 Must Answer

| Question | Dashboard Area |
| --- | --- |
| What do I owe soon? | Upcoming obligations |
| What did I spend this month? | Financial snapshot and spending trends |
| How does this month compare with last month? | Current and prior month expense cards |
| Who or what is driving most of my expenses? | Top contributor and category/merchant breakdown |
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

- Financial insight cards.
- Upcoming obligations.
- Recent saved transactions.
- Top expense contributor.
- Monthly or category trend.
- Optional trust warning when financial numbers are affected by review/quality issues.

The Overview should prioritize actions and trust status over dense analytics.

Current alignment:

- `/` already exists as the authenticated dashboard-first shell.
- The current counts are static placeholders.
- First M11 implementation should keep the existing route and progressively replace placeholders with M9-backed financial values.
- Document count, transaction count, and review item count should move to `/Documents` provenance summaries instead of remaining the primary Home cards.

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

The Documents view owns the "where did this data come from?" story. It is the source/provenance tab for saved financial data.

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
- Source type, such as upload, email, or future import.
- Status.
- OCR quality status.
- Redaction applied.
- Transaction row count.
- Financial field count.
- Review item count.
- Created/saved timestamps.
- Linked validation, extraction, parse, and ingestion identifiers when appropriate.

Expected provenance summaries:

- Saved documents count.
- Documents by type.
- Documents by source type.
- Documents by source institution or merchant.
- Documents by workflow status.
- Documents by OCR/data quality status.
- Total transaction rows represented by saved documents.
- Total review items represented by saved documents.
- Latest saved document date.

Current alignment:

- `/Documents` already lists recent M9 saved document records.
- It currently shows file, status, row counts, review counts, saved timestamp, and remove action.
- M11 should extend this into the provenance dashboard rather than create a separate duplicate document-status route.

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

Current alignment:

- `/Reports` already exists as an authenticated deferred reports shell.
- First M11 work should replace the generic deferred panel with native report sections and a Power BI not-configured state.

## First Dashboard Cards

| Card | Purpose | M9 Source |
| --- | --- | --- |
| Last month expenses | Total debit/spending for the previous calendar month | `transactions` |
| This month running expenses | Total debit/spending from the first day of the current month to today | `transactions` |
| Top expense contributor | Highest merchant, counterparty, category, or description contributing to current-month spending | `transactions` |
| Upcoming due / payable | Nearest due obligation and amount | `statement_summaries`, `document_financial_summaries` |
| Monthly expense trend | Current and prior period spending movement | `transactions` |
| Recent notable expenses | Recent high-value or unusual expenses | `transactions`, `findings` |

Document counts, transaction row counts, and review item counts should be displayed on `/Documents` as provenance and data-quality context. They should not be primary Home dashboard cards.

## Required M9 Query APIs

M11 should read from M9 APIs, not direct database connections.

| Endpoint | Current Status | Purpose |
| --- | --- | --- |
| `GET /api/v1/dashboard/summary` | Planned | Financial insight cards, trends, top contributor, recent notable expenses, and upcoming due/payable |
| `GET /api/v1/transactions` | Planned | Transaction table and transaction trends |
| `GET /api/v1/documents` | Implemented for recent saved documents | Document status and dashboard readiness |
| `GET /api/v1/documents/summary` | Planned | Documents provenance summary: source, type, status, quality, row counts, and review counts |
| `GET /api/v1/documents/{document_id}` | Planned | Document drilldown and source traceability |
| `DELETE /api/v1/documents/{document_id}` | Implemented | Remove saved document record and dependent persisted records |
| `GET /api/v1/statements` | Planned | Statement obligations and credit exposure |
| `GET /api/v1/document-financial-summaries` | Planned | Invoice, receipt, and payment-proof totals |
| `GET /api/v1/reconciliation-links` | Planned | Matched and unmatched evidence links |
| `GET /api/v1/findings` | Planned | Open system/module findings |
| `GET /api/v1/review-items` | Planned | User-facing review queue |

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
recent_notable_expenses
top_expense_contributors
document_processing_status
review_backlog
reconciliation_status
documents_provenance_summary
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

Current cloud-dev alignment:

- Azure SQL is the operational persistence direction.
- PostgreSQL `stats-db` is legacy/local-only and should not drive M11 cloud plans.
- Fabric and Power BI are future reporting/analytics layers over curated M9 data.
- Real tenant IDs, subscription IDs, connection strings, passwords, and secret values must not be committed.

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
- Keep `/` as the dashboard-first route.
- Replace static Home cards with financial insight cards when M9 dashboard summary data is available.
- Treat `/Documents` as the first current M9-backed view and the owner of provenance/source summaries.
- Keep `/Reports` as native report shell plus Power BI not-configured state.
- Keep Power BI as a not-configured report area.

### Phase 2: M9 API Integration

- Continue using implemented `GET /api/v1/documents` on `/Documents`.
- Add or consume M9 dashboard, transaction, document summary, statement, financial summary, reconciliation, finding, and review endpoints as they become available.
- Render real Home financial cards, obligations, recent notable expenses, top contributors, and trends only from M9 APIs.
- Render document counts, source summaries, row counts, review counts, and quality summaries on `/Documents`.
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
- Home dashboard views show financial insights first: last month expenses, current month running expenses, top expense contributor, upcoming due/payable, trends, and recent notable expenses.
- Documents views show provenance first: document counts, source/type summaries, saved records, quality, row counts, review counts, and source drilldowns.
- Each displayed financial number can trace to M9 source document/transaction/evidence metadata when available.
- Power BI/Fabric are treated as optional analytics/reporting layers over curated M9 data.
- Missing Power BI/Fabric configuration does not block the native dashboard.
- No secrets, real connection strings, tenant IDs, subscription IDs, passwords, or secret values are committed.

<!-- M11 End -->
