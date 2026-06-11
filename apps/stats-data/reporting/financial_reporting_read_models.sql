-- M11 - Stats Dashboard and Reporting Start
-- Draft M11 reporting read models for Power BI/Fabric.
--
-- Ownership note:
-- These are proposed M9-owned Azure SQL read models. They are intentionally
-- stored outside the migrations folder until M9 accepts them as a schema change.
-- M11/Power BI should consume read models like these instead of parsing raw
-- validation payload JSON or duplicating business logic in the browser.

CREATE OR ALTER VIEW dbo.vw_reporting_transactions AS
SELECT
    t.transaction_id,
    t.document_id,
    t.transaction_batch_id,
    t.transaction_date,
    t.posted_date,
    t.description,
    t.normalized_description,
    t.amount,
    t.currency,
    t.direction,
    t.signed_amount,
    CASE
        WHEN LOWER(t.direction) = 'debit' THEN ABS(t.amount)
        ELSE CAST(NULL AS decimal(19, 4))
    END AS expense_amount,
    CASE
        WHEN LOWER(t.direction) = 'credit' THEN ABS(t.amount)
        ELSE CAST(NULL AS decimal(19, 4))
    END AS credit_amount,
    t.source_institution,
    COALESCE(NULLIF(t.merchant_or_counterparty, ''), t.normalized_description, t.description) AS expense_contributor,
    t.merchant_or_counterparty,
    t.category,
    t.payment_method,
    t.masked_account_or_card,
    t.confidence,
    t.quality_status,
    t.review_required,
    t.source_page_number,
    t.source_line_number,
    t.source_text_redacted,
    d.original_filename,
    d.document_type,
    d.source_type,
    d.status AS document_status,
    d.ocr_quality_status,
    d.redaction_applied,
    t.created_at_utc,
    t.updated_at_utc
FROM dbo.transactions AS t
INNER JOIN dbo.stats_documents AS d
    ON d.document_id = t.document_id
WHERE t.duplicate_of_transaction_id IS NULL;
GO

CREATE OR ALTER VIEW dbo.vw_reporting_monthly_expenses AS
SELECT
    DATEFROMPARTS(YEAR(transaction_date), MONTH(transaction_date), 1) AS month_start_date,
    currency,
    SUM(CASE WHEN LOWER(direction) = 'debit' THEN ABS(amount) ELSE 0 END) AS expense_total,
    SUM(CASE WHEN LOWER(direction) = 'credit' THEN ABS(amount) ELSE 0 END) AS credit_total,
    SUM(CASE WHEN LOWER(direction) = 'credit' THEN ABS(amount) ELSE 0 END)
        - SUM(CASE WHEN LOWER(direction) = 'debit' THEN ABS(amount) ELSE 0 END) AS net_movement,
    COUNT_BIG(*) AS transaction_count,
    SUM(CASE WHEN review_required = 1 THEN 1 ELSE 0 END) AS review_required_count
FROM dbo.transactions
WHERE duplicate_of_transaction_id IS NULL
GROUP BY
    DATEFROMPARTS(YEAR(transaction_date), MONTH(transaction_date), 1),
    currency;
GO

CREATE OR ALTER VIEW dbo.vw_reporting_top_expense_contributors AS
SELECT
    DATEFROMPARTS(YEAR(t.transaction_date), MONTH(t.transaction_date), 1) AS month_start_date,
    t.currency,
    COALESCE(NULLIF(t.merchant_or_counterparty, ''), t.category, t.normalized_description, t.description) AS expense_contributor,
    t.category,
    t.source_institution,
    SUM(ABS(t.amount)) AS expense_total,
    COUNT_BIG(*) AS transaction_count,
    MAX(t.transaction_date) AS latest_transaction_date
FROM dbo.transactions AS t
WHERE t.duplicate_of_transaction_id IS NULL
    AND LOWER(t.direction) = 'debit'
GROUP BY
    DATEFROMPARTS(YEAR(t.transaction_date), MONTH(t.transaction_date), 1),
    t.currency,
    COALESCE(NULLIF(t.merchant_or_counterparty, ''), t.category, t.normalized_description, t.description),
    t.category,
    t.source_institution;
GO

CREATE OR ALTER VIEW dbo.vw_reporting_upcoming_obligations AS
SELECT
    ss.statement_summary_id AS obligation_id,
    ss.document_id,
    CAST('statement' AS nvarchar(40)) AS obligation_type,
    ss.payment_due_date AS due_date,
    ss.minimum_amount_due,
    ss.total_amount_due AS amount_due,
    ss.outstanding_balance,
    ss.installment_balance,
    ss.currency,
    ss.quality_status,
    d.original_filename,
    d.document_type,
    d.source_institution,
    d.source_type,
    d.status AS document_status
FROM dbo.statement_summaries AS ss
INNER JOIN dbo.stats_documents AS d
    ON d.document_id = ss.document_id
WHERE ss.payment_due_date IS NOT NULL
    AND ss.total_amount_due IS NOT NULL

UNION ALL

SELECT
    dfs.document_financial_summary_id AS obligation_id,
    dfs.document_id,
    CAST('invoice' AS nvarchar(40)) AS obligation_type,
    dfs.issue_date AS due_date,
    CAST(NULL AS decimal(19, 4)) AS minimum_amount_due,
    COALESCE(dfs.owing_amount, dfs.total_amount) AS amount_due,
    dfs.owing_amount AS outstanding_balance,
    CAST(NULL AS decimal(19, 4)) AS installment_balance,
    dfs.currency,
    dfs.quality_status,
    d.original_filename,
    d.document_type,
    d.source_institution,
    d.source_type,
    d.status AS document_status
FROM dbo.document_financial_summaries AS dfs
INNER JOIN dbo.stats_documents AS d
    ON d.document_id = dfs.document_id
WHERE COALESCE(dfs.owing_amount, dfs.total_amount) IS NOT NULL
    AND LOWER(COALESCE(dfs.payment_status, 'owing')) NOT IN ('paid', 'settled', 'closed');
GO

CREATE OR ALTER VIEW dbo.vw_reporting_recent_notable_expenses AS
SELECT TOP (100)
    t.transaction_id,
    t.document_id,
    t.transaction_date,
    t.description,
    COALESCE(NULLIF(t.merchant_or_counterparty, ''), t.normalized_description, t.description) AS expense_contributor,
    t.category,
    ABS(t.amount) AS expense_amount,
    t.currency,
    t.source_institution,
    t.quality_status,
    t.review_required,
    f.severity AS finding_severity,
    f.code AS finding_code,
    f.message AS finding_message,
    t.source_text_redacted,
    d.original_filename,
    d.document_type
FROM dbo.transactions AS t
INNER JOIN dbo.stats_documents AS d
    ON d.document_id = t.document_id
LEFT JOIN dbo.findings AS f
    ON f.transaction_id = t.transaction_id
    AND LOWER(f.status) NOT IN ('resolved', 'closed')
WHERE t.duplicate_of_transaction_id IS NULL
    AND LOWER(t.direction) = 'debit'
ORDER BY
    CASE WHEN t.review_required = 1 THEN 0 ELSE 1 END,
    ABS(t.amount) DESC,
    t.transaction_date DESC;
GO

CREATE OR ALTER VIEW dbo.vw_reporting_document_provenance AS
SELECT
    d.document_id,
    d.original_filename,
    d.source_type,
    d.document_type,
    d.source_institution,
    d.status,
    d.ocr_quality_status,
    d.redaction_applied,
    d.created_at_utc,
    d.updated_at_utc,
    COUNT(DISTINCT t.transaction_id) AS transaction_count,
    COUNT(DISTINCT ff.financial_field_id) AS financial_field_count,
    COUNT(DISTINCT ri.review_item_id) AS review_item_count
FROM dbo.stats_documents AS d
LEFT JOIN dbo.transactions AS t
    ON t.document_id = d.document_id
LEFT JOIN dbo.financial_fields AS ff
    ON ff.document_id = d.document_id
LEFT JOIN dbo.review_items AS ri
    ON ri.document_id = d.document_id
GROUP BY
    d.document_id,
    d.original_filename,
    d.source_type,
    d.document_type,
    d.source_institution,
    d.status,
    d.ocr_quality_status,
    d.redaction_applied,
    d.created_at_utc,
    d.updated_at_utc;
GO

-- M11 End
