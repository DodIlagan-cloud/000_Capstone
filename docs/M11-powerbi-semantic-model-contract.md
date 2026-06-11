<!-- M11 - Stats Dashboard and Reporting Start -->
<!-- Defines the first Power BI semantic model contract for the M11 financial KPI dashboard. -->

# M11 Power BI Semantic Model Contract

## Purpose

This contract defines the first Power BI semantic model for M11. It uses curated M9 Azure SQL data as the source of truth and supports the first financial KPI report embedded into Stats Web.

The model must not read raw OCR text, full uploaded documents, secrets, connection strings, or unredacted evidence. It may use redacted source snippets and masked references supplied by M9.

## Fabric Workspace

| Field | Value |
| --- | --- |
| Workspace | `Stats - Dev - Reporting` |
| Capacity | `capstatsdev001` |
| Capacity SKU | `F2` |
| Region | `Australia East` |
| Workspace type | `Fabric` |
| Semantic model storage | Small semantic model storage format |
| Cost state when idle | Capacity paused |

## First Model Name

```text
Stats Financial KPIs Dev
```

## Source Boundary

M9 owns Azure SQL schema, persistence, migrations, and operational read APIs. M11/Power BI consumes reporting-ready tables or views only.

Initial direct source tables:

| Table | Purpose |
| --- | --- |
| `dbo.transactions` | Expense totals, current-month running totals, trends, top contributors, notable expenses |
| `dbo.stats_documents` | Source institution, document type, upload/source metadata, provenance |
| `dbo.statement_summaries` | Statement due dates, balances, and payable summary fields |
| `dbo.document_financial_summaries` | Invoice/receipt/payment-proof totals and owing status |
| `dbo.findings` | Notable data-quality or system issues attached to records |
| `dbo.review_items` | Review backlog and trust indicators |

Future preferred source:

```text
dbo.vw_reporting_transactions
dbo.vw_reporting_monthly_expenses
dbo.vw_reporting_top_expense_contributors
dbo.vw_reporting_upcoming_obligations
dbo.vw_reporting_recent_notable_expenses
dbo.vw_reporting_document_provenance
```

These views are M9-owned read models. M11 should request them from M9 rather than creating them as ad hoc browser logic.

## Relationships

| From | To | Cardinality | Notes |
| --- | --- | --- | --- |
| `transactions.document_id` | `stats_documents.document_id` | Many-to-one | Source provenance for each transaction |
| `statement_summaries.document_id` | `stats_documents.document_id` | Many-to-one | Statement evidence |
| `document_financial_summaries.document_id` | `stats_documents.document_id` | Many-to-one | Invoice/receipt/payment-proof evidence |
| `findings.document_id` | `stats_documents.document_id` | Many-to-one | Document-level issues |
| `findings.transaction_id` | `transactions.transaction_id` | Many-to-one | Transaction-level issues |
| `review_items.document_id` | `stats_documents.document_id` | Many-to-one | Document-level review tasks |
| `review_items.transaction_id` | `transactions.transaction_id` | Many-to-one | Transaction-level review tasks |

## Base Columns

### Transactions

Include:

- `transaction_id`
- `document_id`
- `transaction_date`
- `posted_date`
- `description`
- `normalized_description`
- `amount`
- `currency`
- `direction`
- `signed_amount`
- `source_institution`
- `merchant_or_counterparty`
- `category`
- `payment_method`
- `masked_account_or_card`
- `confidence`
- `quality_status`
- `review_required`
- `source_page_number`
- `source_line_number`
- `source_text_redacted`
- `created_at_utc`

Calculated columns:

```DAX
Expense Amount =
IF (
    LOWER ( 'transactions'[direction] ) = "debit",
    ABS ( 'transactions'[amount] ),
    BLANK ()
)
```

```DAX
Income Amount =
IF (
    LOWER ( 'transactions'[direction] ) = "credit",
    ABS ( 'transactions'[amount] ),
    BLANK ()
)
```

### Documents

Include:

- `document_id`
- `original_filename`
- `source_type`
- `document_type`
- `source_institution`
- `status`
- `ocr_quality_status`
- `redaction_applied`
- `created_at_utc`
- `updated_at_utc`

### Statement Summaries

Include:

- `statement_summary_id`
- `document_id`
- `statement_date`
- `period_start_date`
- `period_end_date`
- `payment_due_date`
- `minimum_amount_due`
- `total_amount_due`
- `outstanding_balance`
- `available_credit`
- `installment_balance`
- `currency`
- `quality_status`

### Document Financial Summaries

Include:

- `document_financial_summary_id`
- `document_id`
- `invoice_number`
- `issue_date`
- `total_amount`
- `paid_amount`
- `owing_amount`
- `currency`
- `payment_status`
- `quality_status`

## Core Measures

```DAX
Total Expenses =
SUMX (
    FILTER ( 'transactions', LOWER ( 'transactions'[direction] ) = "debit" ),
    ABS ( 'transactions'[amount] )
)
```

```DAX
Total Credits =
SUMX (
    FILTER ( 'transactions', LOWER ( 'transactions'[direction] ) = "credit" ),
    ABS ( 'transactions'[amount] )
)
```

```DAX
Net Movement =
[Total Credits] - [Total Expenses]
```

```DAX
Last Month Expenses =
CALCULATE (
    [Total Expenses],
    PREVIOUSMONTH ( 'Date'[Date] )
)
```

```DAX
This Month Running Expenses =
CALCULATE (
    [Total Expenses],
    DATESMTD ( 'Date'[Date] )
)
```

```DAX
Review Required Count =
CALCULATE (
    COUNTROWS ( 'transactions' ),
    'transactions'[review_required] = TRUE ()
)
```

```DAX
Open Review Items =
CALCULATE (
    COUNTROWS ( 'review_items' ),
    NOT ( LOWER ( 'review_items'[status] ) IN { "resolved", "closed", "accepted" } )
)
```

```DAX
Upcoming Payable =
VAR NextStatementDue =
    CALCULATE (
        MIN ( 'statement_summaries'[payment_due_date] ),
        'statement_summaries'[payment_due_date] >= TODAY ()
    )
RETURN
    CALCULATE (
        SUM ( 'statement_summaries'[total_amount_due] ),
        'statement_summaries'[payment_due_date] = NextStatementDue
    )
```

```DAX
Top Contributor Amount =
MAXX (
    SUMMARIZE (
        'transactions',
        'transactions'[merchant_or_counterparty],
        "ContributorExpense", [Total Expenses]
    ),
    [ContributorExpense]
)
```

## First Report Page

Page name:

```text
Financial Overview
```

Visuals:

| Visual | Backing measure/table | Notes |
| --- | --- | --- |
| KPI card: Last month expenses | `Last Month Expenses` | Primary home KPI |
| KPI card: This month running expenses | `This Month Running Expenses` | Primary home KPI |
| KPI card: Top contributor | `Top Contributor Amount` plus merchant/category | Primary home KPI |
| Line chart: monthly spending history | `Total Expenses` by `Date[Month]` | Shows recent monthly totals for context |
| KPI card: Change vs prior month | `This Month Running Expenses - Prior Month Expenses` | Explains the compact trend delta shown in Stats Web |
| Bar chart: expense by contributor | `Total Expenses` by merchant/category | Drill candidate |
| Table: recent notable expenses | `transactions` filtered by high amount/review/finding | Evidence route candidate |

## Currency Direction

Initial model uses transaction currency as persisted by M9. The Stats Web currency selector is already present, but live converted values require an exchange-rate table or Fabric/M9 reference data.

Future currency tables:

```text
currency_dimension
exchange_rates
```

Default basis:

```text
transaction_date
```

## Embed Outputs Needed Later

After the Power BI report exists, capture these non-secret values for M11 runtime configuration:

- Workspace ID.
- Report ID.
- Dataset or semantic model ID.
- Default report page name.
- Capacity name.

Secrets remain in Key Vault or Container Apps secrets only.

<!-- M11 End -->
