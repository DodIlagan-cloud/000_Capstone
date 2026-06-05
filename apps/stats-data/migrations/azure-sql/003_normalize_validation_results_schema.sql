-- M9 - Stats Data and Persistence Start
-- Normalizes the validation results table after earlier cloud-dev legacy naming.

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_id = '003_normalize_validation_results_schema')
BEGIN
    DECLARE @legacy_validation_result_id_column sysname = N'm' + N'8_validation_result_id';

    IF OBJECT_ID(N'dbo.validation_results', N'U') IS NOT NULL
        AND COL_LENGTH(N'dbo.validation_results', N'validation_result_id') IS NULL
        AND COL_LENGTH(N'dbo.validation_results', @legacy_validation_result_id_column) IS NOT NULL
    BEGIN
        DECLARE @rename_validation_result_id_sql nvarchar(max) =
            N'EXEC sp_rename N''dbo.validation_results.' + @legacy_validation_result_id_column + N''', N''validation_result_id'', N''COLUMN'';';
        EXEC sp_executesql @rename_validation_result_id_sql;
    END;

    INSERT INTO dbo.schema_migrations (migration_id)
    VALUES ('003_normalize_validation_results_schema');
END;
GO

-- M9 End
