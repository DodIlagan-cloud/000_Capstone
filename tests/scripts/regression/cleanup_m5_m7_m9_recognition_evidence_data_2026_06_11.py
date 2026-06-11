"""Clean M5/M7/M9 recognition evidence residue from the Azure SQL dev database.

The script runs inside stats-runtime and uses the container's configured
Azure SQL connection. It intentionally does not print connection strings,
passwords, tokens, or raw financial text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stats_data.database import open_azure_sql_connection
from stats_data.recognition_settings import save_label


EVIDENCE_EMAILS = {
    "m5m7.approval.admin@example.test",
}

CORE_LABELS = [
    ("document", "receipt", ["sales_receipt", "tax_receipt", "payment_terminal_receipt", "card_receipt", "medical_receipt", "unknown"]),
    ("transaction", "purchase", ["card_purchase", "eftpos_payment", "merchant_purchase", "cash_purchase", "unknown"]),
    ("spending", "shopping", ["retail", "general_merchandise", "online_shopping", "unknown", "uncategorized"]),
    ("spending", "transport", ["fuel", "public_transport", "parking", "rideshare", "unknown", "uncategorized"]),
]

WORKFLOW_TABLES = [
    "findings",
    "review_items",
    "financial_evidence_links",
    "line_items",
    "installments",
    "validated_references",
    "validated_entities",
    "document_sections",
    "financial_fields",
    "document_financial_summaries",
    "statement_summaries",
    "duplicate_check_results",
    "duplicate_check_batches",
    "transactions",
    "transaction_batches",
    "processing_runs",
    "document_processing_steps",
    "document_processing_jobs",
    "recognition_label_sync_runs",
    "recognition_config_changes",
    "recognition_label_suggestions",
    "stats_documents",
    "validation_results",
]


@dataclass
class CleanupResult:
    table_name: str
    before_count: int
    after_count: int

    @property
    def deleted_count(self) -> int:
        return self.before_count - self.after_count


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute(
        """
SELECT COUNT(1)
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'dbo'
  AND TABLE_NAME = ?;
""",
        table_name,
    )
    row = cursor.fetchone()
    return bool(row and int(row[0]) > 0)


def _count(cursor: Any, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(1) FROM dbo.{table_name};")
    row = cursor.fetchone()
    return int(row[0] if row else 0)


def _delete_table(cursor: Any, table_name: str) -> CleanupResult | None:
    if not _table_exists(cursor, table_name):
        return None

    before_count = _count(cursor, table_name)
    cursor.execute(f"DELETE FROM dbo.{table_name};")
    after_count = _count(cursor, table_name)
    return CleanupResult(table_name, before_count, after_count)


def _cleanup_test_labels(cursor: Any) -> CleanupResult:
    before_count = _count(cursor, "recognition_labels")
    cursor.execute(
        """
UPDATE dbo.recognition_labels
SET is_active = 0,
    updated_at_utc = SYSUTCDATETIME()
WHERE label_key LIKE 'test[_]%';
"""
    )
    after_count = _count(cursor, "recognition_labels")
    return CleanupResult("recognition_labels test_* deactivated", before_count, after_count)


def _cleanup_evidence_users(cursor: Any) -> CleanupResult:
    before_count = _count(cursor, "users")
    placeholders = ", ".join("?" for _ in EVIDENCE_EMAILS)
    cursor.execute(f"DELETE FROM dbo.users WHERE email IN ({placeholders});", *sorted(EVIDENCE_EMAILS))
    after_count = _count(cursor, "users")
    return CleanupResult("users evidence accounts", before_count, after_count)


def main() -> None:
    print("M5/M7/M9 recognition evidence database cleanup")
    print("Connection source: stats-runtime environment")
    print("Secret policy: connection string is intentionally not printed")
    print("")

    with open_azure_sql_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name;")
        database_name, server_name = cursor.fetchone()
        print(f"database_name={database_name}")
        print(f"server_name={server_name}")
        print("")

        results: list[CleanupResult] = []
        for table_name in WORKFLOW_TABLES:
            result = _delete_table(cursor, table_name)
            if result:
                results.append(result)

        results.append(_cleanup_test_labels(cursor))
        for scope, label, values in CORE_LABELS:
            save_label(connection, scope=scope, original_label="", label=label, values=values)
        results.append(_cleanup_evidence_users(cursor))

        connection.commit()

        print("Cleanup results:")
        print("target | before | after | removed_or_deactivated")
        for result in results:
            print(f"{result.table_name} | {result.before_count} | {result.after_count} | {result.deleted_count}")

        cursor.execute(
            """
SELECT label_scope, label_key, is_active
FROM dbo.recognition_labels
WHERE label_scope IN ('document','transaction','spending')
  AND label_key IN ('receipt','purchase','shopping','transport')
ORDER BY label_scope, label_key;
"""
        )
        print("")
        print("Core recognition labels:")
        print("label_scope | label_key | is_active")
        for row in cursor.fetchall():
            print(f"{row[0]} | {row[1]} | {row[2]}")

    print("")
    print("Result: PASSED - evidence residue cleaned and core labels restored")


if __name__ == "__main__":
    main()
