-- M9 - Stats Data and Persistence Start
-- Adds pre-save duplicate-check persistence for documents and transactions.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '005_duplicate_check_results')
BEGIN
    IF COL_LENGTH('dbo.stats_documents', 'document_fingerprint') IS NULL
        ALTER TABLE dbo.stats_documents ADD document_fingerprint nvarchar(64) NULL;

    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes WHERE name = 'ix_stats_documents_user_hash_fingerprint'
    )
        CREATE INDEX ix_stats_documents_user_hash_fingerprint
            ON dbo.stats_documents(uploaded_by_user_id, sha256, document_fingerprint);

    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'duplicate_check_batches' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.duplicate_check_batches (
            duplicate_check_id nvarchar(36) NOT NULL CONSTRAINT pk_duplicate_check_batches PRIMARY KEY,
            validation_id nvarchar(100) NULL,
            document_id nvarchar(36) NOT NULL,
            uploaded_by_user_id nvarchar(36) NULL,
            saved_by_user_id nvarchar(36) NULL,
            status nvarchar(50) NOT NULL,
            total_record_count int NOT NULL CONSTRAINT df_duplicate_check_batches_total_record_count DEFAULT 0,
            exact_file_duplicate_count int NOT NULL CONSTRAINT df_duplicate_check_batches_exact_file_count DEFAULT 0,
            possible_document_duplicate_count int NOT NULL CONSTRAINT df_duplicate_check_batches_possible_document_count DEFAULT 0,
            within_batch_duplicate_count int NOT NULL CONSTRAINT df_duplicate_check_batches_within_batch_count DEFAULT 0,
            exact_transaction_duplicate_count int NOT NULL CONSTRAINT df_duplicate_check_batches_exact_transaction_count DEFAULT 0,
            possible_transaction_duplicate_count int NOT NULL CONSTRAINT df_duplicate_check_batches_possible_transaction_count DEFAULT 0,
            ready_to_save_count int NOT NULL CONSTRAINT df_duplicate_check_batches_ready_count DEFAULT 0,
            summary_json nvarchar(max) NOT NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_duplicate_check_batches_created_at DEFAULT SYSUTCDATETIME(),
            CONSTRAINT fk_duplicate_check_batches_stats_documents
                FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
            CONSTRAINT ck_duplicate_check_batches_summary_json CHECK (ISJSON(summary_json) = 1)
        );

        CREATE INDEX ix_duplicate_check_batches_document_created
            ON dbo.duplicate_check_batches(document_id, created_at_utc);
    END;

    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'duplicate_check_results' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.duplicate_check_results (
            duplicate_check_result_id nvarchar(36) NOT NULL CONSTRAINT pk_duplicate_check_results PRIMARY KEY,
            duplicate_check_id nvarchar(36) NOT NULL,
            document_id nvarchar(36) NOT NULL,
            record_id nvarchar(100) NULL,
            result_scope nvarchar(50) NOT NULL,
            match_type nvarchar(80) NOT NULL,
            match_status nvarchar(50) NOT NULL,
            matched_document_id nvarchar(36) NULL,
            matched_transaction_id nvarchar(36) NULL,
            confidence decimal(9,6) NULL,
            reason_codes_json nvarchar(max) NOT NULL,
            message nvarchar(1000) NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_duplicate_check_results_created_at DEFAULT SYSUTCDATETIME(),
            CONSTRAINT fk_duplicate_check_results_batches
                FOREIGN KEY (duplicate_check_id) REFERENCES dbo.duplicate_check_batches(duplicate_check_id),
            CONSTRAINT fk_duplicate_check_results_document
                FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
            CONSTRAINT fk_duplicate_check_results_matched_document
                FOREIGN KEY (matched_document_id) REFERENCES dbo.stats_documents(document_id),
            CONSTRAINT fk_duplicate_check_results_matched_transaction
                FOREIGN KEY (matched_transaction_id) REFERENCES dbo.transactions(transaction_id),
            CONSTRAINT ck_duplicate_check_results_reason_codes_json CHECK (ISJSON(reason_codes_json) = 1)
        );

        CREATE INDEX ix_duplicate_check_results_batch_scope
            ON dbo.duplicate_check_results(duplicate_check_id, result_scope, match_type);
    END;

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('005_duplicate_check_results');
END;
GO

-- M9 End
