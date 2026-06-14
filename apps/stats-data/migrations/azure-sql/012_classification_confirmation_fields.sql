-- M8/M9 - Classification Confirmation Persistence Start
-- Stores manual Upload review confirmation metadata for AI-assisted classifications.

IF COL_LENGTH('dbo.transactions', 'classification_vocabulary_status') IS NULL
    ALTER TABLE dbo.transactions ADD classification_vocabulary_status nvarchar(80) NOT NULL CONSTRAINT df_transactions_classification_vocabulary_status DEFAULT 'active_vocabulary_match';

IF COL_LENGTH('dbo.transactions', 'recognition_context_version') IS NULL
    ALTER TABLE dbo.transactions ADD recognition_context_version nvarchar(80) NULL;

IF COL_LENGTH('dbo.transactions', 'classification_confirmation_mode') IS NULL
    ALTER TABLE dbo.transactions ADD classification_confirmation_mode nvarchar(80) NULL;

IF COL_LENGTH('dbo.transactions', 'classification_human_confirmed') IS NULL
    ALTER TABLE dbo.transactions ADD classification_human_confirmed bit NOT NULL CONSTRAINT df_transactions_classification_human_confirmed DEFAULT 0;

IF COL_LENGTH('dbo.transactions', 'classification_confirmed_by_user_id') IS NULL
    ALTER TABLE dbo.transactions ADD classification_confirmed_by_user_id nvarchar(120) NULL;

IF COL_LENGTH('dbo.transactions', 'classification_confirmed_at_utc') IS NULL
    ALTER TABLE dbo.transactions ADD classification_confirmed_at_utc datetime2(3) NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_transactions_classification_confirmation' AND object_id = OBJECT_ID('dbo.transactions'))
    CREATE INDEX ix_transactions_classification_confirmation
        ON dbo.transactions(classification_human_confirmed, classification_vocabulary_status, recognition_context_version);

-- M8/M9 - Classification Confirmation Persistence End
