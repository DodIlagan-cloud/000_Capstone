-- M9 - Stats Data and Persistence Start
-- Adds durable per-step timing summaries for upload processing jobs.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '007_document_processing_steps')
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'document_processing_steps' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.document_processing_steps (
            step_id nvarchar(36) NOT NULL CONSTRAINT pk_document_processing_steps PRIMARY KEY,
            job_id nvarchar(36) NOT NULL,
            document_id nvarchar(64) NULL,
            correlation_id nvarchar(100) NULL,
            module_name nvarchar(50) NOT NULL,
            step_name nvarchar(100) NOT NULL,
            status nvarchar(50) NOT NULL,
            started_at_utc datetime2(3) NOT NULL,
            completed_at_utc datetime2(3) NULL,
            duration_ms bigint NULL,
            metadata_json nvarchar(max) NULL,
            error_code nvarchar(100) NULL,
            error_message nvarchar(1000) NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_document_processing_steps_created_at DEFAULT SYSUTCDATETIME(),
            CONSTRAINT fk_document_processing_steps_job
                FOREIGN KEY (job_id) REFERENCES dbo.document_processing_jobs(job_id)
                ON DELETE CASCADE,
            CONSTRAINT ck_document_processing_steps_metadata_json
                CHECK (metadata_json IS NULL OR ISJSON(metadata_json) = 1)
        );

        CREATE INDEX ix_document_processing_steps_job_created
            ON dbo.document_processing_steps(job_id, created_at_utc);

        CREATE INDEX ix_document_processing_steps_step_status
            ON dbo.document_processing_steps(step_name, status, created_at_utc DESC);
    END;

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('007_document_processing_steps');
END;
GO

-- M9 End
