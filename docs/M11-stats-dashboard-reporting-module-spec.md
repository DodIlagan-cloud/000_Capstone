<!-- M11 - Stats Dashboard and Reporting Start -->
<!-- Defines the Stats Web dashboard and reporting boundary over M9 persisted financial data. -->

# Module 11 Stats Dashboard and Reporting Module Specification

## Module Summary

Module 11 turns persisted Stats financial data into an evidence-backed dashboard and reporting workspace.

M11 is an encompassing Stats Web module. It presents Power BI-backed financial KPI dashboards alongside native Stats Web document provenance, operational status, review queues, and evidence navigation over the M9 Stats Data query layer. M11 must help users understand spending patterns, source coverage, data quality, what needs review, and which source document supports each number.

M11 does not parse documents, extract transactions, validate records, persist data, run migrations, deploy cloud resources, or manage secrets. Those responsibilities remain with M5, M7, M8, M9, M13, and M14.

## Architecture Alignment

| Field | M11 Direction |
| --- | --- |
| Build order | `11` |
| Module | Stats Dashboard and Reporting |
| Type | Encompassing `.NET` app module |
| Owner folder | `apps/stats-web/` |
| Primary input | Power BI embed/reporting configuration, M9 Stats Data query APIs, and authenticated user context |
| Primary output | Embedded financial KPI dashboards, document provenance, report, review, and evidence-backed financial views |
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
| `/` | Authenticated dashboard-first shell with static counts for documents, transactions, and warnings | Replace static readiness cards with Power BI-backed financial KPI cards: last month expenses, current month running expenses, top expense contributor, prior-month change, monthly history, and notable expenses |
| `/Upload` | Authenticated upload workflow calls M3/M4, M5, M7, M8, and now M9 save endpoint through `StatsDataBaseUrl` | Remains the intake/save source for dashboard data; M11 should link users back to upload when no data exists |
| `/Documents` | Authenticated page lists recent saved M9 document records and supports removal through Stats Data API | Owns data provenance: source summary, document status, document type, source institution, quality, review counts, and drilldown |
| `/Reports` | Authenticated reports shell with deferred reporting state | Becomes a native Stats insights workspace powered by curated Fabric/Power BI analytics, focused on explanation, classification, source coverage, and trust rather than duplicating Home KPI cards or showing a pasted report canvas |
| `/EmailSetup` | Shell placeholder for future email ingestion setup | Can later feed document source filters but is not an M11 dependency |
| `/Users` | Admin user management from M1 | M11 only consumes authenticated user context and role-aware visibility |
| `/Admin/Classifications` | Admin classification management from M2 with M5/M7 ownership | M11 may link classification metrics back to this admin surface but must not own rule editing or classification decisions |

### Current M9 API Surface

The current M9 API surface is enough for saved-document visibility but not yet enough for the full M11 dashboard.

| Endpoint | Current Status | M11 Use |
| --- | --- | --- |
| `POST /api/v1/transactions/batches` | Implemented for saving validated upload results into Stats Data | Source of persisted dashboard data after upload review |
| `GET /api/v1/documents?limit=25` | Implemented for recent saved documents | Current foundation for document status and saved-data evidence |
| `DELETE /api/v1/documents/{document_id}` | Implemented for removing saved document records | Current document management action, not a dashboard metric endpoint |
| `GET /api/v1/dashboard/summary` | Not implemented yet | Optional native fallback or support API; primary financial KPI cards should come from Power BI |
| `GET /api/v1/documents/summary` | Not implemented yet | Needed for Documents provenance summary |
| `GET /api/v1/transactions` | Not implemented yet | Needed for transaction table and trends |
| `GET /api/v1/statements` | Not implemented yet | Future work for obligations, recurring bills, and credit exposure |
| `GET /api/v1/document-financial-summaries` | Not implemented yet | Needed for invoice/receipt/payment-proof totals |
| `GET /api/v1/reconciliation-links` | Not implemented yet | Future work for matched/unmatched evidence |
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

- Show Power BI-backed financial KPI dashboards over saved financial data from M9.
- Make document and transaction quality visible before users trust dashboard totals.
- Show spending, income/credits, net movement, categories, merchants, and recent transactions.
- Show MVP reporting by spending category and transaction type, using persisted M9 fields produced by M7/M8 rather than dashboard-side inference.
- Show source document coverage, data quality, and review status so users know whether reported numbers can be trusted.
- Provide report views backed by Power BI/Fabric while preserving native Stats Web workflow and provenance views.
- Keep every displayed financial number traceable to a document, page/line when available, and redacted evidence snippet.
- Use controlled empty, loading, error, and not-configured states when M9 query APIs or reporting embeds are unavailable.

## Non-Goals

- Creating M9 schema, Azure SQL migrations, persistence adapters, or duplicate-check logic.
- Calling M3, M5, M7, or M8 directly for dashboard numbers.
- Rerunning OCR, parsing, extraction, or validation from dashboard/report pages.
- Owning Power BI workspace provisioning, Fabric capacity setup, semantic model refresh, or embed-token secret handling outside the approved M14/cloud boundary.
- Storing report snapshots, raw documents, full OCR text, passwords, tokens, or database connection strings.
- Replacing the Stats Web operational workflow with Power BI.
- Owning document or transaction classification logic. M5 owns document classification, including the optional AI-assisted document-classification fallback and its audit metadata. M7 owns transaction classification. M9 owns durable suggestion, approval, and synchronization records. M11 reports persisted outcomes, classification source, unknown rates, suggestion lifecycle, approved-label coverage, and review backlog.

## Dashboard Product Principle

The M11 dashboard should be an evidence-backed financial control room, not just a chart gallery.

Every important number should answer:

- What happened financially?
- What document or transaction proves it?
- Is the data trusted or does it need review?
- What should the user do next?

The Home dashboard should prioritize financial outcomes over processing counters, and those financial KPI cards should be Power BI-backed once reporting is connected. Document counts, saved-row counts, and review counts belong primarily on the Documents provenance tab, not as primary Home cards. Home may show small native trust warnings only when data quality materially affects a financial insight.

## Page Responsibility Split

M11 must keep the main app pages distinct so users do not see the same dashboard repeated in different places.

| Page | Primary Job | Should Avoid |
| --- | --- | --- |
| Home | Executive financial snapshot: current/last period expenses, top contributor, notable expense, change against prior month, monthly history, currency, and freshness | Dense tables, source provenance summaries, full report canvases, category diagnostics, or long explanations |
| Reports | Explanation and diagnosis: why totals changed, what categories drive spend, how complete classification is, whether source coverage is sufficient, and what trust blockers affect the numbers | Repeating Home KPI cards as primary content or acting as a simple embedded Power BI report frame |
| Documents | Provenance/source records: which files were saved, where records came from, document quality, row counts, review counts, and source drilldown | Becoming the primary financial summary or category analysis page |

Home answers "what happened?". Reports answers "why did it happen and can I trust it?". Documents answers "where did the data come from?".

## User Questions M11 Must Answer

| Question | Dashboard Area |
| --- | --- |
| What did I spend this month? | Financial snapshot and spending trends |
| How does this month compare with last month? | Current and prior month expense cards |
| Who or what is driving most of my expenses? | Top contributor and category/merchant breakdown |
| What type of financial movement is this? | Transaction type mix and transaction detail |
| What spending category does this belong to? | Spending category cards, trends, and filters |
| Are new labels being suggested, approved, or rejected? | Recognition settings metrics and review backlog |
| Did label changes update existing saved records? | Recognition sync/audit metrics |
| Are my source records complete enough to trust the report? | Source document coverage |
| Which extraction or validation issues affect the report? | Data quality and confidence |
| Which documents or transactions need review? | Data quality and review backlog |
| Can every number trace back to source evidence? | Drilldown and evidence preview |
| Which documents were processed, saved, failed, or deferred? | Document status |

## First Dashboard Views

### Overview

The Overview is the first screen after authentication once M11 is active.

Expected content:

- Dashboard header with last update, selected currency, and rate basis. Vendor/source labels should stay out of the primary Home header unless needed for an error or setup state.
- Analytics-backed financial insight cards.
- Recent saved transactions.
- Top expense contributor.
- Analytics-backed monthly history and a clearly labelled current-month change against the prior month.
- Optional trust warning when financial numbers are affected by review/quality issues.

The Overview should prioritize actions and trust status over dense analytics.

Current alignment:

- `/` already exists as the authenticated dashboard-first shell.
- The current counts are static placeholders.
- First M11 implementation should keep the existing route and progressively replace placeholders with analytics-backed financial KPI cards when reporting configuration is available.
- Document count, transaction count, and review item count should move to `/Documents` provenance summaries instead of remaining the primary Home cards.
- The currency toggle belongs beside the last-updated indicator in the upper-left dashboard header so users can evaluate both data freshness and reporting currency before reading the KPI cards.

### Transactions

The Transactions view shows saved M9 transaction rows.

Expected filters:

- Date range.
- Currency.
- Direction.
- Transaction type.
- Transaction subtype.
- Category.
- Spending subcategory.
- Merchant or counterparty.
- Source institution.
- Payment method.
- Quality status.
- Review required.
- Classification source.
- Recognition suggestion status where linked.

Expected columns:

- Transaction date.
- Posted date when available.
- Description.
- Merchant/counterparty.
- Category.
- Amount.
- Currency.
- Direction.
- Transaction type.
- Transaction subtype.
- Spending category.
- Spending subcategory.
- Payment method.
- Source document.
- Confidence or quality status.
- Review state.
- Label approval/sync status when a transaction is affected by a pending or recently approved label change.

### Recognition Quality Metrics

M11 should make recognition governance measurable without exposing provider names, model versions, or raw OCR text in normal user screens.

Expected metrics:

- Unknown document type count and rate.
- Unknown transaction type count and rate.
- Uncategorized spending count and rate.
- Pending recognition-label suggestions.
- Approved, rejected, edited-before-approval, renamed, and merged suggestion counts.
- Label synchronization runs and affected transaction counts.
- Transactions still using old labels after an approved rename/merge.
- Category/reporting coverage after admin approval.

The normal dashboard should describe these in user language, such as "items needing label review" or "labels awaiting approval." Technical AI/provider metadata belongs in admin/audit detail views only when needed for governance.

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

### Future Work: Obligations And Credit Exposure

Obligations, recurring bills, credit-card exposure, and installment summaries are valid future reporting outcomes, but they are not part of the first Reports page implementation. They should be added only when M9 has stable statement, obligation, payment-status, and recurring-payment read models.

Future expected content:

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

The Reports view is a native Stats insights workspace powered by curated Fabric/Power BI analytics. It should support the literature-backed value proposition that Stats turns scattered financial documents into useful and trustworthy financial information.

Reports should not repeat the Home KPI cards as its primary content. It may share the same reporting period, currency, and freshness context, but its purpose is to explain and diagnose the financial snapshot: which categories drove the numbers, how complete classification is, which sources are represented, and what quality or review issues affect trust.

Expected header context:

- Reporting period.
- Currency.
- Last analytics refresh.
- Data readiness or classification coverage.
- Source summary, such as document and transaction counts, as compact context rather than primary KPI cards.

Initial report sections:

- Financial overview.
- Spending categories.
- Classification quality.
- Source document coverage.
- Review impact.

The Reports page must include selected-section context so users understand what each section answers, which data it uses, and what should be reviewed before trusting the numbers.

Expected initial sections:

| Section | Question Answered | Expected Content |
| --- | --- | --- |
| Financial overview | What changed in spending, and is the current period moving up or down? | Prior-month expense total, current running expense total, movement against prior month, monthly history, and context about what to check before trusting category-level conclusions |
| Spending categories | Where is the money going, and which categories drive spend? | Category breakdown, amount, share of total, confidence/readiness, review count, uncategorized total, and link to review uncategorized transactions |
| Classification quality | How reliable are category and transaction labels? | Categorized vs uncategorized counts, unknown transaction type counts, low-confidence labels, pending/approved/rejected suggestion counts when available, and labels needing review |
| Source coverage | Is the report based on enough source material? | Months covered, documents per month, transactions per month, missing/weak months, source institution mix, and OCR/validation issue impact |
| Review impact | What weakens trust in the reported numbers? | Review-required transactions, low OCR quality documents, validation warnings, missing dates/amounts/categories, duplicates/exclusions, and affected totals |

Deferred report sections:

- Budget vs actual, once real budget records exist.
- Bills and recurring payments, once stable obligation and payment-status data exists.
- Credit-card exposure and installment summaries, once statement-specific read models exist.
- Invoice/payment reconciliation, once reliable matching data exists.

When Power BI is not configured, the Reports page must show a clear not-configured state. Native document/provenance and operational workflow views must remain usable.

Current alignment:

- `/Reports` exists as an authenticated native analytics workbench, not a pasted Power BI report frame.
- The first Reports implementation now uses native report-section navigation, report panels, currency/refresh context, financial overview metrics, monthly history, and controlled not-configured/error states.
- Spending categories and classification quality have dedicated report sections, but category totals remain dependent on stable persisted classification data from M7/M8/M9.
- A full Power BI report canvas may remain available for validation, analyst exploration, or future export workflows, but it should not be the default production Reports experience.

## First Dashboard Cards

| Card | Purpose | Primary Source |
| --- | --- | --- |
| Last month expenses | Total debit/spending for the previous calendar month | Power BI semantic model over M9 `transactions` |
| This month running expenses | Total debit/spending from the first day of the reporting month to the reporting as-of date | Power BI semantic model over M9 `transactions` |
| Top expense contributor | Highest merchant, counterparty, category, or description contributing to current-month spending | Power BI semantic model over M9 `transactions` |
| Change vs prior month | Current month spending minus the previous month; positive means spending is higher | Power BI semantic model over M9 `transactions` |
| Recent notable expenses | Recent high-value or unusual expenses | Power BI semantic model over M9 `transactions` and `findings` |

Document counts, transaction row counts, and review item counts should be displayed on `/Documents` as provenance and data-quality context. They should not be primary Home dashboard cards.

## Transaction Classification Direction

Spending categories and transaction types should not depend on OCR alone. OCR and extraction provide transaction rows, but useful MVP reporting requires M7-owned transaction classification before M9 persistence.

Recommended classification approach:

- Normalize transaction descriptions and source institution labels before classification.
- Keep transaction type separate from spending category. Transaction type describes movement mechanics such as purchase, payment, transfer, refund, fee, interest, installment, adjustment, or tax. Spending category describes the reporting bucket such as medical, pharmacy, groceries, utilities, transport, banking fees, interest, transfers, shopping, food/dining, income, tax, or uncategorized.
- Use stable vocabularies for both transaction types and household/MVP spending categories.
- Apply deterministic rules first for descriptions, merchants, keywords, section labels, references, account patterns, document types/subtypes, and payment methods.
- Use optional AI-assisted classification only as a configured fallback for weak, ambiguous, or unknown deterministic rule results, following the same pattern as M5 document classification.
- Store transaction type and spending category suggestions with confidence, rule/model source, version, and review status.
- Route low-confidence or ambiguous transactions to review instead of forcing a category.
- Persist user corrections so future similar transactions can be classified more reliably.
- Keep type/category reports transparent by showing uncategorized spend, unknown transaction type counts, low-confidence classification counts, AI-assisted coverage, and review-required records.

M11 should report classification coverage and category trust before presenting category totals as reliable financial insight. M7 owns classification suggestions and optional AI-assisted fallback, M8 validates/review-gates them, and M9 owns persisted classification fields, audit trail, and migrations. M11 consumes the resulting read models.

## Currency Display And Exchange Rates

M11 owns the reporting currency user experience, not exchange-rate acquisition or persistence.

### Home Placement

The Home dashboard header should place the currency toggle beside the last update section in the upper-left corner of the page.

Suggested header structure:

```text
Financial Dashboard
Last updated: 08 Jun 2026 09:42    Currency: [ NZD v ]    Rate basis: Transaction date
```

This placement keeps the two most important interpretation controls together:

- How fresh is the dashboard?
- Which currency are the financial KPI cards using?

### M11-Owned Behavior

M11 owns:

- Currency toggle placement and visual behavior in Stats Web.
- Passing selected currency context into embedded Power BI reports where supported.
- Displaying selected currency, rate basis, last Power BI refresh, and not-configured states.
- Requiring Power BI KPI cards to respond to the selected reporting currency.

M11 does not own:

- Fetching current exchange rates from an external provider.
- Persisting exchange-rate tables.
- Creating Azure SQL schema or migrations for currency/rate data.
- Managing Power BI/Fabric credentials, service principals, embed secrets, or refresh secrets.

### Exchange Rate Direction

Exchange rates should be refreshed outside the browser and stored as auditable reference data before Power BI uses them.

Current gap to preserve: historical test data may be stored in PHP while the product default remains NZD for the New Zealand user context. The dashboard should not lose those records when NZD is selected. Once FX support exists, the selected reporting currency should convert persisted transaction amounts through an auditable exchange-rate table instead of filtering out transactions whose original currency differs from the selected display currency.

Recommended flow:

```text
External FX source or manual reference table
        |
        v
M9/Fabric stores exchange-rate reference data
        |
        v
Power BI semantic model applies selected reporting currency
        |
        v
M11 embeds Power BI KPI cards and reports
```

Default rate basis should be transaction-date rate for historical reporting accuracy. A current-rate mode can be added later if users need a present-value estimate.

Power BI should use a currency dimension, exchange-rate table, converted amount measures, and dynamic format strings so selected currency changes both values and symbols consistently.

## Required M9 Query APIs

M11 should read native operational/provenance data from M9 APIs, not direct database connections. Financial KPI cards and analytical dashboard visuals should come from embedded Power BI reports/dashboards over curated M9 data.

| Endpoint | Current Status | Purpose |
| --- | --- | --- |
| `GET /api/v1/dashboard/summary` | Planned/optional | Native fallback, validation support, or non-Power BI operational summary when embed is unavailable |
| `GET /api/v1/transactions` | Planned | Transaction table and transaction trends |
| `GET /api/v1/documents` | Implemented for recent saved documents | Document status and dashboard readiness |
| `GET /api/v1/documents/summary` | Planned | Documents provenance summary: source, type, status, quality, row counts, and review counts |
| `GET /api/v1/documents/{document_id}` | Planned | Document drilldown and source traceability |
| `DELETE /api/v1/documents/{document_id}` | Implemented | Remove saved document record and dependent persisted records |
| `GET /api/v1/statements` | Planned | Future statement obligations, recurring bills, and credit exposure |
| `GET /api/v1/document-financial-summaries` | Planned | Invoice, receipt, and payment-proof totals |
| `GET /api/v1/reconciliation-links` | Planned | Future matched and unmatched evidence links |
| `GET /api/v1/findings` | Planned | Open system/module findings |
| `GET /api/v1/review-items` | Planned | User-facing review queue |

If an endpoint is unavailable, M11 should show a controlled deferred state rather than calling upstream processing modules.

## Suggested Reporting Data Shapes

M9 may expose these as API response groups, SQL views, or later curated reporting tables.

```text
dashboard_summary
monthly_cashflow
category_spending
recent_transactions
recent_notable_expenses
top_expense_contributors
document_processing_status
review_backlog
documents_provenance_summary
transaction_classification
source_document_coverage
data_quality_confidence
review_exceptions
```

M11 should treat these as read models. M9 owns how they are derived.

Future reporting read models may include `upcoming_obligations`, `credit_exposure`, and `reconciliation_status` after M9 promotes stable obligation and matching data.

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
M11 native views read M9 APIs for operational workflow and provenance
        |
        v
Fabric / Power BI consumes curated M9 data for measures, semantic models, and analytical outputs
        |
        v
M11 renders native Stats report sections for product-facing investigation and trust workflows
```

### Native Stats Web Views

Use native M11 views for daily workflow:

- Review queues.
- Upload/document status.
- Document provenance.
- Reconciliation status.
- Evidence drilldowns.
- Empty/loading/error states.

### Power BI And Fabric Analytics

Use Power BI/Fabric to provide curated analytical outputs behind Stats-native reporting:

- Last month expenses.
- This month running expenses.
- Top expense contributors.
- Current-month change against the prior month.
- Monthly spending history.
- Category and merchant analysis.
- Classification coverage and uncategorized spend.
- Source coverage and document quality indicators.
- Obligation/payable summaries only after stable obligation and payment-status data exists.
- Payment history.
- Document processing KPIs.
- Quality and review backlog trends.
- Export-ready report pages when approved.

Stats Web should render the default user-facing Reports experience itself. Full embedded Power BI report pages are acceptable for validation, development, analyst exploration, and future export-ready report views, but the primary production UX should be a native, question-led Stats view.

### Fabric

Use Fabric for curated analytical modelling:

- Lakehouse, warehouse, or semantic model fed from approved M9 data.
- Business-friendly measures and dimensions.
- Power BI report hosting and modelling where needed.
- Stable analytical outputs that Stats Web can present as native insights.

M11 should not require Fabric/Power BI to be configured before native document/provenance and operational workflow views are useful. However, financial KPI cards and analytical report sections are considered reporting features and should display a controlled not-configured state until the approved analytics layer is connected.

Current cloud-dev alignment:

- Azure SQL is the operational persistence direction.
- PostgreSQL `stats-db` is legacy/local-only and should not drive M11 cloud plans.
- Fabric and Power BI are future reporting/analytics layers over curated M9 data.
- Real tenant IDs, subscription IDs, connection strings, passwords, and secret values must not be committed.

### Current Fabric Execution Status

As of 2026-06-08, the M11 development Fabric capacity exists and is paused for cost control.

Completed checks:

- `Microsoft.Fabric` resource provider is registered.
- Microsoft Fabric Azure CLI extension is installed.
- Development capacity `capstatsdev001` exists in `rg-stats-dev`.
- Capacity region is `Australia East`.
- Capacity SKU is `F2`.
- Capacity state is `Paused`.
- Native tenant account `Dod@ejpilagangmail.onmicrosoft.com` exists and has Owner access on the active subscription.
- Capacity administrator is `Dod@ejpilagangmail.onmicrosoft.com`.
- Tags include `project=stats`, `module=M11`, `environment=dev`, and `cost-control=suspend-when-idle`.
- Because the capacity is paused, Fabric hourly compute cost should not be running while M11 is idle.

Remaining setup:

- Build the first Power BI financial KPI report pages.
- Configure semantic model refresh policy inside Fabric/Power BI.
- Configure Stats Web Power BI embed settings through secret-backed runtime configuration.

Workspace status:

- Fabric workspace `Stats - Dev - Reporting` has been created.
- Both the original portal user and native tenant account `Dod@ejpilagangmail.onmicrosoft.com` have Admin access on the workspace.
- Workspace capacity assignment has completed for `capstatsdev001`.
- Workspace type is `Fabric`.
- Semantic model storage format is small semantic model storage format.
- Attempts to update capacity administration from the personal Gmail CLI identity are rejected by Azure Active Directory. Use the native tenant account for capacity administration.

Reporting model status:

- First semantic model contract has been defined in `docs/M11-powerbi-semantic-model-contract.md`.
- Draft reporting read-model SQL has been prepared in `apps/stats-data/reporting/financial_reporting_read_models.sql`.
- M11 read-model SQL has been applied to cloud-dev Azure SQL for reporting validation.
- The reporting read models now include `vw_reporting_spending_categories` and `vw_reporting_classification_quality` so Reports can explain category readiness and classification trust.
- Latest verified cloud-dev rows after the current reporting update: `vw_reporting_transactions` 1, `vw_reporting_monthly_expenses` 1, `vw_reporting_top_expense_contributors` 1, `vw_reporting_spending_categories` 1, `vw_reporting_classification_quality` 1, `vw_reporting_upcoming_obligations` 0, `vw_reporting_recent_notable_expenses` 1, and `vw_reporting_document_provenance` 1.
- Power BI semantic model `Stats Financial KPIs Dev` has been created in `Stats - Dev - Reporting`.
- Semantic model ID is `48d2cf50-7694-44a3-8e33-6919c24677e4`.
- Azure SQL data-source credentials have been configured for the semantic model through the Power BI datasource API without printing secret values.
- Semantic model refresh has been triggered and completed successfully through the Power BI API.
- Fabric Create Report API attempts were accepted as long-running operations but failed during report import because the Power BI report workload rejected the generated PBIR `version.json` schema.
- The first report item was then created manually in the Power BI/Fabric portal from the `Stats Financial KPIs Dev` semantic model.
- Report `Financial Overview Dev` exists in workspace `Stats - Dev - Reporting`.
- Report ID is `6e8c2178-de48-4199-886d-1d72adb73658`.
- Report default page display name is `Page 1`; internal page name is `8af1331343190715ce1b`.
- `M11` is a milestone/spec/test label only. It must not be used as a prefix in production-facing Stats Web labels, Power BI report names, report pages, semantic model table names, dashboards, or user-visible artefacts.
- Stats Web `/Reports` no longer loads the Power BI client script by default and now renders the product-facing report investigation page natively.
- The read-model SQL is still not a formal M9 migration. M9 should promote it into migrations or a managed reporting-view deployment path after review.

Cost-control rule:

- M11 should only run the Fabric capacity while building, refreshing, or testing reports.
- When work stops, use Azure Portal or `az fabric capacity suspend --resource-group rg-stats-dev --capacity-name capstatsdev001`.
- When work resumes, use Azure Portal or `az fabric capacity resume --resource-group rg-stats-dev --capacity-name capstatsdev001`.

## Power BI Embed Direction

The planned default embed mode is `AppOwnsData`, consistent with the existing Stats Web configuration placeholder.

M11 should use a backend embed-config endpoint when Power BI is enabled:

```text
StatsWeb:Downstream:ReportingEmbedConfigUrl
```

Stats Web exposes the browser-facing contract at:

```text
GET /api/v1/reporting/embed-config?currency=NZD
```

That route must be handled by Stats Web before the generic module API proxy. It returns a controlled state when Power BI is not configured.

Stats Web supports two backend modes:

- External embed backend: fetch from `StatsWeb:Downstream:ReportingEmbedConfigUrl`.
- Direct Power BI backend: use service-principal credentials from secret-backed configuration to call Microsoft identity and Power BI REST APIs.

The direct backend uses Microsoft client-credentials authentication for the Power BI API scope, fetches the configured report from the configured workspace, and generates a view-only report embed token.

The browser-facing response may include only short-lived embed configuration needed by the browser:

- `status`
- `message`
- `embed_url`
- `report_id`
- `dataset_id`
- `access_token`
- `token_expires_at_utc`
- `last_refreshed_at_utc`
- `selected_currency`
- `rate_basis`
- `default_page_name`
- `pages`

Secrets, tenant credentials, service principal credentials, and real resource identifiers must come from Azure Container Apps secrets or Key Vault through the owning cloud/runtime boundary. They must not be committed.

When embed config is missing or unavailable, M11 should show:

```text
Power BI reporting is not connected yet.
Stats can still show document provenance, upload status, review queues, and evidence workflow.
```

## Configuration

Existing safe placeholders:

| Setting | Purpose |
| --- | --- |
| `StatsWeb:Downstream:StatsDataBaseUrl` | Future M9 API target for dashboard data |
| `StatsWeb:Downstream:ReportingEmbedConfigUrl` | Future backend embed-config endpoint |
| `StatsWeb:PowerBi:TenantId` | Future tenant identifier, never a secret |
| `StatsWeb:PowerBi:ClientId` | Future service principal client identifier, never a secret |
| `StatsWeb:PowerBi:ClientSecret` | Secret-backed service principal credential, never committed |
| `StatsWeb:PowerBi:WorkspaceId` | Future Power BI/Fabric workspace identifier |
| `StatsWeb:PowerBi:DashboardReportId` | Future report identifier |
| `StatsWeb:PowerBi:DatasetId` | Future semantic model/dataset identifier |
| `StatsWeb:PowerBi:ApiBaseUrl` | Power BI REST API base URL, default `https://api.powerbi.com/v1.0/myorg` |
| `StatsWeb:PowerBi:EmbedMode` | Planned embed mode, default `AppOwnsData` |
| `StatsWeb:Reporting:AsOfDate` / `STATS_AS_OF_DATE` | Optional `yyyy-MM-dd` reporting clock override for historical testing, such as `2019-01-31`; blank uses the real current date |
| `StatsWeb:Reporting:DefaultCurrency` / `STATS_REPORTING_DEFAULT_CURRENCY` | Optional initial currency selection. Committed default remains `NZD`. |
| `StatsWeb:Reporting:FxRates` / `STATS_REPORTING_FX_RATES` | Optional comma-separated reporting FX override pairs, such as `PHP:NZD=0.0300,NZD:AUD=0.9200,NZD:USD=0.6100`, for local or historical test runs until an auditable FX reference table is available. This must convert source currency amounts into the selected reporting currency instead of filtering records out; cross-currency rates may be derived through configured bridge pairs. |
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
| Power BI not configured | Keep native document/provenance views usable and show financial dashboard/reporting not connected |
| Power BI unavailable | Show embed error without breaking native operational/provenance views |

## Drilldown And Evidence Requirements

M11 should let users move from dashboard number to evidence:

- Power BI summary card/report visual to filtered transaction/document list where embed drillthrough or Stats Web deep links are available.
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

- Define M11 dashboard views, native report-section expectations, analytics integration expectations, and native provenance API expectations.
- Keep `/` as the dashboard-first route.
- Replace static Home cards with analytics-backed financial insight cards when reporting configuration is available.
- Treat `/Documents` as the first current M9-backed view and the owner of provenance/source summaries.
- Define `/Reports` as a native insights workspace for spending categories, classification quality, source coverage, data quality, and transaction drilldown, with controlled not-configured states.

### Phase 2: M9 API Integration

- Continue using implemented `GET /api/v1/documents` on `/Documents`.
- Add or consume M9 transaction, document summary, statement, financial summary, finding, and review endpoints as they become available.
- Render real Home financial cards, recent notable expenses, top contributors, and trends from curated M9/Fabric/Power BI analytics data.
- Render document counts, source summaries, row counts, review counts, and quality summaries on `/Documents`.
- Add filters and drilldowns.
- Add user-facing error and partial-data states.

### Phase 3: Reporting Views

- Add native Reports sections for spending categories, classification quality, source document coverage, data quality/confidence, and transaction drilldown.
- Keep obligations, credit-card exposure, budget-vs-actual, and reconciliation as future report sections until the supporting M9 read models are stable.
- Add export-ready view structure when output requirements are approved.
- Keep native provenance and workflow views usable when Power BI is unavailable.

### Phase 4: Fabric And Power BI

- Create curated M9 reporting views or exports.
- Build a Fabric semantic model or compatible Power BI dataset over approved M9 data.
- Build first analytics-backed measures for Home KPI cards and Reports diagnostic sections.
- Add embed config endpoint through the appropriate backend/cloud boundary.
- Use Power BI/Fabric outputs to populate native Stats Web report sections when configured. Keep full embedded reports as a secondary validation/export path, not the default Reports UX.

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
- M11 reads native operational/provenance data from M9 APIs or controlled deferred states only.
- M11 does not call processing modules directly for report totals.
- Home dashboard views show Power BI-backed financial insights first: last month expenses, current month running expenses, top expense contributor, prior-month change, monthly history, and recent notable expenses.
- Home remains a snapshot dashboard and does not become the category analysis, transaction table, source coverage, or report explanation page.
- Reports does not duplicate Home KPI cards as primary content; it explains category drivers, classification coverage, source coverage, data quality, and review impact behind the Home numbers.
- Documents views show provenance first: document counts, source/type summaries, saved records, quality, row counts, review counts, and source drilldowns.
- Reports includes selected reporting period, currency, data readiness/classification coverage, source context, and review impact.
- Each displayed financial number can trace to M9 source document/transaction/evidence metadata when available.
- Power BI/Fabric are treated as analytical services over curated M9 data; Stats Web renders the primary product-facing dashboard and report investigation experience.
- A full pasted Power BI report canvas is not required for the default Reports UX and should not be the only way users understand reporting results.
- Missing Power BI/Fabric configuration does not block native document/provenance and operational workflow views.
- No secrets, real connection strings, tenant IDs, subscription IDs, passwords, or secret values are committed.

<!-- M11 End -->
