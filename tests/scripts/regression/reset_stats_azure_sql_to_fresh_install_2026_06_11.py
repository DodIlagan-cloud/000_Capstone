"""Reset the Stats Azure SQL database to a fresh-install data state.

This keeps schema and migration history, deletes application/user data, then
reseeds baseline recognition settings so the app behaves like a newly installed
Stats database before first-admin bootstrap.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from stats_data.database import open_azure_sql_connection
from stats_data.recognition_settings import seed_recognition_settings_if_empty


PRESERVED_TABLES = {"schema_migrations"}


@dataclass(frozen=True)
class TableInfo:
    schema: str
    name: str
    row_count: int

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}"


def _table_infos(cursor: Any) -> list[TableInfo]:
    cursor.execute(
        """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    SUM(CASE WHEN p.index_id IN (0, 1) THEN p.rows ELSE 0 END) AS row_count
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
LEFT JOIN sys.partitions AS p ON p.object_id = t.object_id
WHERE s.name = 'dbo'
GROUP BY s.name, t.name
ORDER BY t.name;
"""
    )
    return [TableInfo(str(row[0]), str(row[1]), int(row[2] or 0)) for row in cursor.fetchall()]


def _database_identity(cursor: Any) -> tuple[str, str]:
    cursor.execute("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name;")
    row = cursor.fetchone()
    return str(row[0]), str(row[1])


def _quoted(value: str) -> str:
    return "[" + value.replace("]", "]]") + "]"


def _foreign_keys(cursor: Any) -> list[tuple[str, str, str]]:
    cursor.execute(
        """
SELECT
    OBJECT_SCHEMA_NAME(parent_object_id) AS schema_name,
    OBJECT_NAME(parent_object_id) AS table_name,
    name AS foreign_key_name
FROM sys.foreign_keys
ORDER BY name;
"""
    )
    return [(str(row[0]), str(row[1]), str(row[2])) for row in cursor.fetchall()]


def _set_foreign_keys(cursor: Any, *, enabled: bool) -> None:
    for schema, table, foreign_key in _foreign_keys(cursor):
        if enabled:
            cursor.execute(
                f"ALTER TABLE {_quoted(schema)}.{_quoted(table)} WITH CHECK CHECK CONSTRAINT {_quoted(foreign_key)};"
            )
        else:
            cursor.execute(
                f"ALTER TABLE {_quoted(schema)}.{_quoted(table)} NOCHECK CONSTRAINT {_quoted(foreign_key)};"
            )


def _delete_tables(cursor: Any, tables: list[TableInfo]) -> dict[str, int]:
    deleted: dict[str, int] = {}
    _set_foreign_keys(cursor, enabled=False)
    for table in tables:
        if table.name in PRESERVED_TABLES:
            continue
        cursor.execute(f"DELETE FROM {_quoted(table.schema)}.{_quoted(table.name)};")
        deleted[table.qualified] = int(cursor.rowcount if cursor.rowcount is not None else 0)
    _set_foreign_keys(cursor, enabled=True)
    return deleted


def _reseed_identity_columns(cursor: Any, tables: list[TableInfo]) -> None:
    cursor.execute(
        """
SELECT s.name, t.name
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = 'dbo'
  AND OBJECTPROPERTY(t.object_id, 'TableHasIdentity') = 1;
"""
    )
    identity_tables = [(str(row[0]), str(row[1])) for row in cursor.fetchall()]
    resettable = {(table.schema, table.name) for table in tables if table.name not in PRESERVED_TABLES}
    for schema, table in identity_tables:
        if (schema, table) in resettable:
            cursor.execute(f"DBCC CHECKIDENT ('[{schema}].[{table}]', RESEED, 0) WITH NO_INFOMSGS;")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually delete data. Without this, only prints a dry run.")
    args = parser.parse_args()

    connection = open_azure_sql_connection()
    try:
        cursor = connection.cursor()
        database_name, server_name = _database_identity(cursor)
        before = _table_infos(cursor)

        print("Stats Azure SQL fresh-install reset")
        print("Connection source: stats-runtime environment")
        print("Secret policy: connection string is intentionally not printed")
        print(f"database_name={database_name}")
        print(f"server_name={server_name}")
        print(f"mode={'EXECUTE' if args.execute else 'DRY_RUN'}")
        print()
        print("Tables before reset:")
        print("table | row_count | action")
        for table in before:
            action = "preserve" if table.name in PRESERVED_TABLES else "delete"
            print(f"{table.qualified} | {table.row_count} | {action}")

        if not args.execute:
            print()
            print("Result: DRY_RUN - no rows were deleted")
            return 0

        deleted = _delete_tables(cursor, before)
        _reseed_identity_columns(cursor, before)
        connection.commit()

        seed_recognition_settings_if_empty(connection)

        after = _table_infos(cursor)
        print()
        print("Deleted rows:")
        print("table | deleted_rows")
        for table_name in sorted(deleted):
            print(f"{table_name} | {deleted[table_name]}")
        print()
        print("Tables after reset:")
        print("table | row_count")
        for table in after:
            print(f"{table.qualified} | {table.row_count}")
        print()
        print("Result: PASSED - database reset to fresh-install data state")
        return 0
    except Exception:
        connection.rollback()
        print("Result: FAILED - reset rolled back")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
