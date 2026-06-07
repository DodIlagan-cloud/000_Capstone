-- M9 - Stats Data and Persistence Start
-- Adds durable upload processing-job tracking for cloud-safe async workflows.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '006_document_processing_jobs')
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'document_processing_jobs' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.document_processing_jobs (
            job_id nvarchar(36) NOT NULL CONSTRAINT pk_document_processing_jobs PRIMARY KEY,
            ingestion_id nvarchar(100) NULL,
            uploaded_by_user_id nvarchar(36) NULL,
            original_filename nvarchar(255) NOT NULL,
            source_type nvarchar(50) NOT NULL,
            source_id nvarchar(100) NULL,
            sha256 nvarchar(64) NULL,
            status nvarchar(50) NOT NULL,
            stage nvarchar(50) NOT NULL,
            message nvarchar(1000) NULL,
            parse_id nvarchar(100) NULL,
            extraction_id nvarchar(100) NULL,
            validation_id nvarchar(100) NULL,
            result_payload_json nvarchar(max) NULL,
            error_detail nvarchar(2000) NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_document_processing_jobs_created_at DEFAULT SYSUTCDATETIME(),
            updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_document_processing_jobs_updated_at DEFAULT SYSUTCDATETIME(),
            completed_at_utc datetime2(3) NULL,
            CONSTRAINT ck_document_processing_jobs_result_json CHECK (result_payload_json IS NULL OR ISJSON(result_payload_json) = 1)
        );

        CREATE INDEX ix_document_processing_jobs_user_status
            ON dbo.document_processing_jobs(uploaded_by_user_id, status, created_at_utc DESC);

        CREATE INDEX ix_document_processing_jobs_ingestion
            ON dbo.document_processing_jobs(ingestion_id);
    END;

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('006_document_processing_jobs');
END;
GO

-- M9 End
