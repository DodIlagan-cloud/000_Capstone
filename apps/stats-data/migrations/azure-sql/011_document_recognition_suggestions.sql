-- M9 Document Suggestion Approval Start - 2026-06-11
-- Adds document-label suggestion persistence and saved-document linkage.

IF COL_LENGTH('dbo.stats_documents', 'recognition_suggestion_id') IS NULL
    ALTER TABLE dbo.stats_documents ADD recognition_suggestion_id nvarchar(120) NULL;

IF COL_LENGTH('dbo.stats_documents', 'recognition_suggestion_status') IS NULL
    ALTER TABLE dbo.stats_documents ADD recognition_suggestion_status nvarchar(40) NOT NULL CONSTRAINT df_stats_documents_recognition_suggestion_status DEFAULT 'none';

IF COL_LENGTH('dbo.stats_documents', 'suggested_document_type') IS NULL
    ALTER TABLE dbo.stats_documents ADD suggested_document_type nvarchar(80) NULL;

IF COL_LENGTH('dbo.stats_documents', 'suggested_document_subtype') IS NULL
    ALTER TABLE dbo.stats_documents ADD suggested_document_subtype nvarchar(100) NULL;

IF COL_LENGTH('dbo.stats_documents', 'document_suggestion_confidence') IS NULL
    ALTER TABLE dbo.stats_documents ADD document_suggestion_confidence decimal(9,6) NULL;

IF COL_LENGTH('dbo.stats_documents', 'document_suggestion_reason_codes_json') IS NULL
    ALTER TABLE dbo.stats_documents ADD document_suggestion_reason_codes_json nvarchar(max) NULL;

IF COL_LENGTH('dbo.stats_documents', 'document_suggestion_source') IS NULL
    ALTER TABLE dbo.stats_documents ADD document_suggestion_source nvarchar(80) NULL;

IF COL_LENGTH('dbo.stats_documents', 'document_suggestion_evidence_ref') IS NULL
    ALTER TABLE dbo.stats_documents ADD document_suggestion_evidence_ref nvarchar(300) NULL;

IF OBJECT_ID('dbo.recognition_label_suggestions', 'U') IS NOT NULL
BEGIN
    IF COL_LENGTH('dbo.recognition_label_suggestions', 'current_document_type') IS NULL
        ALTER TABLE dbo.recognition_label_suggestions ADD current_document_type nvarchar(80) NULL;

    IF COL_LENGTH('dbo.recognition_label_suggestions', 'current_document_subtype') IS NULL
        ALTER TABLE dbo.recognition_label_suggestions ADD current_document_subtype nvarchar(100) NULL;

    IF COL_LENGTH('dbo.recognition_label_suggestions', 'suggested_document_type') IS NULL
        ALTER TABLE dbo.recognition_label_suggestions ADD suggested_document_type nvarchar(80) NULL;

    IF COL_LENGTH('dbo.recognition_label_suggestions', 'suggested_document_subtype') IS NULL
        ALTER TABLE dbo.recognition_label_suggestions ADD suggested_document_subtype nvarchar(100) NULL;
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'ix_stats_documents_recognition_suggestions'
      AND object_id = OBJECT_ID('dbo.stats_documents')
)
    CREATE INDEX ix_stats_documents_recognition_suggestions
        ON dbo.stats_documents(recognition_suggestion_status, recognition_suggestion_id);

-- M9 Document Suggestion Approval End - 2026-06-11
