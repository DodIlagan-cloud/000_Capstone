-- M9 - Stats Data and Persistence Start
-- Keeps duplicate-check audit rows from creating candidate stats_documents rows.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '014_duplicate_check_candidate_document')
BEGIN
    IF COL_LENGTH('dbo.duplicate_check_batches', 'candidate_document_id') IS NULL
        ALTER TABLE dbo.duplicate_check_batches ADD candidate_document_id nvarchar(36) NULL;

    IF COL_LENGTH('dbo.duplicate_check_results', 'candidate_document_id') IS NULL
        ALTER TABLE dbo.duplicate_check_results ADD candidate_document_id nvarchar(36) NULL;

    EXEC(N'
        UPDATE dbo.duplicate_check_batches
        SET candidate_document_id = document_id
        WHERE candidate_document_id IS NULL;
    ');

    EXEC(N'
        UPDATE dbo.duplicate_check_results
        SET candidate_document_id = document_id
        WHERE candidate_document_id IS NULL;
    ');

    IF EXISTS (
        SELECT 1
        FROM sys.foreign_keys
        WHERE name = 'fk_duplicate_check_batches_stats_documents'
          AND parent_object_id = OBJECT_ID('dbo.duplicate_check_batches')
    )
        ALTER TABLE dbo.duplicate_check_batches DROP CONSTRAINT fk_duplicate_check_batches_stats_documents;

    IF EXISTS (
        SELECT 1
        FROM sys.foreign_keys
        WHERE name = 'fk_duplicate_check_results_document'
          AND parent_object_id = OBJECT_ID('dbo.duplicate_check_results')
    )
        ALTER TABLE dbo.duplicate_check_results DROP CONSTRAINT fk_duplicate_check_results_document;

    IF EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = 'ix_duplicate_check_batches_document_created'
          AND object_id = OBJECT_ID('dbo.duplicate_check_batches')
    )
        DROP INDEX ix_duplicate_check_batches_document_created ON dbo.duplicate_check_batches;

    ALTER TABLE dbo.duplicate_check_batches ALTER COLUMN document_id nvarchar(36) NULL;
    ALTER TABLE dbo.duplicate_check_results ALTER COLUMN document_id nvarchar(36) NULL;

    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes WHERE name = 'ix_duplicate_check_batches_document_created'
    )
        CREATE INDEX ix_duplicate_check_batches_document_created
            ON dbo.duplicate_check_batches(document_id, created_at_utc);

    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes WHERE name = 'ix_duplicate_check_batches_candidate_created'
    )
        EXEC(N'
            CREATE INDEX ix_duplicate_check_batches_candidate_created
                ON dbo.duplicate_check_batches(candidate_document_id, created_at_utc);
        ');

    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes WHERE name = 'ix_duplicate_check_results_candidate_scope'
    )
        EXEC(N'
            CREATE INDEX ix_duplicate_check_results_candidate_scope
                ON dbo.duplicate_check_results(candidate_document_id, result_scope, match_type);
        ');

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('014_duplicate_check_candidate_document');
END;
GO

-- M9 End
