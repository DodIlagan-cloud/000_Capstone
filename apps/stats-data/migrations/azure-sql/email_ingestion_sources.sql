-- M12 - Email Ingestion Module Start
-- Stores email ingestion source profile metadata. Raw mailbox/PDF passwords remain in secrets.

IF OBJECT_ID('dbo.email_ingestion_sources', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.email_ingestion_sources (
        source_id nvarchar(120) NOT NULL CONSTRAINT pk_email_ingestion_sources PRIMARY KEY,
        display_name nvarchar(200) NOT NULL,
        provider nvarchar(40) NOT NULL CONSTRAINT df_email_sources_provider DEFAULT 'custom_imap',
        email_address nvarchar(320) NOT NULL,
        enabled bit NOT NULL CONSTRAINT df_email_sources_enabled DEFAULT 1,
        folder nvarchar(240) NOT NULL CONSTRAINT df_email_sources_folder DEFAULT 'Inbox',
        secret_ref nvarchar(240) NULL,
        connection_status nvarchar(40) NOT NULL CONSTRAINT df_email_sources_connection_status DEFAULT 'not_tested',
        connection_settings_json nvarchar(max) NOT NULL CONSTRAINT df_email_sources_connection_settings DEFAULT '{}',
        sender_allowlist_json nvarchar(max) NOT NULL CONSTRAINT df_email_sources_sender_allowlist DEFAULT '[]',
        subject_contains_json nvarchar(max) NOT NULL CONSTRAINT df_email_sources_subject_contains DEFAULT '[]',
        attachment_policy_json nvarchar(max) NOT NULL CONSTRAINT df_email_sources_attachment_policy DEFAULT '{}',
        pdf_password_policy_json nvarchar(max) NOT NULL CONSTRAINT df_email_sources_pdf_password_policy DEFAULT '{}',
        post_process_policy_json nvarchar(max) NOT NULL CONSTRAINT df_email_sources_post_process_policy DEFAULT '{}',
        last_tested_at_utc datetime2(3) NULL,
        last_run_id nvarchar(80) NULL,
        last_run_status nvarchar(40) NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_sources_created_at DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_sources_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF COL_LENGTH('dbo.email_ingestion_sources', 'connection_settings_json') IS NULL
BEGIN
    ALTER TABLE dbo.email_ingestion_sources
        ADD connection_settings_json nvarchar(max) NOT NULL
            CONSTRAINT df_email_sources_connection_settings DEFAULT '{}';
END;

IF COL_LENGTH('dbo.email_ingestion_sources', 'sender_allowlist_json') IS NULL
BEGIN
    ALTER TABLE dbo.email_ingestion_sources
        ADD sender_allowlist_json nvarchar(max) NOT NULL
            CONSTRAINT df_email_sources_sender_allowlist DEFAULT '[]';
END;

IF COL_LENGTH('dbo.email_ingestion_sources', 'subject_contains_json') IS NULL
BEGIN
    ALTER TABLE dbo.email_ingestion_sources
        ADD subject_contains_json nvarchar(max) NOT NULL
            CONSTRAINT df_email_sources_subject_contains DEFAULT '[]';
END;

IF COL_LENGTH('dbo.email_ingestion_sources', 'attachment_policy_json') IS NULL
BEGIN
    ALTER TABLE dbo.email_ingestion_sources
        ADD attachment_policy_json nvarchar(max) NOT NULL
            CONSTRAINT df_email_sources_attachment_policy DEFAULT '{}';
END;

IF COL_LENGTH('dbo.email_ingestion_sources', 'pdf_password_policy_json') IS NULL
BEGIN
    ALTER TABLE dbo.email_ingestion_sources
        ADD pdf_password_policy_json nvarchar(max) NOT NULL
            CONSTRAINT df_email_sources_pdf_password_policy DEFAULT '{}';
END;

IF COL_LENGTH('dbo.email_ingestion_sources', 'post_process_policy_json') IS NULL
BEGIN
    ALTER TABLE dbo.email_ingestion_sources
        ADD post_process_policy_json nvarchar(max) NOT NULL
            CONSTRAINT df_email_sources_post_process_policy DEFAULT '{}';
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_email_sources_enabled_provider' AND object_id = OBJECT_ID('dbo.email_ingestion_sources'))
    CREATE INDEX ix_email_sources_enabled_provider
        ON dbo.email_ingestion_sources(enabled, provider);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_email_sources_email_address' AND object_id = OBJECT_ID('dbo.email_ingestion_sources'))
    CREATE INDEX ix_email_sources_email_address
        ON dbo.email_ingestion_sources(email_address);

IF OBJECT_ID('dbo.email_ingestion_secrets', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.email_ingestion_secrets (
        secret_ref nvarchar(240) NOT NULL CONSTRAINT pk_email_ingestion_secrets PRIMARY KEY,
        encrypted_value varbinary(max) NOT NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_secrets_created_at DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_secrets_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

-- M12 - Email Ingestion Module End
