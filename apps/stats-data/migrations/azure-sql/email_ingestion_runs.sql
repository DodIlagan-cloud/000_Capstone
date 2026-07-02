-- M12 - Email Ingestion Module Start
-- Stores email ingestion run history and content-free candidate rows.
-- Candidate rows carry a dedup_key so repeated runs do not re-import the same
-- mailbox attachment. No attachment content, mailbox passwords, or PDF passwords
-- are stored here.
--
-- SCHEMA NOTE: this migration creates the M12 tables in dbo. The M12 runtime
-- reads DATABASE_SCHEMA (default dbo) when qualifying table names, so if you
-- change DATABASE_SCHEMA you must also create these tables in that schema -
-- the migrations do not parameterize it. Keep DATABASE_SCHEMA=dbo for M12
-- unless the migrations are edited to match.

IF OBJECT_ID('dbo.email_ingestion_runs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.email_ingestion_runs (
        run_id nvarchar(80) NOT NULL CONSTRAINT pk_email_ingestion_runs PRIMARY KEY,
        source_id nvarchar(120) NOT NULL,
        mode nvarchar(40) NOT NULL CONSTRAINT df_email_runs_mode DEFAULT 'dry_run',
        status nvarchar(40) NOT NULL,
        started_at_utc datetime2(3) NULL,
        completed_at_utc datetime2(3) NULL,
        correlation_id nvarchar(80) NULL,
        error_message nvarchar(2000) NULL,
        summary_json nvarchar(max) NOT NULL CONSTRAINT df_email_runs_summary DEFAULT '{}',
        message_count int NOT NULL CONSTRAINT df_email_runs_message_count DEFAULT 0,
        attachment_count int NOT NULL CONSTRAINT df_email_runs_attachment_count DEFAULT 0,
        retrieved_count int NOT NULL CONSTRAINT df_email_runs_retrieved_count DEFAULT 0,
        handed_off_count int NOT NULL CONSTRAINT df_email_runs_handed_off_count DEFAULT 0,
        skipped_count int NOT NULL CONSTRAINT df_email_runs_skipped_count DEFAULT 0,
        duplicate_count int NOT NULL CONSTRAINT df_email_runs_duplicate_count DEFAULT 0,
        failed_count int NOT NULL CONSTRAINT df_email_runs_failed_count DEFAULT 0,
        password_required_count int NOT NULL CONSTRAINT df_email_runs_password_required_count DEFAULT 0,
        password_failed_count int NOT NULL CONSTRAINT df_email_runs_password_failed_count DEFAULT 0,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_runs_created_at DEFAULT SYSUTCDATETIME()
    );
END;

-- Evidence column for configured-password unlock failures (mirrors the summary
-- model); added separately so existing databases pick it up.
IF COL_LENGTH('dbo.email_ingestion_runs', 'password_failed_count') IS NULL
    ALTER TABLE dbo.email_ingestion_runs
        ADD password_failed_count int NOT NULL
            CONSTRAINT df_email_runs_password_failed_count DEFAULT 0;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_email_runs_source_started' AND object_id = OBJECT_ID('dbo.email_ingestion_runs'))
    CREATE INDEX ix_email_runs_source_started
        ON dbo.email_ingestion_runs(source_id, started_at_utc DESC);

IF OBJECT_ID('dbo.email_ingestion_run_candidates', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.email_ingestion_run_candidates (
        id bigint IDENTITY(1, 1) NOT NULL CONSTRAINT pk_email_ingestion_run_candidates PRIMARY KEY,
        run_id nvarchar(80) NOT NULL,
        source_id nvarchar(120) NOT NULL,
        candidate_id nvarchar(80) NOT NULL,
        filename nvarchar(400) NOT NULL,
        status nvarchar(40) NOT NULL,
        sender nvarchar(400) NULL,
        subject_redacted nvarchar(400) NULL,
        received_at nvarchar(80) NULL,
        message_id nvarchar(400) NULL,
        attachment_id nvarchar(120) NULL,
        sha256 nvarchar(80) NULL,
        original_sha256 nvarchar(80) NULL,
        dedup_key nvarchar(700) NULL,
        handoff_ingestion_id nvarchar(120) NULL,
        handoff_status nvarchar(40) NULL,
        handoff_content_reference nvarchar(1000) NULL,
        handoff_error nvarchar(2000) NULL,
        finding_codes_json nvarchar(max) NOT NULL CONSTRAINT df_email_run_candidates_findings DEFAULT '[]',
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_run_candidates_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_email_run_candidates_run FOREIGN KEY (run_id)
            REFERENCES dbo.email_ingestion_runs(run_id) ON DELETE CASCADE
    );
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_email_run_candidates_run' AND object_id = OBJECT_ID('dbo.email_ingestion_run_candidates'))
    CREATE INDEX ix_email_run_candidates_run
        ON dbo.email_ingestion_run_candidates(run_id);

-- Provenance for rule-unlocked PDFs: sha256 holds the handed-off (decrypted)
-- content hash; original_sha256 keeps the encrypted-source hash when it differs.
IF COL_LENGTH('dbo.email_ingestion_run_candidates', 'original_sha256') IS NULL
    ALTER TABLE dbo.email_ingestion_run_candidates
        ADD original_sha256 nvarchar(80) NULL;

-- Supports the cross-run dedup lookup: "has this attachment identity already
-- been imported (handed_off) by a prior run?"
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_email_run_candidates_dedup_status' AND object_id = OBJECT_ID('dbo.email_ingestion_run_candidates'))
    CREATE INDEX ix_email_run_candidates_dedup_status
        ON dbo.email_ingestion_run_candidates(dedup_key) INCLUDE (status);

-- Idempotency marker: an attachment whose stored bytes were already pushed through
-- the pipeline (manual button or scheduler) must not be saved to M9 twice.
IF OBJECT_ID('dbo.email_ingestion_processed', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.email_ingestion_processed (
        ingestion_id nvarchar(120) NOT NULL CONSTRAINT pk_email_ingestion_processed PRIMARY KEY,
        document_id nvarchar(120) NULL,
        run_id nvarchar(80) NULL,
        processed_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_processed_at DEFAULT SYSUTCDATETIME()
    );
END;

-- M12 - Email Ingestion Module End
