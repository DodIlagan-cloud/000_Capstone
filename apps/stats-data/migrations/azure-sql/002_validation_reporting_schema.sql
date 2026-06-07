-- M9 - Stats Data and Persistence Start
-- Adds Azure SQL structures for the evolved validation handoff used by dashboard and reporting.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '002_validation_reporting_schema')
BEGIN
    DECLARE @legacy_validation_results_table sysname = N'm' + N'8_validation_results';

    IF OBJECT_ID(N'dbo.validation_results', N'U') IS NULL
        AND OBJECT_ID(N'dbo.' + @legacy_validation_results_table, N'U') IS NOT NULL
    BEGIN
        EXEC sp_rename N'dbo.m8_validation_results', N'validation_results';
    END;

    IF COL_LENGTH('dbo.validation_results', 'section_candidate_count') IS NULL
        ALTER TABLE dbo.validation_results ADD section_candidate_count int NOT NULL CONSTRAINT df_validation_results_section_count DEFAULT 0;

    IF COL_LENGTH('dbo.validation_results', 'entity_count') IS NULL
        ALTER TABLE dbo.validation_results ADD entity_count int NOT NULL CONSTRAINT df_validation_results_entity_count DEFAULT 0;

    IF COL_LENGTH('dbo.validation_results', 'reference_count') IS NULL
        ALTER TABLE dbo.validation_results ADD reference_count int NOT NULL CONSTRAINT df_validation_results_reference_count DEFAULT 0;

    IF COL_LENGTH('dbo.validation_results', 'line_item_count') IS NULL
        ALTER TABLE dbo.validation_results ADD line_item_count int NOT NULL CONSTRAINT df_validation_results_line_item_count DEFAULT 0;

    IF COL_LENGTH('dbo.validation_results', 'installment_count') IS NULL
        ALTER TABLE dbo.validation_results ADD installment_count int NOT NULL CONSTRAINT df_validation_results_installment_count DEFAULT 0;

    IF COL_LENGTH('dbo.validation_results', 'warning_installment_count') IS NULL
        ALTER TABLE dbo.validation_results ADD warning_installment_count int NOT NULL CONSTRAINT df_validation_results_warning_installment_count DEFAULT 0;

    IF COL_LENGTH('dbo.validation_results', 'invalid_installment_count') IS NULL
        ALTER TABLE dbo.validation_results ADD invalid_installment_count int NOT NULL CONSTRAINT df_validation_results_invalid_installment_count DEFAULT 0;

    IF COL_LENGTH('dbo.transactions', 'reason_codes_json') IS NULL
        ALTER TABLE dbo.transactions ADD reason_codes_json nvarchar(max) NULL;

    IF COL_LENGTH('dbo.transactions', 'source_section_id') IS NULL
        ALTER TABLE dbo.transactions ADD source_section_id nvarchar(100) NULL;

    IF COL_LENGTH('dbo.transactions', 'source_section_label') IS NULL
        ALTER TABLE dbo.transactions ADD source_section_label nvarchar(150) NULL;

    IF COL_LENGTH('dbo.transactions', 'source_ocr_confidence') IS NULL
        ALTER TABLE dbo.transactions ADD source_ocr_confidence decimal(9,6) NULL;

    IF COL_LENGTH('dbo.transactions', 'source_extraction_confidence') IS NULL
        ALTER TABLE dbo.transactions ADD source_extraction_confidence decimal(9,6) NULL;

    IF COL_LENGTH('dbo.financial_fields', 'reason_codes_json') IS NULL
        ALTER TABLE dbo.financial_fields ADD reason_codes_json nvarchar(max) NULL;

    IF COL_LENGTH('dbo.financial_fields', 'source_section_id') IS NULL
        ALTER TABLE dbo.financial_fields ADD source_section_id nvarchar(100) NULL;

    IF COL_LENGTH('dbo.financial_fields', 'source_section_label') IS NULL
        ALTER TABLE dbo.financial_fields ADD source_section_label nvarchar(150) NULL;

    IF COL_LENGTH('dbo.financial_fields', 'source_ocr_confidence') IS NULL
        ALTER TABLE dbo.financial_fields ADD source_ocr_confidence decimal(9,6) NULL;

    IF COL_LENGTH('dbo.financial_fields', 'source_extraction_confidence') IS NULL
        ALTER TABLE dbo.financial_fields ADD source_extraction_confidence decimal(9,6) NULL;

    IF COL_LENGTH('dbo.line_items', 'source_line_item_id') IS NULL
        ALTER TABLE dbo.line_items ADD source_line_item_id nvarchar(100) NULL;

    IF COL_LENGTH('dbo.line_items', 'amount') IS NULL
        ALTER TABLE dbo.line_items ADD amount decimal(19,4) NULL;

    IF COL_LENGTH('dbo.line_items', 'currency') IS NULL
        ALTER TABLE dbo.line_items ADD currency nvarchar(3) NULL;

    IF COL_LENGTH('dbo.line_items', 'reason_codes_json') IS NULL
        ALTER TABLE dbo.line_items ADD reason_codes_json nvarchar(max) NULL;

    IF COL_LENGTH('dbo.line_items', 'source_section_id') IS NULL
        ALTER TABLE dbo.line_items ADD source_section_id nvarchar(100) NULL;

    IF COL_LENGTH('dbo.line_items', 'source_section_label') IS NULL
        ALTER TABLE dbo.line_items ADD source_section_label nvarchar(150) NULL;

    IF COL_LENGTH('dbo.line_items', 'source_ocr_confidence') IS NULL
        ALTER TABLE dbo.line_items ADD source_ocr_confidence decimal(9,6) NULL;

    IF COL_LENGTH('dbo.line_items', 'source_extraction_confidence') IS NULL
        ALTER TABLE dbo.line_items ADD source_extraction_confidence decimal(9,6) NULL;

    IF COL_LENGTH('dbo.review_items', 'record_id') IS NULL
        ALTER TABLE dbo.review_items ADD record_id nvarchar(100) NULL;

    IF COL_LENGTH('dbo.review_items', 'reason_codes_json') IS NULL
        ALTER TABLE dbo.review_items ADD reason_codes_json nvarchar(max) NULL;

    IF COL_LENGTH('dbo.review_items', 'source_section_id') IS NULL
        ALTER TABLE dbo.review_items ADD source_section_id nvarchar(100) NULL;

    IF COL_LENGTH('dbo.review_items', 'source_section_label') IS NULL
        ALTER TABLE dbo.review_items ADD source_section_label nvarchar(150) NULL;

    IF COL_LENGTH('dbo.review_items', 'source_ocr_confidence') IS NULL
        ALTER TABLE dbo.review_items ADD source_ocr_confidence decimal(9,6) NULL;

    IF COL_LENGTH('dbo.review_items', 'source_extraction_confidence') IS NULL
        ALTER TABLE dbo.review_items ADD source_extraction_confidence decimal(9,6) NULL;

    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'document_sections' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.document_sections (
            document_section_id nvarchar(36) NOT NULL CONSTRAINT pk_document_sections PRIMARY KEY,
            document_id nvarchar(36) NOT NULL,
            source_section_id nvarchar(100) NOT NULL,
            section_label nvarchar(150) NOT NULL,
            page_number int NULL,
            first_line_number int NOT NULL,
            last_line_number int NOT NULL,
            source_text_redacted nvarchar(max) NOT NULL,
            confidence decimal(9,6) NULL,
            reason_codes_json nvarchar(max) NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_document_sections_created_at DEFAULT SYSUTCDATETIME(),
            CONSTRAINT fk_document_sections_stats_documents
                FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
            CONSTRAINT ck_document_sections_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1)
        );

        CREATE INDEX ix_document_sections_document_label
            ON dbo.document_sections(document_id, section_label, page_number);
    END;

    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'validated_entities' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.validated_entities (
            validated_entity_id nvarchar(36) NOT NULL CONSTRAINT pk_validated_entities PRIMARY KEY,
            document_id nvarchar(36) NOT NULL,
            source_entity_id nvarchar(100) NOT NULL,
            entity_type nvarchar(100) NOT NULL,
            value nvarchar(500) NOT NULL,
            confidence decimal(9,6) NULL,
            quality_status nvarchar(50) NOT NULL,
            reason_codes_json nvarchar(max) NULL,
            source_page_number int NULL,
            source_line_number int NULL,
            source_section_id nvarchar(100) NULL,
            source_section_label nvarchar(150) NULL,
            source_text_redacted nvarchar(1000) NULL,
            source_ocr_confidence decimal(9,6) NULL,
            source_extraction_confidence decimal(9,6) NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_validated_entities_created_at DEFAULT SYSUTCDATETIME(),
            CONSTRAINT fk_validated_entities_stats_documents
                FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
            CONSTRAINT ck_validated_entities_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1)
        );

        CREATE INDEX ix_validated_entities_document_type
            ON dbo.validated_entities(document_id, entity_type, quality_status);
    END;

    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'validated_references' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.validated_references (
            validated_reference_id nvarchar(36) NOT NULL CONSTRAINT pk_validated_references PRIMARY KEY,
            document_id nvarchar(36) NOT NULL,
            source_reference_id nvarchar(100) NOT NULL,
            reference_type nvarchar(100) NOT NULL,
            value nvarchar(500) NOT NULL,
            masked bit NOT NULL CONSTRAINT df_validated_references_masked DEFAULT 0,
            confidence decimal(9,6) NULL,
            quality_status nvarchar(50) NOT NULL,
            reason_codes_json nvarchar(max) NULL,
            source_page_number int NULL,
            source_line_number int NULL,
            source_section_id nvarchar(100) NULL,
            source_section_label nvarchar(150) NULL,
            source_text_redacted nvarchar(1000) NULL,
            source_ocr_confidence decimal(9,6) NULL,
            source_extraction_confidence decimal(9,6) NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_validated_references_created_at DEFAULT SYSUTCDATETIME(),
            CONSTRAINT fk_validated_references_stats_documents
                FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
            CONSTRAINT ck_validated_references_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1)
        );

        CREATE INDEX ix_validated_references_document_type
            ON dbo.validated_references(document_id, reference_type, quality_status);
    END;

    IF NOT EXISTS (
        SELECT 1 FROM sys.tables WHERE name = 'installments' AND schema_id = SCHEMA_ID('dbo')
    )
    BEGIN
        CREATE TABLE dbo.installments (
            installment_id nvarchar(36) NOT NULL CONSTRAINT pk_installments PRIMARY KEY,
            document_id nvarchar(36) NOT NULL,
            source_installment_id nvarchar(100) NOT NULL,
            purchase_date date NULL,
            posted_date date NULL,
            description nvarchar(500) NOT NULL,
            principal_amount decimal(19,4) NULL,
            current_billing_amount decimal(19,4) NULL,
            remaining_balance decimal(19,4) NULL,
            currency nvarchar(3) NOT NULL CONSTRAINT df_installments_currency DEFAULT 'PHP',
            term_text nvarchar(200) NULL,
            confidence decimal(9,6) NULL,
            quality_status nvarchar(50) NOT NULL,
            reason_codes_json nvarchar(max) NULL,
            source_page_number int NULL,
            source_line_number int NULL,
            source_section_id nvarchar(100) NULL,
            source_section_label nvarchar(150) NULL,
            source_text_redacted nvarchar(1000) NULL,
            source_ocr_confidence decimal(9,6) NULL,
            source_extraction_confidence decimal(9,6) NULL,
            created_at_utc datetime2(3) NOT NULL CONSTRAINT df_installments_created_at DEFAULT SYSUTCDATETIME(),
            updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_installments_updated_at DEFAULT SYSUTCDATETIME(),
            CONSTRAINT fk_installments_stats_documents
                FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
            CONSTRAINT ck_installments_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1)
        );

        CREATE INDEX ix_installments_document_status
            ON dbo.installments(document_id, quality_status, purchase_date);
    END;

    IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'ck_transactions_reason_codes_json')
        EXEC(N'ALTER TABLE dbo.transactions ADD CONSTRAINT ck_transactions_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1);');

    IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'ck_financial_fields_reason_codes_json')
        EXEC(N'ALTER TABLE dbo.financial_fields ADD CONSTRAINT ck_financial_fields_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1);');

    IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'ck_line_items_reason_codes_json')
        EXEC(N'ALTER TABLE dbo.line_items ADD CONSTRAINT ck_line_items_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1);');

    IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'ck_review_items_reason_codes_json')
        EXEC(N'ALTER TABLE dbo.review_items ADD CONSTRAINT ck_review_items_reason_codes_json CHECK (reason_codes_json IS NULL OR ISJSON(reason_codes_json) = 1);');

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('002_validation_reporting_schema');
END;
GO

-- M9 End
