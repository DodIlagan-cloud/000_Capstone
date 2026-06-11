from __future__ import annotations

from stats_data.database import open_azure_sql_connection


QUERY = """
SELECT label_scope, label_key, values_json, is_active
FROM dbo.recognition_labels
WHERE label_scope IN ('document','transaction','spending')
  AND label_key IN ('receipt','purchase','shopping','transport')
ORDER BY label_scope, label_key;
""".strip()


def main() -> None:
    print("Azure SQL runtime query evidence")
    print("Connection source: stats-runtime environment")
    print("Secret policy: connection string is intentionally not printed")
    print("")
    print("Connection identity query:")
    print("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name;")
    with open_azure_sql_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name;")
        database_name, server_name = cursor.fetchone()
        print(f"database_name={database_name}")
        print(f"server_name={server_name}")
        print("")
        print("Recognition settings query:")
        print(QUERY)
        print("")
        cursor.execute(QUERY)
        columns = [column[0] for column in cursor.description]
        print(" | ".join(columns))
        rows = cursor.fetchall()
        for row in rows:
            print(" | ".join(str(value)[:120] for value in row))
        print(f"Row count: {len(rows)}")
    print("")
    expected_database = "sqldb-stats-dev"
    if str(database_name).lower() != expected_database:
        raise SystemExit(f"Result: FAILED - expected database {expected_database}, got {database_name}")
    if len(rows) < 4:
        raise SystemExit("Result: FAILED - expected target recognition labels were not returned")
    print("Result: PASSED - query executed against Azure SQL sqldb-stats-dev from stats-runtime")


if __name__ == "__main__":
    main()
