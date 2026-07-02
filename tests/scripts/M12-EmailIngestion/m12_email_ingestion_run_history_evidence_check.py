"""M12 Email Ingestion run-history evidence check.

Proves the Azure SQL run-history evidence chain for one import run from inside the
Stats runtime container:

- the run header row exists with direct evidence columns, including
  password_required_count AND password_failed_count (migration applied);
- candidate rows carry sha256 (handed-off content hash), original_sha256
  (encrypted-source hash for rule-unlocked PDFs), and a stable dedup_key;
- processed markers exist for candidates already pushed to the database.

It never prints connection strings, tokens, mailbox/PDF passwords, email bodies,
or attachment contents (subjects are stored redacted).
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
    parser = argparse.ArgumentParser(description="Prove M12 run-history SQL evidence for one import run.")
    parser.add_argument("--run-id", default="", help="M12 run id (email_run_...). Default: newest run.")
    parser.add_argument("--source-id", default="", help="Optional source filter when defaulting to the newest run.")
    parser.add_argument("--target", choices=["local", "container", "cloud"], default="container")
    args = parser.parse_args()

    query_code = textwrap.dedent(
        """
        import json
        import os

        run_id = os.environ.get("M12_EVIDENCE_RUN_ID", "")
        source_id = os.environ.get("M12_EVIDENCE_SOURCE_ID", "")

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

            # Migration proof: the direct evidence columns exist.
            cursor.execute(
                "SELECT COL_LENGTH('dbo.email_ingestion_runs', 'password_failed_count') AS pf, "
                "COL_LENGTH('dbo.email_ingestion_run_candidates', 'original_sha256') AS os;"
            )
            columns = cursor.fetchone()
            if columns.pf is None:
                raise SystemExit("email_ingestion_runs.password_failed_count column is missing (run migration)")
            if columns.os is None:
                raise SystemExit("email_ingestion_run_candidates.original_sha256 column is missing (run migration)")
            print("PASS: password_failed_count and original_sha256 evidence columns exist")

            if not run_id:
                where = "WHERE source_id = ?" if source_id else ""
                params = [source_id] if source_id else []
                cursor.execute(
                    f"SELECT TOP (1) run_id FROM dbo.email_ingestion_runs {where} "
                    "ORDER BY started_at_utc DESC, run_id DESC;",
                    *params,
                )
                newest = cursor.fetchone()
                if not newest:
                    raise SystemExit("No email ingestion runs were found in run history")
                run_id = newest.run_id
            print(f"Run id: {run_id}")

            cursor.execute(
                '''
                SELECT run_id, source_id, mode, status, started_at_utc, completed_at_utc,
                       message_count, attachment_count, retrieved_count, handed_off_count,
                       skipped_count, duplicate_count, failed_count,
                       password_required_count, password_failed_count
                FROM dbo.email_ingestion_runs
                WHERE run_id = ?;
                ''',
                run_id,
            )
            run = cursor.fetchone()
            if not run:
                raise SystemExit(f"Run header row was not found: {run_id}")
            print("Run header:")
            print(
                f"run_id={run.run_id} source_id={run.source_id} mode={run.mode} status={run.status} "
                f"started={run.started_at_utc} completed={run.completed_at_utc}"
            )
            print(
                f"counts: messages={run.message_count} attachments={run.attachment_count} "
                f"retrieved={run.retrieved_count} handed_off={run.handed_off_count} "
                f"skipped={run.skipped_count} duplicates={run.duplicate_count} failed={run.failed_count} "
                f"password_required={run.password_required_count} password_failed={run.password_failed_count}"
            )

            cursor.execute(
                '''
                SELECT candidate_id, filename, status, sha256, original_sha256, dedup_key,
                       handoff_ingestion_id, handoff_status, subject_redacted
                FROM dbo.email_ingestion_run_candidates
                WHERE run_id = ?
                ORDER BY id;
                ''',
                run_id,
            )
            candidates = cursor.fetchall()
            print(f"Candidate rows: {len(candidates)}")
            if not candidates:
                raise SystemExit("Run has no candidate rows; run history evidence is incomplete")
            handoff_ids = []
            for index, row in enumerate(candidates, start=1):
                print(
                    f"{index}. candidate_id={row.candidate_id} filename={row.filename} status={row.status} "
                    f"sha256={row.sha256} original_sha256={row.original_sha256} "
                    f"dedup_key={row.dedup_key} handoff_ingestion_id={row.handoff_ingestion_id} "
                    f"handoff_status={row.handoff_status} subject={row.subject_redacted}"
                )
                if not row.dedup_key:
                    raise SystemExit(f"Candidate {row.candidate_id} has no dedup_key")
                if row.status in ("handed_off",) and not row.sha256:
                    raise SystemExit(f"Handed-off candidate {row.candidate_id} has no content sha256")
                if row.original_sha256 and row.sha256 == row.original_sha256:
                    raise SystemExit(
                        f"Candidate {row.candidate_id} hash provenance looks wrong: "
                        "sha256 must be the processed content hash, distinct from original_sha256"
                    )
                if row.handoff_ingestion_id:
                    handoff_ids.append(row.handoff_ingestion_id)

            processed_rows = []
            if handoff_ids:
                placeholders = ",".join("?" for _ in handoff_ids)
                cursor.execute(
                    f'''
                    SELECT ingestion_id, document_id, run_id, processed_at_utc
                    FROM dbo.email_ingestion_processed
                    WHERE ingestion_id IN ({placeholders});
                    ''',
                    *handoff_ids,
                )
                processed_rows = cursor.fetchall()
            print(f"Processed markers: {len(processed_rows)}")
            for index, row in enumerate(processed_rows, start=1):
                print(
                    f"p{index}. ingestion_id={row.ingestion_id} document_id={row.document_id} "
                    f"run_id={row.run_id} processed_at={row.processed_at_utc}"
                )
            if handoff_ids and not processed_rows:
                print(
                    "NOTE: no processed markers yet - run 'Ingest to database' (or wait for the "
                    "scheduled retry) and re-run this check for the database-processed proof."
                )

        print("Result: PASSED")
        """
    )

    result = run_query(
        query_code,
        {
            "M12_EVIDENCE_RUN_ID": args.run_id,
            "M12_EVIDENCE_SOURCE_ID": args.source_id,
        },
        args.target,
    )
    print("M12 Email Ingestion run-history evidence check")
    print(f"Target: {args.target}")
    print(f"Executed: {'local workstation -> Azure SQL' if args.target in {'local', 'cloud'} else f'inside {CONTAINER}'}")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        fail(result.stderr.strip() or "run history evidence query failed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Result: INTERRUPTED")
        sys.exit(130)
