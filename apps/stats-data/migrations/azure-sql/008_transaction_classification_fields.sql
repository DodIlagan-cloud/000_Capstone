-- M7/M9 - Transaction Classification Persistence Start
-- Stores user-reviewed transaction labels for reporting and audit.

IF COL_LENGTH('dbo.transactions', 'transaction_type') IS NULL
    ALTER TABLE dbo.transactions ADD transaction_type nvarchar(80) NOT NULL CONSTRAINT df_transactions_transaction_type DEFAULT 'unknown';

IF COL_LENGTH('dbo.transactions', 'transaction_subtype') IS NULL
    ALTER TABLE dbo.transactions ADD transaction_subtype nvarchar(100) NOT NULL CONSTRAINT df_transactions_transaction_subtype DEFAULT 'unknown';

IF COL_LENGTH('dbo.transactions', 'spending_category') IS NULL
    ALTER TABLE dbo.transactions ADD spending_category nvarchar(100) NOT NULL CONSTRAINT df_transactions_spending_category DEFAULT 'uncategorized';

IF COL_LENGTH('dbo.transactions', 'spending_subcategory') IS NULL
    ALTER TABLE dbo.transactions ADD spending_subcategory nvarchar(100) NOT NULL CONSTRAINT df_transactions_spending_subcategory DEFAULT 'unknown';

IF COL_LENGTH('dbo.transactions', 'classification_source') IS NULL
    ALTER TABLE dbo.transactions ADD classification_source nvarchar(80) NOT NULL CONSTRAINT df_transactions_classification_source DEFAULT 'unknown';

IF COL_LENGTH('dbo.transactions', 'classification_review_required') IS NULL
    ALTER TABLE dbo.transactions ADD classification_review_required bit NOT NULL CONSTRAINT df_transactions_classification_review_required DEFAULT 0;

IF COL_LENGTH('dbo.transactions', 'classification_review_reason_codes_json') IS NULL
    ALTER TABLE dbo.transactions ADD classification_review_reason_codes_json nvarchar(max) NULL;

IF COL_LENGTH('dbo.transactions', 'classification_ai_model_name') IS NULL
    ALTER TABLE dbo.transactions ADD classification_ai_model_name nvarchar(150) NULL;

IF COL_LENGTH('dbo.transactions', 'classification_ai_model_version') IS NULL
    ALTER TABLE dbo.transactions ADD classification_ai_model_version nvarchar(150) NULL;

IF COL_LENGTH('dbo.transactions', 'classification_ai_confidence') IS NULL
    ALTER TABLE dbo.transactions ADD classification_ai_confidence decimal(9,6) NULL;

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'ck_transactions_classification_review_reason_codes_json')
    EXEC(N'ALTER TABLE dbo.transactions ADD CONSTRAINT ck_transactions_classification_review_reason_codes_json CHECK (classification_review_reason_codes_json IS NULL OR ISJSON(classification_review_reason_codes_json) = 1);');

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_transactions_classification_reporting' AND object_id = OBJECT_ID('dbo.transactions'))
    CREATE INDEX ix_transactions_classification_reporting
        ON dbo.transactions(transaction_type, spending_category, quality_status);

-- M7/M9 - Transaction Classification Persistence End
