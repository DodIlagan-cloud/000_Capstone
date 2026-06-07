-- M9 - Stats Data and Persistence Start
-- Azure SQL initial schema for Stats-owned product data.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = 'schema_migrations' AND schema_id = SCHEMA_ID('dbo')
)
BEGIN
    CREATE TABLE dbo.schema_migrations (
        migration_id nvarchar(100) NOT NULL CONSTRAINT pk_schema_migrations PRIMARY KEY,
        applied_at_utc datetime2(3) NOT NULL CONSTRAINT df_schema_migrations_applied_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '001_initial_stats_data_schema')
BEGIN
    CREATE TABLE dbo.validation_results (
        validation_result_id nvarchar(36) NOT NULL CONSTRAINT pk_validation_results PRIMARY KEY,
        validation_id nvarchar(100) NULL,
        extraction_id nvarchar(100) NULL,
        parse_id nvarchar(100) NULL,
        ingestion_id nvarchar(100) NULL,
        uploaded_by_user_id nvarchar(36) NULL,
        document_type nvarchar(80) NULL,
        status nvarchar(50) NOT NULL,
        document_review_status nvarchar(50) NULL,
        recommended_action nvarchar(100) NULL,
        normalized_record_count int NOT NULL CONSTRAINT df_validation_results_normalized_count DEFAULT 0,
        valid_record_count int NOT NULL CONSTRAINT df_validation_results_valid_count DEFAULT 0,
        warning_record_count int NOT NULL CONSTRAINT df_validation_results_warning_count DEFAULT 0,
        invalid_record_count int NOT NULL CONSTRAINT df_validation_results_invalid_count DEFAULT 0,
        duplicate_record_count int NOT NULL CONSTRAINT df_validation_results_duplicate_count DEFAULT 0,
        review_item_count int NOT NULL CONSTRAINT df_validation_results_review_count DEFAULT 0,
        debit_total decimal(19,4) NULL,
        credit_total decimal(19,4) NULL,
        net_total decimal(19,4) NULL,
        reconciliation_delta decimal(19,4) NULL,
        payload_json nvarchar(max) NOT NULL,
        promotion_status nvarchar(50) NOT NULL CONSTRAINT df_validation_results_promotion_status DEFAULT 'pending',
        promotion_error nvarchar(2000) NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_validation_results_created_at DEFAULT SYSUTCDATETIME(),
        promoted_at_utc datetime2(3) NULL,
        CONSTRAINT ck_validation_results_payload_json CHECK (ISJSON(payload_json) = 1)
    );

    CREATE UNIQUE INDEX ux_validation_results_validation_id
        ON dbo.validation_results(validation_id)
        WHERE validation_id IS NOT NULL;

    CREATE TABLE dbo.stats_documents (
        document_id nvarchar(36) NOT NULL CONSTRAINT pk_stats_documents PRIMARY KEY,
        ingestion_id nvarchar(100) NULL,
        uploaded_by_user_id nvarchar(36) NULL,
        validation_result_id nvarchar(36) NULL,
        original_filename nvarchar(255) NOT NULL,
        normalized_filename nvarchar(255) NOT NULL,
        source_type nvarchar(50) NOT NULL,
        source_id nvarchar(100) NULL,
        sha256 nvarchar(64) NULL,
        document_fingerprint nvarchar(64) NULL,
        detected_mime_type nvarchar(150) NULL,
        size_bytes bigint NULL,
        storage_reference nvarchar(1024) NOT NULL,
        document_type nvarchar(80) NULL,
        source_institution nvarchar(150) NULL,
        status nvarchar(50) NOT NULL,
        ocr_quality_status nvarchar(50) NULL,
        redaction_applied bit NOT NULL CONSTRAINT df_stats_documents_redaction_applied DEFAULT 0,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_stats_documents_created_at DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_stats_documents_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_stats_documents_validation_results
            FOREIGN KEY (validation_result_id) REFERENCES dbo.validation_results(validation_result_id)
    );

    CREATE INDEX ix_stats_documents_user_status
        ON dbo.stats_documents(uploaded_by_user_id, status, created_at_utc);

    CREATE INDEX ix_stats_documents_document_type
        ON dbo.stats_documents(document_type, created_at_utc);

    CREATE TABLE dbo.processing_runs (
        processing_run_id nvarchar(36) NOT NULL CONSTRAINT pk_processing_runs PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        parse_id nvarchar(100) NULL,
        extraction_id nvarchar(100) NULL,
        validation_id nvarchar(100) NULL,
        module_name nvarchar(80) NOT NULL,
        module_version nvarchar(50) NULL,
        status nvarchar(50) NOT NULL,
        started_at_utc datetime2(3) NOT NULL,
        completed_at_utc datetime2(3) NULL,
        summary_json nvarchar(max) NULL,
        finding_counts_json nvarchar(max) NULL,
        CONSTRAINT fk_processing_runs_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
        CONSTRAINT ck_processing_runs_summary_json CHECK (summary_json IS NULL OR ISJSON(summary_json) = 1),
        CONSTRAINT ck_processing_runs_finding_counts_json CHECK (finding_counts_json IS NULL OR ISJSON(finding_counts_json) = 1)
    );

    CREATE INDEX ix_processing_runs_document_module
        ON dbo.processing_runs(document_id, module_name, started_at_utc);

    CREATE TABLE dbo.transaction_batches (
        transaction_batch_id nvarchar(36) NOT NULL CONSTRAINT pk_transaction_batches PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        validation_id nvarchar(100) NULL,
        saved_by_user_id nvarchar(36) NULL,
        status nvarchar(50) NOT NULL,
        input_record_count int NOT NULL CONSTRAINT df_transaction_batches_input_count DEFAULT 0,
        saved_record_count int NOT NULL CONSTRAINT df_transaction_batches_saved_count DEFAULT 0,
        duplicate_record_count int NOT NULL CONSTRAINT df_transaction_batches_duplicate_count DEFAULT 0,
        warning_record_count int NOT NULL CONSTRAINT df_transaction_batches_warning_count DEFAULT 0,
        invalid_record_count int NOT NULL CONSTRAINT df_transaction_batches_invalid_count DEFAULT 0,
        debit_total decimal(19,4) NULL,
        credit_total decimal(19,4) NULL,
        net_total decimal(19,4) NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_transaction_batches_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_transaction_batches_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id)
    );

    CREATE INDEX ix_transaction_batches_user_created
        ON dbo.transaction_batches(saved_by_user_id, created_at_utc);

    CREATE TABLE dbo.transactions (
        transaction_id nvarchar(36) NOT NULL CONSTRAINT pk_transactions PRIMARY KEY,
        transaction_batch_id nvarchar(36) NOT NULL,
        document_id nvarchar(36) NOT NULL,
        source_candidate_id nvarchar(100) NULL,
        transaction_date date NOT NULL,
        posted_date date NULL,
        description nvarchar(500) NOT NULL,
        normalized_description nvarchar(500) NOT NULL,
        amount decimal(19,4) NOT NULL,
        currency nvarchar(3) NOT NULL CONSTRAINT df_transactions_currency DEFAULT 'PHP',
        direction nvarchar(20) NOT NULL,
        signed_amount decimal(19,4) NOT NULL,
        source_institution nvarchar(150) NULL,
        merchant_or_counterparty nvarchar(200) NULL,
        category nvarchar(100) NULL,
        reference nvarchar(150) NULL,
        payment_method nvarchar(80) NULL,
        masked_account_or_card nvarchar(80) NULL,
        confidence decimal(9,6) NULL,
        quality_status nvarchar(50) NOT NULL,
        review_required bit NOT NULL CONSTRAINT df_transactions_review_required DEFAULT 0,
        duplicate_of_transaction_id nvarchar(36) NULL,
        duplicate_key nvarchar(450) NOT NULL,
        source_page_number int NULL,
        source_line_number int NULL,
        source_text_redacted nvarchar(1000) NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_transactions_created_at DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_transactions_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_transactions_transaction_batches
            FOREIGN KEY (transaction_batch_id) REFERENCES dbo.transaction_batches(transaction_batch_id),
        CONSTRAINT fk_transactions_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
        CONSTRAINT fk_transactions_duplicate_of
            FOREIGN KEY (duplicate_of_transaction_id) REFERENCES dbo.transactions(transaction_id)
    );

    CREATE INDEX ix_transactions_document_date
        ON dbo.transactions(document_id, transaction_date);

    CREATE INDEX ix_transactions_reporting
        ON dbo.transactions(transaction_date, direction, currency, category, quality_status);

    CREATE UNIQUE INDEX ux_transactions_duplicate_key
        ON dbo.transactions(duplicate_key)
        WHERE duplicate_of_transaction_id IS NULL;

    CREATE TABLE dbo.financial_fields (
        financial_field_id nvarchar(36) NOT NULL CONSTRAINT pk_financial_fields PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        transaction_batch_id nvarchar(36) NULL,
        field_name nvarchar(120) NOT NULL,
        field_label nvarchar(200) NULL,
        value_type nvarchar(50) NOT NULL,
        value nvarchar(500) NOT NULL,
        currency nvarchar(3) NULL,
        confidence decimal(9,6) NULL,
        quality_status nvarchar(50) NOT NULL,
        source_page_number int NULL,
        source_line_number int NULL,
        source_text_redacted nvarchar(1000) NULL,
        CONSTRAINT fk_financial_fields_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
        CONSTRAINT fk_financial_fields_transaction_batches
            FOREIGN KEY (transaction_batch_id) REFERENCES dbo.transaction_batches(transaction_batch_id)
    );

    CREATE TABLE dbo.statement_summaries (
        statement_summary_id nvarchar(36) NOT NULL CONSTRAINT pk_statement_summaries PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        statement_date date NULL,
        period_start_date date NULL,
        period_end_date date NULL,
        payment_due_date date NULL,
        minimum_amount_due decimal(19,4) NULL,
        total_amount_due decimal(19,4) NULL,
        previous_balance decimal(19,4) NULL,
        payments_total decimal(19,4) NULL,
        purchases_total decimal(19,4) NULL,
        fees_total decimal(19,4) NULL,
        interest_total decimal(19,4) NULL,
        installment_balance decimal(19,4) NULL,
        outstanding_balance decimal(19,4) NULL,
        credit_limit decimal(19,4) NULL,
        available_credit decimal(19,4) NULL,
        currency nvarchar(3) NOT NULL CONSTRAINT df_statement_summaries_currency DEFAULT 'PHP',
        confidence decimal(9,6) NULL,
        quality_status nvarchar(50) NOT NULL,
        CONSTRAINT fk_statement_summaries_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id)
    );

    CREATE INDEX ix_statement_summaries_due_date
        ON dbo.statement_summaries(payment_due_date, quality_status);

    CREATE TABLE dbo.document_financial_summaries (
        document_financial_summary_id nvarchar(36) NOT NULL CONSTRAINT pk_document_financial_summaries PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        invoice_number nvarchar(100) NULL,
        issue_date date NULL,
        subtotal_amount decimal(19,4) NULL,
        tax_amount decimal(19,4) NULL,
        total_amount decimal(19,4) NULL,
        paid_amount decimal(19,4) NULL,
        owing_amount decimal(19,4) NULL,
        currency nvarchar(3) NOT NULL CONSTRAINT df_document_financial_summaries_currency DEFAULT 'PHP',
        payment_status nvarchar(50) NULL,
        confidence decimal(9,6) NULL,
        quality_status nvarchar(50) NOT NULL,
        CONSTRAINT fk_document_financial_summaries_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id)
    );

    CREATE INDEX ix_document_financial_summaries_payment_status
        ON dbo.document_financial_summaries(payment_status, issue_date);

    CREATE TABLE dbo.line_items (
        line_item_id nvarchar(36) NOT NULL CONSTRAINT pk_line_items PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        description nvarchar(500) NOT NULL,
        quantity decimal(19,4) NULL,
        unit_amount decimal(19,4) NULL,
        line_amount decimal(19,4) NULL,
        tax_amount decimal(19,4) NULL,
        category nvarchar(100) NULL,
        confidence decimal(9,6) NULL,
        quality_status nvarchar(50) NOT NULL,
        source_page_number int NULL,
        source_line_number int NULL,
        source_text_redacted nvarchar(1000) NULL,
        CONSTRAINT fk_line_items_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id)
    );

    CREATE TABLE dbo.financial_evidence_links (
        financial_evidence_link_id nvarchar(36) NOT NULL CONSTRAINT pk_financial_evidence_links PRIMARY KEY,
        source_document_id nvarchar(36) NULL,
        target_document_id nvarchar(36) NULL,
        source_transaction_id nvarchar(36) NULL,
        target_transaction_id nvarchar(36) NULL,
        link_type nvarchar(80) NOT NULL,
        match_status nvarchar(50) NOT NULL,
        match_confidence decimal(9,6) NULL,
        match_reason nvarchar(500) NULL,
        reference nvarchar(150) NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_financial_evidence_links_created_at DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_financial_evidence_links_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_financial_evidence_links_source_document
            FOREIGN KEY (source_document_id) REFERENCES dbo.stats_documents(document_id),
        CONSTRAINT fk_financial_evidence_links_target_document
            FOREIGN KEY (target_document_id) REFERENCES dbo.stats_documents(document_id),
        CONSTRAINT fk_financial_evidence_links_source_transaction
            FOREIGN KEY (source_transaction_id) REFERENCES dbo.transactions(transaction_id),
        CONSTRAINT fk_financial_evidence_links_target_transaction
            FOREIGN KEY (target_transaction_id) REFERENCES dbo.transactions(transaction_id)
    );

    CREATE INDEX ix_financial_evidence_links_status
        ON dbo.financial_evidence_links(match_status, link_type);

    CREATE TABLE dbo.findings (
        finding_id nvarchar(36) NOT NULL CONSTRAINT pk_findings PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        transaction_id nvarchar(36) NULL,
        processing_run_id nvarchar(36) NULL,
        source_module nvarchar(50) NOT NULL,
        code nvarchar(100) NOT NULL,
        severity nvarchar(20) NOT NULL,
        message nvarchar(1000) NOT NULL,
        status nvarchar(50) NOT NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_findings_created_at DEFAULT SYSUTCDATETIME(),
        resolved_at_utc datetime2(3) NULL,
        resolved_by_user_id nvarchar(36) NULL,
        CONSTRAINT fk_findings_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
        CONSTRAINT fk_findings_transactions
            FOREIGN KEY (transaction_id) REFERENCES dbo.transactions(transaction_id),
        CONSTRAINT fk_findings_processing_runs
            FOREIGN KEY (processing_run_id) REFERENCES dbo.processing_runs(processing_run_id)
    );

    CREATE INDEX ix_findings_status_severity
        ON dbo.findings(status, severity, created_at_utc);

    CREATE TABLE dbo.review_items (
        review_item_id nvarchar(36) NOT NULL CONSTRAINT pk_review_items PRIMARY KEY,
        document_id nvarchar(36) NOT NULL,
        transaction_id nvarchar(36) NULL,
        source_review_id nvarchar(100) NULL,
        item_type nvarchar(80) NOT NULL,
        severity nvarchar(20) NOT NULL,
        title nvarchar(200) NOT NULL,
        message nvarchar(1000) NOT NULL,
        field_name nvarchar(120) NULL,
        recommended_action nvarchar(100) NULL,
        status nvarchar(50) NOT NULL,
        source_page_number int NULL,
        source_line_number int NULL,
        source_text_redacted nvarchar(1000) NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_review_items_created_at DEFAULT SYSUTCDATETIME(),
        resolved_at_utc datetime2(3) NULL,
        resolved_by_user_id nvarchar(36) NULL,
        CONSTRAINT fk_review_items_stats_documents
            FOREIGN KEY (document_id) REFERENCES dbo.stats_documents(document_id),
        CONSTRAINT fk_review_items_transactions
            FOREIGN KEY (transaction_id) REFERENCES dbo.transactions(transaction_id)
    );

    CREATE INDEX ix_review_items_status_severity
        ON dbo.review_items(status, severity, created_at_utc);

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('001_initial_stats_data_schema');
END;
GO

-- M9 End
