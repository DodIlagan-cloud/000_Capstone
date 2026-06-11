-- Active recognition settings for database-backed labels and rules.

IF OBJECT_ID('dbo.recognition_labels', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.recognition_labels (
        label_id nvarchar(120) NOT NULL CONSTRAINT pk_recognition_labels PRIMARY KEY,
        label_scope nvarchar(40) NOT NULL,
        label_key nvarchar(160) NOT NULL,
        display_label nvarchar(200) NOT NULL,
        values_json nvarchar(max) NOT NULL,
        is_system bit NOT NULL CONSTRAINT df_recognition_labels_is_system DEFAULT 0,
        is_active bit NOT NULL CONSTRAINT df_recognition_labels_is_active DEFAULT 1,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_recognition_labels_created DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_recognition_labels_updated DEFAULT SYSUTCDATETIME(),
        CONSTRAINT ck_recognition_labels_values_json CHECK (ISJSON(values_json) = 1)
    );
END;

IF OBJECT_ID('dbo.recognition_rules', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.recognition_rules (
        rule_id nvarchar(120) NOT NULL CONSTRAINT pk_recognition_rules PRIMARY KEY,
        rule_scope nvarchar(40) NOT NULL,
        target_label nvarchar(160) NOT NULL,
        target_subtype nvarchar(160) NOT NULL,
        reason_code nvarchar(160) NOT NULL,
        required_any_json nvarchar(max) NOT NULL,
        signals_json nvarchar(max) NOT NULL,
        minimum_score decimal(9,6) NOT NULL CONSTRAINT df_recognition_rules_minimum_score DEFAULT 0.35,
        is_system bit NOT NULL CONSTRAINT df_recognition_rules_is_system DEFAULT 0,
        is_active bit NOT NULL CONSTRAINT df_recognition_rules_is_active DEFAULT 1,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_recognition_rules_created DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_recognition_rules_updated DEFAULT SYSUTCDATETIME(),
        CONSTRAINT ck_recognition_rules_required_any_json CHECK (ISJSON(required_any_json) = 1),
        CONSTRAINT ck_recognition_rules_signals_json CHECK (ISJSON(signals_json) = 1)
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'ux_recognition_labels_scope_key'
      AND object_id = OBJECT_ID('dbo.recognition_labels')
)
    CREATE UNIQUE INDEX ux_recognition_labels_scope_key
        ON dbo.recognition_labels(label_scope, label_key);

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'ux_recognition_rules_scope_reason'
      AND object_id = OBJECT_ID('dbo.recognition_rules')
)
    CREATE UNIQUE INDEX ux_recognition_rules_scope_reason
        ON dbo.recognition_rules(rule_scope, reason_code);

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'ix_recognition_rules_scope_target'
      AND object_id = OBJECT_ID('dbo.recognition_rules')
)
    CREATE INDEX ix_recognition_rules_scope_target
        ON dbo.recognition_rules(rule_scope, target_label, target_subtype, is_active);
