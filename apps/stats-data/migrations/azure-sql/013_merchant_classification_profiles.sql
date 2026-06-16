-- M9 - Learned Merchant Classification Profiles Start
-- Stores human-confirmed merchant classifications for exact reuse before AI.

IF OBJECT_ID('dbo.merchant_classification_profiles', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.merchant_classification_profiles (
        merchant_profile_id nvarchar(36) NOT NULL CONSTRAINT pk_merchant_classification_profiles PRIMARY KEY,
        merchant_key nvarchar(240) NOT NULL,
        merchant_display_name nvarchar(200) NOT NULL,
        owner_user_id nvarchar(120) NULL,
        transaction_type nvarchar(80) NOT NULL,
        transaction_subtype nvarchar(100) NOT NULL,
        spending_category nvarchar(100) NOT NULL,
        spending_subcategory nvarchar(100) NOT NULL,
        classification_source nvarchar(80) NOT NULL CONSTRAINT df_merchant_profiles_classification_source DEFAULT 'human_confirmed_transaction',
        confirmation_count int NOT NULL CONSTRAINT df_merchant_profiles_confirmation_count DEFAULT 0,
        conflict_count int NOT NULL CONSTRAINT df_merchant_profiles_conflict_count DEFAULT 0,
        profile_status nvarchar(40) NOT NULL CONSTRAINT df_merchant_profiles_status DEFAULT 'active',
        first_confirmed_transaction_id nvarchar(36) NULL,
        last_confirmed_transaction_id nvarchar(36) NULL,
        last_confirmed_by_user_id nvarchar(120) NULL,
        last_confirmed_at_utc datetime2(3) NULL,
        created_at_utc datetime2(3) NOT NULL CONSTRAINT df_merchant_profiles_created_at DEFAULT SYSUTCDATETIME(),
        updated_at_utc datetime2(3) NOT NULL CONSTRAINT df_merchant_profiles_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_merchant_profiles_key' AND object_id = OBJECT_ID('dbo.merchant_classification_profiles'))
    CREATE UNIQUE INDEX ux_merchant_profiles_key
        ON dbo.merchant_classification_profiles(merchant_key);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_merchant_profiles_status_key' AND object_id = OBJECT_ID('dbo.merchant_classification_profiles'))
    CREATE INDEX ix_merchant_profiles_status_key
        ON dbo.merchant_classification_profiles(profile_status, merchant_key);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_merchant_profiles_last_confirmed' AND object_id = OBJECT_ID('dbo.merchant_classification_profiles'))
    CREATE INDEX ix_merchant_profiles_last_confirmed
        ON dbo.merchant_classification_profiles(last_confirmed_at_utc);

-- M9 - Learned Merchant Classification Profiles End
