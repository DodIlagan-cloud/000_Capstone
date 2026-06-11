-- Recognition label suggestion governance for admin approval and historical sync.

IF COL_LENGTH('dbo.transactions', 'recognition_suggestion_id') IS NULL
    ALTER TABLE dbo.transactions ADD recognition_suggestion_id nvarchar(120) NULL;

IF COL_LENGTH('dbo.transactions', 'recognition_suggestion_status') IS NULL
    ALTER TABLE dbo.transactions ADD recognition_suggestion_status nvarchar(40) NOT NULL CONSTRAINT df_transactions_recognition_suggestion_status DEFAULT 'none';

IF COL_LENGTH('dbo.transactions', 'suggested_transaction_type') IS NULL
    ALTER TABLE dbo.transactions ADD suggested_transaction_type nvarchar(80) NULL;

IF COL_LENGTH('dbo.transactions', 'suggested_transaction_subtype') IS NULL
    ALTER TABLE dbo.transactions ADD suggested_transaction_subtype nvarchar(100) NULL;

IF COL_LENGTH('dbo.transactions', 'suggested_spending_category') IS NULL
    ALTER TABLE dbo.transactions ADD suggested_spending_category nvarchar(100) NULL;

IF COL_LENGTH('dbo.transactions', 'suggested_spending_subcategory') IS NULL
    ALTER TABLE dbo.transactions ADD suggested_spending_subcategory nvarchar(100) NULL;

IF COL_LENGTH('dbo.transactions', 'suggestion_confidence') IS NULL
    ALTER TABLE dbo.transactions ADD suggestion_confidence decimal(9,6) NULL;

IF COL_LENGTH('dbo.transactions', 'suggestion_reason_codes_json') IS NULL
    ALTER TABLE dbo.transactions ADD suggestion_reason_codes_json nvarchar(max) NULL;

IF COL_LENGTH('dbo.transactions', 'suggestion_source') IS NULL
    ALTER TABLE dbo.transactions ADD suggestion_source nvarchar(80) NULL;

IF COL_LENGTH('dbo.transactions', 'suggestion_evidence_ref') IS NULL
    ALTER TABLE dbo.transactions ADD suggestion_evidence_ref nvarchar(300) NULL;

IF OBJECT_ID('dbo.recognition_label_suggestions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.recognition_label_suggestions (
        suggestion_id nvarchar(120) NOT NULL CONSTRAINT pk_recognition_label_suggestions PRIMARY KEY,
        source_module nvarchar(40) NOT NULL,
        suggestion_status nvarchar(40) NOT NULL CONSTRAINT df_recognition_label_suggestions_status DEFAULT 'pending',
        document_id nvarchar(120) NULL,
        transaction_id nvarchar(120) NULL,
        source_candidate_id nvarchar(120) NULL,
        current_transaction_type nvarchar(80) NULL,
        current_transaction_subtype nvarchar(100) NULL,
        current_spending_category nvarchar(100) NULL,
        current_spending_subcategory nvarchar(100) NULL,
        suggested_transaction_type nvarchar(80) NULL,
        suggested_transaction_subtype nvarchar(100) NULL,
        suggested_spending_category nvarchar(100) NULL,
        suggested_spending_subcategory nvarchar(100) NULL,
        suggestion_confidence decimal(9,6) NULL,
        suggestion_reason_codes_json nvarchar(max) NULL,
        suggestion_source nvarchar(80) NULL,
        suggestion_evidence_ref nvarchar(300) NULL,
        created_at_utc datetime2 NOT NULL CONSTRAINT df_recognition_label_suggestions_created DEFAULT SYSUTCDATETIME(),
        reviewed_at_utc datetime2 NULL,
        reviewed_by_user_id nvarchar(120) NULL,
        review_action nvarchar(60) NULL,
        review_note nvarchar(1000) NULL
    );
END;

IF OBJECT_ID('dbo.recognition_config_changes', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.recognition_config_changes (
        config_change_id nvarchar(120) NOT NULL CONSTRAINT pk_recognition_config_changes PRIMARY KEY,
        suggestion_id nvarchar(120) NULL,
        admin_user_id nvarchar(120) NULL,
        action_type nvarchar(60) NOT NULL,
        config_file nvarchar(260) NOT NULL,
        before_label nvarchar(160) NULL,
        after_label nvarchar(160) NULL,
        before_values_json nvarchar(max) NULL,
        after_values_json nvarchar(max) NULL,
        change_reason nvarchar(1000) NULL,
        created_at_utc datetime2 NOT NULL CONSTRAINT df_recognition_config_changes_created DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID('dbo.recognition_label_sync_runs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.recognition_label_sync_runs (
        sync_run_id nvarchar(120) NOT NULL CONSTRAINT pk_recognition_label_sync_runs PRIMARY KEY,
        config_change_id nvarchar(120) NULL,
        sync_policy nvarchar(80) NOT NULL,
        label_field nvarchar(80) NOT NULL,
        old_value nvarchar(160) NULL,
        new_value nvarchar(160) NULL,
        affected_row_count int NOT NULL CONSTRAINT df_recognition_label_sync_runs_affected DEFAULT 0,
        status nvarchar(40) NOT NULL CONSTRAINT df_recognition_label_sync_runs_status DEFAULT 'completed',
        failure_detail nvarchar(1000) NULL,
        started_at_utc datetime2 NOT NULL CONSTRAINT df_recognition_label_sync_runs_started DEFAULT SYSUTCDATETIME(),
        completed_at_utc datetime2 NULL
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'ix_transactions_recognition_suggestions'
      AND object_id = OBJECT_ID('dbo.transactions')
)
    CREATE INDEX ix_transactions_recognition_suggestions
        ON dbo.transactions(recognition_suggestion_status, recognition_suggestion_id);
