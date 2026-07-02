"""M12 Email Ingestion database evidence check.

Run after an email Run import has handed PDFs to Blob intake and the automated
"Ingest to database" step has completed. The script queries Azure SQL from inside
the Stats runtime container and proves the whole chain: document/batch rows with
Blob linkage (stats_documents.storage_reference is REQUIRED unless
--allow-legacy-storage-reference), a completed processing job, review-item counts,
and transaction rows printed as identifiers/statuses only. It never prints
connection strings, tokens, passwords, document contents, or transaction values
(descriptions, amounts, currencies, directions, dates are not selected).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap


CONTAINER = "stats-runtime"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def run_query(query_code: str, env_vars: dict[str, str], target: str) -> subprocess.CompletedProcess:
    """Run the query code inside the runtime container (default) or locally (local/cloud).

    The local/cloud targets execute with the LOCAL Python against Azure SQL, so they need
    AZURE_SQL_CONNECTIONSTRING in the local environment, pyodbc + ODBC Driver 18
    installed, and a SQL firewall rule for this workstation's IP.
    """
    if target in {"local", "cloud"}:
        env = {**os.environ, **env_vars}
        if not (env.get("AZURE_SQL_CONNECTIONSTRING") or env.get("SQL_CONNECTION_STRING")):
            fail(
                f"AZURE_SQL_CONNECTIONSTRING must be set in the local environment for --target {target} "
                "(plus local pyodbc/ODBC Driver 18 and a SQL firewall rule for this workstation)."
            )
        return subprocess.run([sys.executable, "-c", query_code], check=False, capture_output=True, text=True, env=env)
    command = ["docker", "exec"]
    for key, value in env_vars.items():
        command += ["-e", f"{key}={value}"]
    command += [CONTAINER, "/opt/stats/runtime/bin/python", "-c", query_code]
    return subprocess.run(command, check=False, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prove automated M12 database persistence for one ingestion id.")
    parser.add_argument("--ingestion-id", required=True, help="M3/M4 ingestion id from the email import handoff.")
    parser.add_argument(
        "--expected-source-type",
        default="email_attachment",
        help="Expected Stats document source_type for M12 automated ingestion.",
    )
    parser.add_argument(
        "--expected-saved-by",
        default="system-email-automation",
        help="Expected transaction batch saved_by_user_id for automated save.",
    )
    parser.add_argument(
        "--allow-legacy-storage-reference",
        action="store_true",
        help=(
            "Tolerate an empty stats_documents.storage_reference (documents ingested "
            "before the Blob-linkage fix). Default is strict: the matched document must "
            "carry the Blob reference."
        ),
    )
    parser.add_argument("--target", choices=["local", "container", "cloud"], default="container")
    args = parser.parse_args()

    query_code = textwrap.dedent(
        """
        import os
        import sys

        ingestion_id = os.environ["M12_EVIDENCE_INGESTION_ID"]
        expected_source_type = os.environ["M12_EVIDENCE_SOURCE_TYPE"]
        expected_saved_by = os.environ["M12_EVIDENCE_SAVED_BY"]
        allow_legacy_storage_ref = os.environ.get("M12_EVIDENCE_ALLOW_LEGACY_STORAGE_REF") == "1"

        connection_string = os.environ.get("AZURE_SQL_CONNECTIONSTRING") or os.environ.get("SQL_CONNECTION_STRING")
        if not connection_string:
            raise SystemExit("AZURE_SQL_CONNECTIONSTRING is not configured in the runtime container")

        if "Driver=" not in connection_string:
            connection_string = "Driver={ODBC Driver 18 for SQL Server};" + connection_string
        connection_string = (
            connection_string
            .replace("Initial Catalog=", "Database=")
            .replace("User ID=", "UID=")
            .replace("Password=", "PWD=")
            .replace("Encrypt=True", "Encrypt=yes")
            .replace("Encrypt=False", "Encrypt=no")
            .replace("TrustServerCertificate=True", "TrustServerCertificate=yes")
            .replace("TrustServerCertificate=False", "TrustServerCertificate=no")
        )

        import pyodbc

        with pyodbc.connect(connection_string, timeout=10) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name;")
            identity = cursor.fetchone()
            print("Database proof:")
            print(f"database={identity.database_name} server={identity.server_name}")
            print("Query:")
            print("stats_documents + transaction_batches by ingestion_id")
            cursor.execute(
                '''
                SELECT TOP (20)
                    d.document_id,
                    d.ingestion_id,
                    d.source_type,
                    d.original_filename,
                    d.status AS document_status,
                    d.storage_reference,
                    d.validation_result_id,
                    tb.transaction_batch_id,
                    tb.status AS batch_status,
                    tb.saved_record_count,
                    tb.warning_record_count,
                    tb.invalid_record_count,
                    tb.saved_by_user_id
                FROM dbo.stats_documents AS d
                LEFT JOIN dbo.transaction_batches AS tb
                    ON tb.document_id = d.document_id
                WHERE d.ingestion_id = ?
                ORDER BY d.created_at_utc DESC;
                ''',
                ingestion_id,
            )
            rows = cursor.fetchall()

            # Processing-job linkage: the automated pipeline must have created and
            # completed an M9 processing job for this ingestion id.
            print("Processing job query:")
            print("document_processing_jobs by ingestion_id")
            cursor.execute(
                '''
                SELECT TOP (5)
                    job_id, ingestion_id, status, stage, source_type,
                    parse_id, extraction_id, validation_id, error_detail
                FROM dbo.document_processing_jobs
                WHERE ingestion_id = ?
                ORDER BY created_at_utc DESC;
                ''',
                ingestion_id,
            )
            job_rows = cursor.fetchall()

            document_ids = [row.document_id for row in rows]
            transaction_rows = []
            if document_ids:
                placeholders = ",".join("?" for _ in document_ids)
                print("Transaction query:")
                print("transactions by document_id from imported email PDF (identifiers/statuses only)")
                # Evidence runs use real mailbox PDFs, so sensitive columns
                # (description, amount, currency, direction, dates) are NOT
                # selected: the proof only needs traceable identifiers, statuses,
                # and counts.
                cursor.execute(
                    f'''
                    SELECT TOP (20)
                        t.transaction_id,
                        t.document_id,
                        t.transaction_batch_id,
                        t.quality_status,
                        t.review_required
                    FROM dbo.transactions AS t
                    WHERE t.document_id IN ({placeholders})
                    ORDER BY t.created_at_utc DESC;
                    ''',
                    *document_ids,
                )
                transaction_rows = cursor.fetchall()

        print(f"Rows returned: {len(rows)}")
        if not rows:
            raise SystemExit("No Stats document rows were found for the supplied ingestion id")

        passed = False
        matched_with_storage_ref = False
        matching_document_ids = set()
        for index, row in enumerate(rows, start=1):
            print(
                f"{index}. document_id={row.document_id} ingestion_id={row.ingestion_id} "
                f"source_type={row.source_type} document_status={row.document_status} "
                f"storage_reference={row.storage_reference} "
                f"batch_status={row.batch_status} saved={row.saved_record_count} "
                f"warning={row.warning_record_count} invalid={row.invalid_record_count} "
                f"saved_by={row.saved_by_user_id}"
            )
            if row.source_type == expected_source_type and row.saved_by_user_id == expected_saved_by:
                passed = True
                matching_document_ids.add(row.document_id)
                if row.storage_reference:
                    matched_with_storage_ref = True

        if not passed:
            raise SystemExit(
                "No row matched the expected automated email source_type and saved_by_user_id"
            )
        if not matched_with_storage_ref:
            # The M12 success path must prove mailbox PDF -> Blob -> database, so
            # missing Blob linkage fails by default.
            if allow_legacy_storage_ref:
                print(
                    "NOTE: storage_reference is empty (legacy pre-fix ingest); accepted "
                    "because --allow-legacy-storage-reference was set."
                )
            else:
                raise SystemExit(
                    "Matched document has no storage_reference (Blob linkage). Re-run the "
                    "ingest with current code, or pass --allow-legacy-storage-reference for "
                    "documents ingested before the Blob-linkage fix."
                )

        print(f"Processing job rows returned: {len(job_rows)}")
        if not job_rows:
            raise SystemExit("No document_processing_jobs row was found for the ingestion id")
        completed_job = False
        for index, row in enumerate(job_rows, start=1):
            print(
                f"job{index}. job_id={row.job_id} status={row.status} stage={row.stage} "
                f"source_type={row.source_type} parse_id={row.parse_id} "
                f"extraction_id={row.extraction_id} validation_id={row.validation_id} "
                f"error={row.error_detail}"
            )
            if row.status == "completed":
                completed_job = True
        if not completed_job:
            raise SystemExit("No completed processing job was found for the ingestion id")

        # Review-item counts prove the governance trail (zero is a valid outcome).
        placeholders = ",".join("?" for _ in matching_document_ids)
        cursor2_rows = []
        with pyodbc.connect(connection_string, timeout=10) as review_connection:
            review_cursor = review_connection.cursor()
            review_cursor.execute(
                f'''
                SELECT TOP (10) review_item_id, document_id, item_type, severity, status, title
                FROM dbo.review_items
                WHERE document_id IN ({placeholders})
                ORDER BY created_at_utc DESC;
                ''',
                *matching_document_ids,
            )
            cursor2_rows = review_cursor.fetchall()
        print(f"Review item rows returned: {len(cursor2_rows)}")
        for index, row in enumerate(cursor2_rows, start=1):
            print(
                f"rv{index}. review_item_id={row.review_item_id} document_id={row.document_id} "
                f"type={row.item_type} severity={row.severity} status={row.status} title={row.title}"
            )
        print(f"Transaction rows returned: {len(transaction_rows)}")
        if not transaction_rows:
            raise SystemExit("No transaction rows were found for the imported email PDF document")
        matching_transactions = [
            row for row in transaction_rows if row.document_id in matching_document_ids
        ]
        if not matching_transactions:
            raise SystemExit(
                "Transaction rows were found, but none matched the automated email document"
            )
        for index, row in enumerate(matching_transactions, start=1):
            print(
                f"tx{index}. transaction_id={row.transaction_id} document_id={row.document_id} "
                f"batch_id={row.transaction_batch_id} quality={row.quality_status} "
                f"review_required={bool(row.review_required)}"
            )
        print(f"Matching transaction count: {len(matching_transactions)}")
        print("Result: PASSED")
        """
    )

    result = run_query(
        query_code,
        {
            "M12_EVIDENCE_INGESTION_ID": args.ingestion_id,
            "M12_EVIDENCE_SOURCE_TYPE": args.expected_source_type,
            "M12_EVIDENCE_SAVED_BY": args.expected_saved_by,
            "M12_EVIDENCE_ALLOW_LEGACY_STORAGE_REF": "1" if args.allow_legacy_storage_reference else "0",
        },
        args.target,
    )
    print("M12 Email Ingestion database evidence check")
    print(f"Target: {args.target}")
    print(f"Executed: {'local workstation -> Azure SQL' if args.target in {'local', 'cloud'} else f'inside {CONTAINER}'}")
    print(f"Ingestion id: {args.ingestion_id}")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        fail(result.stderr.strip() or "database evidence query failed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Result: INTERRUPTED")
        sys.exit(130)
