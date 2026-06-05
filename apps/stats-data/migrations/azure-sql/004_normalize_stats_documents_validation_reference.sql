-- M9 - Stats Data and Persistence Start
-- Normalizes the document validation-result reference after earlier cloud-dev legacy naming.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '004_normalize_stats_documents_validation_reference')
BEGIN
    DECLARE @legacy_validation_result_id_column sysname = N'm' + N'8_validation_result_id';

    IF OBJECT_ID(N'dbo.stats_documents', N'U') IS NOT NULL
        AND COL_LENGTH(N'dbo.stats_documents', N'validation_result_id') IS NULL
        AND COL_LENGTH(N'dbo.stats_documents', @legacy_validation_result_id_column) IS NOT NULL
    BEGIN
        DECLARE @rename_document_validation_result_id_sql nvarchar(max) =
            N'EXEC sp_rename N''dbo.stats_documents.' + @legacy_validation_result_id_column + N''', N''validation_result_id'', N''COLUMN'';';
        EXEC sp_executesql @rename_document_validation_result_id_sql;
    END;

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('004_normalize_stats_documents_validation_reference');
END;
GO

-- M9 End
