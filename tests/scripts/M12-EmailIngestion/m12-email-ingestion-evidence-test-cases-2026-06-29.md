<!-- M12 - Email Ingestion Module Start -->

# M12 Email Ingestion Evidence Test Cases - 2026-06-29

These test cases capture the evidence-driven checks for the M12 Email Ingestion work completed from 2026-06-29 through 2026-07-01. They are designed for the Stats runtime container and must not expose mailbox app passwords, PDF passwords, connection strings, email bodies, or raw attachment contents.

## Current Acceptance Boundary

The current test session accepts **M12 Email Ingestion Evidence - Manual Import,
Blob Handoff, and Database Processing** only:

- Manual Upload remains unchanged and is captured first in the same Edge session.
- Email Setup retrieves eligible PDF attachments from the configured mailbox and
  hands them to M3/M4 Blob-backed intake.
- Blob evidence is before/after: the source mailbox PDF exists before import and
  the imported Blob row exists after import.
- `Ingest to database`, when tested, proves a system-provenance database save from
  the imported run. It must be labelled Phase A scaffold evidence, not final
  governed auto-save.
- Event Grid, Durable Functions, Container Apps Job cron, and final recognition
  governance are future acceptance items.

## Runtime Target

| Target | Expected URL |
| --- | --- |
| Stats Web | `http://127.0.0.1:8080` |
| Email Ingestion API | `http://127.0.0.1:8019` |
| Runtime container | `stats-runtime` |

## Test Prerequisites

- `STATS_INTERNAL_API_KEY` must be configured before running process-imported,
  file-intake readback, or scheduled-run checks.
- `STATS_TESTDATA_DIR` must point to a directory with top-level PDFs when
  file-intake real-PDF unit tests are included in the run.
- The selected Email Setup source profile must already have a saved mailbox app
  password secret. Later connection/import checks should leave the password field
  blank and rely on `secret_ref`.
- PDF password evidence uses configured saved PDF password rules in M12. Full
  locked-PDF parsing/database proof is only in scope when the downstream path
  receives the unlocked/decrypted PDF for that run; one-time password queue/retry is
  deferred.

## Failure-Stop Rule

Run the evidence workflow one step at a time. After each step, verify the expected
result and capture the required evidence before moving on.

If any unexpected failure occurs, stop the testing loop immediately. Do not continue
to later steps until the failure is inspected and reported. The failure report must
include:

- the failed step,
- the expected result,
- the actual result,
- the likely cause based on UI, logs, API, or database evidence,
- the recommended fix or decision,
- whether continuing would risk bad evidence or data mutation.

Intentional failure tests are allowed only when labelled as intentional failure
evidence. They must show the failed state, the reason, the fix, and the successful
rerun before the evidence package is considered complete.

## One-Command Evidence Suite (preferred)

Run from `C:\000_Capstone` after the runtime container is up and after the manual
`Run import` / `Ingest to database` steps whose evidence is being captured:

```powershell
python tests\\scripts\\M12-EmailIngestion\m12_evidence_suite.py --visual-evidence-dir <screenshot-folder>
```

The suite runs, in order: the M12 unit tests, the runtime evidence check, the
run-history SQL evidence check, the Blob after-proof, the Azure SQL database
proof, and the visual-evidence manifest. It auto-discovers the newest handed-off
run and its `ingestion_id` from the M12 run-history API (override with `--run-id`
/ `--ingestion-id`), writes every transcript into a timestamped
`m12-evidence-suite-<timestamp>` folder next to the scripts, and prints a summary
matrix. The suite is read-only: it never triggers an import or a database ingest.

**Acceptance gate.** The default mode is acceptance: every core proof (unit,
runtime, run_history, blob, database, visual) must actually run and pass. A
skipped core step (missing handed-off run, no `az login`, no
`--visual-evidence-dir`, or an explicit `--skip-*` flag) downgrades the verdict
to `Result: INCOMPLETE` (exit code 2) - the suite cannot report acceptance
success without proving mailbox PDF -> Blob -> database plus the visual set.
`Result: PASSED` from a default-mode run is therefore sufficient for the
acceptance evidence package.

**Visual evidence (before/after data-state model).** Screenshots prove the STATE
of the acted-upon data before and after a step, and are only required where that
state lives on a surface the suite cannot query: the external mailbox, the Azure
Portal, and the app UI. Every machine-queryable state (run history rows, blob
listing, SQL rows) is proven by the suite's transcripts - a screenshot of
queryable text is optional extra, never required. The whole set is BOUND TO ONE
RUN: the manifest's `run_id` must match the run the suite proves, and its
`subject_file` must be a candidate of that run, so the before and after pictures
provably show the same PDF traveling the chain.

Required proofs (three):

| Proof key in filename | Transition / phase | Required screenshot | Allowed capture_method |
| --- | --- | --- | --- |
| `mailbox-before` | mailbox_to_blob / before | Mailbox message showing the subject PDF before import | `mailbox_browser` |
| `blob-after` | mailbox_to_blob / after | Blob row under `intake/<ingestion_id>` after import | `azure_portal`, `storage_browser` |
| `documents-view` | database_to_app / after | Documents/Reports showing the ingested document | `windows_browser` |

Optional proofs (accepted, never required): `run-status` (Email Setup run status;
the run-history transcript is authoritative), `mailbox-after` (message read/moved
when the post-process policy runs), `db-proof` (terminal capture, redundant with
the database transcript).

The identity thread across the set: the filename in `mailbox-before` = the
manifest `subject_file` = a candidate filename in the run-history transcript; the
`ingestion_id` in the blob path = the same id in the SQL `storage_reference`; the
filename in `documents-view` = the same document. That thread is what makes three
screenshots sufficient.

Manifest rules (unchanged from the anti-synthetic hardening): every image/PDF in
the folder must be listed, `synthetic: false`, `live_capture: true`, filenames
containing synthetic/mock/sample/generated/demo markers are rejected, and each
proof key only accepts its allowed capture methods. The suite records each
capture's sha256 into `visual.txt` as a permanent text integrity anchor.

Example files: `01-mailbox-before.png`, `02-blob-after.png`,
`03-documents-view.png`.

Example `visual-evidence-manifest.json`:

```json
{
  "run_id": "email_run_abc123def456",
  "subject_file": "statement.pdf",
  "subject_sha256": "<optional: sha256 of the PDF content, checked against the run candidate>",
  "items": [
    {
      "proof_key": "mailbox-before",
      "file": "01-mailbox-before.png",
      "capture_method": "mailbox_browser",
      "synthetic": false,
      "live_capture": true
    },
    {
      "proof_key": "blob-after",
      "file": "02-blob-after.png",
      "capture_method": "azure_portal",
      "synthetic": false,
      "live_capture": true
    },
    {
      "proof_key": "documents-view",
      "file": "03-documents-view.png",
      "capture_method": "windows_browser",
      "synthetic": false,
      "live_capture": true
    }
  ]
}
```

The suite writes per-proof coverage, the run binding, and the sha256 anchors into
`visual.txt` and FAILS the step when any required proof is missing, when the
manifest is not bound to the proven run, or when any attestation rule is
violated. Unrelated, synthetic, or wrong-run screenshots cannot satisfy the gate.

**Prep mode.** Use `--prep` (optionally with `--skip-unit`, `--skip-blob`,
`--skip-database`) for a terminal-only diagnostic where skips are allowed. A
prep-mode transcript is NOT valid acceptance evidence; the summary records the
mode so the two cannot be confused.

For host-running diagnostics that should use the same Stats Web proxy shape as
cloud, use `--target local` and pass the local Stats Web URL if it is not
`http://127.0.0.1:8080`:

```powershell
$env:STATS_INTERNAL_API_KEY = "<local internal key>"
python tests\\scripts\\M12-EmailIngestion\m12_evidence_suite.py --target local `
    --web-base-url http://127.0.0.1:8080 `
    --prep --skip-blob --skip-database
```

## Cloud Evidence Run (Azure Container Apps)

The same suite proves the DEPLOYED runtime with `--target cloud`. All API calls go
through the Stats Web public ingress (the proxy fronts every module), so this
covers the real cloud path end-to-end:

```powershell
$env:STATS_INTERNAL_API_KEY = "<internal key for this session>"
$env:AZURE_SQL_CONNECTIONSTRING = "<cloud-dev connection string>"
python tests\\scripts\\M12-EmailIngestion\m12_evidence_suite.py --target cloud `
    --web-base-url https://ca-stats-dev-001.<env>.azurecontainerapps.io `
    --visual-evidence-dir <screenshot-folder>
```

Cloud-target prerequisites (all operator-side; nothing execs into the replica):

- The deployed Stats Container App has the M12 cloud runtime env from
  `infrastructure/cloud/azure-container-apps.env.example`: `EMAIL_PROVIDER=imap`,
  `EMAIL_INGESTION_MODE=handoff`, `EMAIL_SOURCE_CONFIG_STORE=azure_sql`, the
  chosen `EMAIL_SECRET_PROVIDER`, container-local downstream URLs
  (`http://localhost:8014` through `8018`), Azure SQL, Blob Storage, and the
  internal API key configured as secret references.
- `az login` done (Blob proof uses the local az CLI, same as the container target).
- `STATS_INTERNAL_API_KEY` set in the shell - there is no `docker exec` path to
  read it from the cloud replica. Clear it after the session.
- `AZURE_SQL_CONNECTIONSTRING` set in the shell, local `pyodbc` + ODBC Driver 18
  installed, and a SQL server firewall rule for this workstation's IP - the
  run-history and database proofs execute locally against Azure SQL instead of
  inside the container.
- `AZURE_STORAGE_ACCOUNT_NAME` / `AZURE_STORAGE_CONTAINER_NAME` set locally (or
  pass `--account` / `--container` to the blob check).
- The manual `Run import` / `Ingest to database` steps are performed against the
  CLOUD Email Setup page (`https://<app-url>/EmailSetup`), and the visual set is
  captured from the cloud UI/portal (`run-status`, `blob-after`,
  `documents-view` screenshots must show the cloud URL bar, not localhost).

Differences from the container target, recorded in the transcripts: the M12
`/health` endpoint is not proxied, so cloud liveness is proven by the
authenticated sources call through the ingress; and the in-replica secret probe
is replaced by the API-level saved-secret proof (blank-password test-connection
resolving the secret by reference). The individual checks also accept
`--target cloud` (`runtime` additionally needs `--web-base-url`) for step-by-step
capture. The scheduled-tick cloud proof stays separate: start the Container Apps
Job (`az containerapp job start --name job-stats-m12-email-ingestion ...`) and
capture its execution log plus the `last_auto_run_at` change.

## Automated Evidence Check

The individual checks remain available for step-by-step capture. Run from
`C:\000_Capstone` after the runtime container is up:

```powershell
python tests\\scripts\\M12-EmailIngestion\m12_email_ingestion_runtime_evidence_check.py
```

Expected result:

```text
Result: PASSED
```

The script verifies the runtime page, runtime JavaScript, M12 health endpoint, source-profile API privacy, central secret availability by reference, and saved-secret test-connection behavior when a configured source is present.

## Run-History SQL Evidence Check

Proves the Azure SQL run-history chain for one run (header row with
`password_required_count` and `password_failed_count`, candidate rows with
`sha256` / `original_sha256` / `dedup_key`, and processed markers):

```powershell
python tests\\scripts\\M12-EmailIngestion\m12_email_ingestion_run_history_evidence_check.py --run-id <run-id-from-email-setup>
```

Omit `--run-id` to prove the newest run. Expected result: `Result: PASSED`. The
check also fails fast when the `email_ingestion_runs.sql` migration has not been
applied (missing evidence columns), which makes stale-schema screenshots impossible.

## Blob Import Evidence Check

Run this after clicking `Run import` from `http://127.0.0.1:8080/EmailSetup` and confirming at least one PDF candidate is handed off/imported. Use the `ingestion_id` from the run result or M12 handoff log when available:

```powershell
python tests\\scripts\\M12-EmailIngestion\m12_email_ingestion_blob_evidence_check.py --ingestion-id <ingestion-id-from-run>
```

If the exact ingestion id is not available, run the same check with the configured intake prefix:

```powershell
python tests\\scripts\\M12-EmailIngestion\m12_email_ingestion_blob_evidence_check.py
```

Expected result:

```text
Result: PASSED
```

Capture this terminal output as evidence. Also open the same storage account and container in Azure Portal / Storage Browser, navigate to the printed prefix, and capture a browser screenshot showing the imported blob row. Do not capture connection strings, account keys, SAS tokens, or file contents.

## Phase A Database Evidence Check

Run this after `Run import` succeeds and `Ingest to database` completes for the imported PDFs. Use the M3/M4 ingestion id from the Email Setup run result, Recent runs detail, or redacted M12 handoff log:

```powershell
python tests\\scripts\\M12-EmailIngestion\m12_email_ingestion_database_evidence_check.py --ingestion-id <ingestion-id-from-run>
```

Expected result:

```text
Result: PASSED
```

The script runs the Azure SQL query from inside `stats-runtime`, prints `DB_NAME()` / `@@SERVERNAME`, and proves the whole email-to-database workflow: matching `stats_documents` plus `transaction_batches` rows, transactions, a completed `document_processing_jobs` row with its parse/extraction/validation ids, and `review_items` counts for the saved document (zero is a valid outcome). It must show `source_type=email_attachment` and `saved_by_user_id=system-email-automation` for at least one row, and that row must carry `storage_reference` (Blob linkage) - an empty reference fails the check unless `--allow-legacy-storage-reference` is passed for documents ingested before the Blob-linkage fix. Because evidence runs use real mailbox PDFs, transaction rows are printed as identifiers and statuses only: descriptions, amounts, currencies, directions, and dates are never selected or printed. It must not print connection strings, SQL passwords, document contents, mailbox passwords, or PDF passwords. This proves the current Phase A process-to-database scaffold only; it does not prove final governed auto-save.

## Evidence Test Matrix

| ID | Area | Test Case | Evidence to Capture | Expected Result |
| --- | --- | --- | --- | --- |
| M12-EV-001 | Runtime health | Open Email Ingestion API health endpoint. | Terminal output or browser screenshot for `http://127.0.0.1:8019/health`. | Status is `healthy`; service is `Email Ingestion Module`; provider/mode are present. |
| M12-EV-001A | One-browser evidence setup | Use one visible Microsoft Edge session for `/Upload`, `/EmailSetup`, and any app result pages. | Screenshots all show the same browser chrome/address bar style. | Evidence is not mixed across multiple browser sessions. |
| M12-EV-001B | Manual Upload regression checkpoint | In the same browser session, open `http://127.0.0.1:8080/Upload` before the M12 checks. | Browser screenshot with URL bar and the existing Manual Upload page. | Manual Upload still loads and remains a user-driven review/save workflow; M12 is additive. |
| M12-EV-002 | Email Setup page load | Open `http://127.0.0.1:8080/EmailSetup` while authenticated. | Browser screenshot with address bar and Email Setup page visible. | Page loads the operational mailbox source profile UI, not the old placeholder. |
| M12-EV-003 | IMAP controls simplified | Inspect Email Setup page and served JS. | Runtime check output and browser screenshot of profile area. | Users see `IMAP host` only for Custom IMAP; `IMAP port` and `Use SSL` are not visible. Backend keeps secure defaults. |
| M12-EV-004 | Provider-neutral setup | Select provider dropdown. | Browser screenshot of provider dropdown. | Provider options include Custom IMAP, Gmail, Outlook / Microsoft 365, and Yahoo Mail without making the module Yahoo-only. |
| M12-EV-005 | Mailbox password save privacy | Save a profile with a mailbox app password, then reload/select it. | Browser screenshot after selecting saved profile and terminal output from runtime check. | Password field is blank; hint says saved mailbox app password is available; source API response does not contain `app_password`. |
| M12-EV-006 | Saved secret resolves centrally | Query secret availability through runtime helper without printing secret value. | Terminal output from runtime check. | Profile has a `secret_ref`; central secret row exists/resolves as available; no raw secret is printed. |
| M12-EV-007 | Test connection uses saved secret | Click Test connection after selecting profile and leaving password blank. | Browser screenshot near Test connection status or terminal output from runtime check. | Test connection succeeds or returns a specific provider/folder error. If it fails, evidence must show the exact reason and the fix, such as re-saving the mailbox app password or correcting folder case. |
| M12-EV-008 | Folder is honored | Change folder field, test connection or run ingestion. | Browser screenshot showing folder and result status, plus terminal/API output if available. | Test/run request uses the typed folder through `mailbox_folder`; backend returns the folder actually tested/used. |
| M12-EV-009 | PDF passwords collapsed | Select a profile with saved PDF passwords. | Browser screenshot of profile area. | `Saved PDF passwords` is collapsed by default, even when saved password entries exist. |
| M12-EV-010 | PDF-only attachment handling | Run dry run against a mailbox containing PDFs and non-PDF inline assets. | Browser screenshot of run results. | PDF attachments are considered; non-PDF inline images are ignored by retrieval and do not clutter results as unsupported attachment rows. |
| M12-EV-011 | Saved PDF passwords | Add more than two saved PDF passwords and save profile. | Browser screenshot of collapsed summary and terminal/API response with redacted values. | Multiple password references round-trip; raw PDF passwords do not appear in API response or logs. |
| M12-EV-012 | Profile row actions | View Configured mailboxes table. | Browser screenshot of table. | Row actions include `Select` and `Delete`; selection wording says `Select`, not `Edit`. |
| M12-EV-013 | Source pagination | Seed or configure more than 10 mailbox profiles. | Browser screenshot of Configured mailboxes table footer. | Table shows at most 10 rows per page and displays page number buttons at the bottom. |
| M12-EV-014 | Run result pagination | Run/dry-run against more than 10 eligible PDF candidates. | Browser screenshot of run results footer. | Result table shows at most 10 rows per page and displays page number buttons at the bottom. |
| M12-EV-015 | Message limit control | Run with Max messages and with No message limit selected. | Browser screenshots or API payload/output. | Default max is explicit; `No message limit` sends `max_messages = 0`. |
| M12-EV-016 | Sender/subject filters | Configure sender allowlist and subject keywords, then dry run. | Browser screenshot of profile fields and run summary. | Results reflect the configured filters; sender-only or subject-only matches are accepted according to current OR semantics. |
| M12-EV-017 | Mailbox before proof | Before Run import, capture the mailbox message/attachment in the already signed-in mailbox browser. | Browser screenshot of the mailbox list/message showing the PDF attachment name, redacted as needed. | Reviewer can see the source PDF existed before Stats imported it. |
| M12-EV-018 | Import run handoff | Click Run import for retrieved/unlocked PDFs. | Browser screenshot of run summary and M3/M4 handoff evidence. | Eligible PDFs are handed off to file ingestion; locked PDFs are unlocked by configured saved PDF password rules or marked password-related instead of silently failing. |
| M12-EV-019 | Blob container after proof | After Run import, list the configured Blob container/prefix and open the container in Azure Portal or Storage Browser. | Terminal screenshot from `m12_email_ingestion_blob_evidence_check.py` plus browser screenshot of the Blob container row for the imported PDF. | Imported PDF appears under the configured intake prefix/ingestion id; evidence shows account, container, blob name, size/content type/last modified without exposing storage secrets or file contents. |
| M12-EV-020 | Phase A database ingest | Click `Ingest to database` after a successful Run import. | Browser screenshot with URL bar showing Email Setup run status and processed/saved/failed/review counts. | The button processes the exact import `run_id`; status shows processed count, saved record count, failed count, and review item count. Label this Phase A scaffold evidence. |
| M12-EV-021 | Azure SQL database proof | Run `m12_email_ingestion_database_evidence_check.py --ingestion-id <ingestion-id>`. | Terminal screenshot showing database/server identity, query label, returned rows, `source_type=email_attachment`, `saved_by_user_id=system-email-automation`, and `Result: PASSED`. | The imported email PDF has a database-backed Stats document/batch result. This proves Phase A process-to-database, not final governed auto-save. |
| M12-EV-022 | Documents/Reports visibility | Open `http://127.0.0.1:8080/Documents` or Reports after database ingest. | Browser screenshot with URL bar and the imported document/report result visible. | The email-ingested document appears through the normal database-backed app views without changing the manual Upload workflow. |
| M12-EV-023 | Security log review | Review runtime logs after saving/testing/running. | Terminal screenshot with redacted grep/check output. | Logs do not contain mailbox app passwords, PDF passwords, email bodies, raw attachment contents, SQL connection strings, or tokens. |
| M12-EV-024 | Import trace logging | Run import for a PDF and inspect M12 logs. | Terminal screenshot or captured log excerpt. | Logs include `run_id`, source profile ID, message ID, attachment ID, handoff source ID, M3/M4 `ingestion_id`, handoff status, and Blob `content_reference`; logs do not expose passwords or raw attachment content. |
| M12-EV-025 | Failure/fix evidence | Trigger or observe a known actionable failure, such as incorrect folder case or unreadable saved secret, then correct it and rerun. | Browser screenshot of failed status, terminal/log root-cause proof, and successful rerun screenshot. | Failure is specific and understandable; the fix is documented; the rerun proves recovery. |
| M12-EV-026 | Process-imported configuration failure | Run or simulate process-imported with missing/invalid internal service key in a controlled test context. | Unit-test output or UI/API evidence showing the failed result. | Result is `failed` with `processed_count = 1`, `failed_count = 1`, and a visible reason such as missing `STATS_INTERNAL_API_KEY`. |
| M12-EV-027 | Process-imported retry idempotency | Run `Ingest to database` again for an already processed import run, or use the unit evidence. | Browser/API/unit-test evidence showing already-processed status. | The same M3/M4 ingestion is not fetched or saved again; result reports `already_processed` instead of duplicating database rows. |
| M12-EV-028 | Scheduled run guard | Exercise scheduler unit/API path for off/disabled profiles, due profiles, failed import, and no-run-id import. | Unit-test output or internal endpoint evidence. | Only due enabled profiles run; scheduler passes the exact returned `run_id`; failed/no-run-id imports do not process older latest runs and do not advance `last_auto_run_at`. |
| M12-EV-029 | Delete profile confirmation | Create or use a disposable mailbox source profile, click `Delete`, then cancel once and confirm once. | Browser screenshots showing the inline confirmation, cancel state, confirmed deletion, and refreshed Configured mailboxes table. | Cancel keeps the profile; Confirm removes the source row from the UI without exposing mailbox/PDF secrets. The production profile used for ingestion is not deleted during evidence unless intentionally recreated. |
| M12-EV-030 | Delete profile API behavior | Call or observe `DELETE /api/v1/email-ingestion-sources/{source_id}` for a disposable profile, then refresh/list sources. | API/terminal output or UI evidence with secret values redacted. | Existing source returns deleted status and no longer appears in `GET /email-ingestion-sources`; missing source returns 404; raw secret values are never returned. |
| M12-EV-031 | Run-history SQL evidence | Run `m12_email_ingestion_run_history_evidence_check.py --run-id <run-id>` after an import. | Terminal screenshot showing DB identity, run header counts (including `password_failed_count`), candidate rows with `sha256`/`original_sha256`/`dedup_key`, processed markers, and `Result: PASSED`. | Run history rows exist in Azure SQL with the direct evidence columns; missing migration columns fail the check instead of producing stale screenshots. |
| M12-EV-032 | Duplicate source create rejected | POST a create for an existing `source_id` (API) or attempt to save a new profile that collides. | API/terminal output or UI error message. | Create returns HTTP 409 with an "already exists" message; the existing profile and its `secret_ref` are unchanged. Updates still succeed through PATCH/Select. |
| M12-EV-033 | Oversized message skip visibility | Run a dry run against a mailbox message whose total MIME size exceeds the fetch safety limit (or use unit evidence `test_oversized_message_skip_is_reported_to_caller`). | Run result findings or unit-test output. | The run reports `EMAIL_MESSAGE_FETCH_SKIPPED_TOO_LARGE` with message size and limit; the message does not silently disappear. |
| M12-EV-034 | Unlocked PDF hash provenance | Import a rule-unlocked password-protected PDF, then inspect the run candidate row / run-history check output. | Run-history check output or run detail API response. | Candidate `sha256` matches the decrypted content stored in Blob/intake; `original_sha256` preserves the encrypted-source hash; the two differ. |
| M12-EV-035 | Scheduler retry of unprocessed imports | Use unit evidence `test_run_due_profiles_retries_unprocessed_earlier_runs`, or observe a tick after a failed ingest. | Unit-test output or scheduled-run response showing `retried_runs`. | A later tick re-ingests earlier handed-off runs that never reached the database (oldest first); processed markers prevent double saves. |
| M12-EV-036 | Job secret via Key Vault reference | After deploying the M12 job, show the job's secret configuration (`az containerapp job show`, secrets section). | Terminal/portal screenshot showing the secret bound as a Key Vault reference with the managed identity; no secret value visible. | The internal key is a `keyVaultUrl`/identity binding, not an inline value; the deploy script never prints or passes the raw key. |

## Screenshot Evidence Checklist

NOTE: the acceptance gate (`m12_evidence_suite.py`) requires only the three
run-bound before/after proofs above; terminal-output rows below are superseded by
the suite's saved transcripts (screenshot them only if the assessor explicitly
requires pictures of terminals - one capture of the final suite summary is the
recommended maximum). The remaining rows are useful development/spot-check
captures, not gate requirements.

Use actual Windows screenshots when preparing assessment evidence:

| Evidence | Required Screenshot |
| --- | --- |
| One-browser baseline | Browser screenshot showing `/Upload` before navigating to `/EmailSetup`. |
| Email Setup page | Browser screenshot with URL bar visible. |
| Saved secret UI | Browser screenshot after selecting profile, showing blank password field and saved-secret hint. |
| Test connection | Browser screenshot showing status just below the Test connection button. |
| Folder behavior | Browser screenshot showing non-default folder and returned result/status. |
| PDF password collapsed | Browser screenshot showing `Saved PDF passwords` closed by default. |
| Source pagination | Browser screenshot with more than 10 configured sources and page buttons visible. |
| Delete profile | Browser screenshots showing Delete action, inline confirmation/cancel, confirmed deletion, and refreshed source list. |
| Run result pagination | Browser screenshot with more than 10 result candidates and page buttons visible. |
| Mailbox before proof | Browser screenshot showing the source mailbox message or PDF attachment before Stats import. |
| Blob container imported files | Browser screenshot of Azure Portal or Storage Browser showing the configured storage account, container, prefix/ingestion id, and imported PDF blob row after Stats import. |
| Blob terminal proof | PowerShell screenshot showing `m12_email_ingestion_blob_evidence_check.py`, account/container/prefix, blob rows, and `Result: PASSED`. |
| Phase A database proof | PowerShell screenshot showing `m12_email_ingestion_database_evidence_check.py`, DB/server identity, matching `stats_documents` / `transaction_batches` rows, `source_type=email_attachment`, `saved_by_user_id=system-email-automation`, and `Result: PASSED`. |
| App database result proof | Browser screenshot of Documents or Reports showing the database-backed result for the automated email-ingested document. |
| Manual Upload regression | Browser screenshot of `/Upload` from the same Edge session before Email Setup evidence. |
| Import trace logs | Terminal screenshot showing M12 handoff trace log lines for a run/import. |
| Terminal proof | PowerShell screenshot showing the runtime evidence script result and `Result: PASSED`. |
| Evidence suite summary | PowerShell screenshot of `m12_evidence_suite.py` ending with the summary matrix and `Result: PASSED`; keep the generated `m12-evidence-suite-<timestamp>` folder with per-step transcripts alongside the screenshots. |
| Run-history SQL proof | PowerShell screenshot of `m12_email_ingestion_run_history_evidence_check.py` showing run header counts, candidate hash/dedup rows, processed markers, and `Result: PASSED`. |

## Notes

- The mailbox password field must never display the saved password after reload. A blank password field with the saved-secret hint is the expected secure state.
- The evidence script intentionally prints only boolean secret availability and secret references, never secret values.
- If a real mailbox is unavailable during evidence capture, record the provider error as a connectivity issue and keep the UI/API privacy checks as separate pass/fail items.

<!-- M12 End -->

