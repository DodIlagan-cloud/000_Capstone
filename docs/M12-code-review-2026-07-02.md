# M12 Email Ingestion Module — Code Review (2026-07-02)

Scope: all of `modules/email-ingestion-module/app` (config, routes, models, services, pipeline) plus `config/defaults.env` and `requirements.txt`. ~3,700 lines.

Overall: the module is well-structured and unusually deliberate about security (TLS-required IMAP, SSRF host guard, placeholder-secret startup guard, `hmac.compare_digest`, secrets excluded from serialization, injectable collaborators for tests). The findings below are ordered by severity.

---

## High

### H1. Unwrapped IMAP/socket exceptions turn common failures into 500s
`imap_service.py` only raises `ImapProviderError` for its own checks. But the most common failures raise other types that no caller catches:

- `mailbox.login(...)` raises `imaplib.IMAP4.error` on a wrong/expired app password (`test_connection` line 46, `fetch_messages` line 57, `apply_post_process` line 102).
- `imaplib.IMAP4_SSL(host, port)` in `_connect` (line 171) raises `ConnectionRefusedError`, `TimeoutError`, `ssl.SSLError`, etc. for unreachable hosts / bad ports.

Callers (`routes/sources.py:88`, `ingestion_service.py:76`, `ingestion_service.py:304`) catch `ImapProviderError` only. Result: a wrong password on "Test connection" returns HTTP 500 instead of a `failed` status; in the post-process block an `imaplib` error after successful handoffs fails the whole request. Wrap the bodies of `test_connection` / `fetch_messages` / `apply_post_process` (or `_connect` + login) and re-raise as `ImapProviderError`.

### H2. No socket timeout on IMAP connections
`imaplib.IMAP4_SSL(host, port)` is created with no `timeout` (`imap_service.py:171`). Default is no timeout, so a black-holed host hangs the request thread (and a scheduled tick) indefinitely — and the scheduler lock (see M5) stays held. Pass `timeout=` (e.g. 30s).

### H3. Cross-run dedup key is built from unstable IMAP sequence numbers
`fetch_messages` searches without `UID`, so `message_id` is an IMAP *sequence number* (`imap_service.py:66-80`), and `attachment_id` is a MIME-walk index. The dedup key is `source_id:message_id:attachment_id:sha256` (`ingestion_service.py:130`). Sequence numbers shift whenever messages are added/deleted/moved, so the same attachment gets a new dedup key and `is_attachment_already_imported` misses → re-import duplicates. (Post-process "move to folder" mitigates this only when configured; the default policy is a no-op.) Use IMAP UIDs (`mailbox.uid('search'/'fetch', ...)`) or key on `internet_message_id + sha256` instead.

### H4. `received_after` / `received_before` / `DEFAULT_LOOKBACK_HOURS` are silently ignored
`RetrievalRequest` accepts `received_after`/`received_before` (`models/ingestion.py:196-197`) and config defines `DEFAULT_LOOKBACK_HOURS`, but `fetch_messages` never applies a `SINCE`/`BEFORE` search criterion — every run scans the whole folder (sender/subject narrowed at best) and takes the newest N. API fields that are accepted but ignored are a contract trap, and full-mailbox scans get slower forever. Add `SINCE` from `received_after`-or-lookback, or reject the unsupported fields.

---

## Medium

### M1. `ACCESS_TOKEN_ALGORITHM` is checked but not used for signing
`_decode_access_token` compares the token header's `alg` to the configured algorithm (`auth_service.py:72`) but always computes the signature with `hashlib.sha256` (line 75-79). Setting `ACCESS_TOKEN_ALGORITHM=HS512` (in step with the identity module) would silently reject every token. Either map the setting to the digest or hard-pin `HS256` and validate that at startup.

### M2. `_imap_endpoint` port/SSL inference is surprising
`imap_service.py:202-210`: if `imap_host` contains one colon (`host:port`), the embedded port silently overrides `imap_port`, and `use_ssl` is inferred as `port != 143` — the profile's `use_ssl` flag is ignored on that path, and any non-143 port is presumed SSL. IPv6 literals (multiple colons) fall through to the un-split branch and then fail to connect. Prefer rejecting `host:port` input or parsing it explicitly with validation, and honor `use_ssl` consistently.

### M3. SSRF guard: check/use race and allowlist semantics
`_assert_host_allowed` resolves the host (`imap_service.py:186`) and then `IMAP4_SSL` resolves it *again* — a DNS-rebinding window between check and connect. Also, the comment says "an explicit allowlist always wins," but an allowlisted host that resolves privately is still blocked (private-range check runs regardless, lines 183-199). Minor, but either fix the comment or short-circuit after an allowlist match; for rebinding, connect to the vetted IP or accept and document the residual risk.

### M4. `POST /email-ingestion-sources` silently overwrites an existing profile
`create_source_profile` derives `source_id` from display name + email local part and upserts (in-memory dict assignment / SQL MERGE, `source_profile_service.py:41-68`). Re-creating with the same name replaces the existing profile (and can re-point its `secret_ref`) with no 409. Return a conflict or generate unique IDs.

### M5. Scheduler lock is per-process only; schedule advance on failed ingest
`_scheduler_lock` is a `threading.Lock` (`scheduler.py:24`) — it does not protect against multiple uvicorn workers or >1 job replicas. Fine for a single-replica Container Apps Job, but worth an explicit guard (SQL app lock) or a documented single-replica constraint. Also `mark(...)` runs even when ingest fails (`scheduler.py:93-94`), so a failed *ingest* isn't retried until the next cadence window, while a failed *import* retries every tick with no backoff — asymmetric and worth a comment or a retry cap.

### M6. `DATABASE_SCHEMA` setting is dead
`settings.database_schema` (`config.py:137`) is never referenced; all SQL hardcodes `dbo.` (`secret_service.py`, `source_profile_service.py`, `run_history_service.py`). Either use it or delete it — a config knob that does nothing is a deployment landmine.

### M7. `httpx.Client` never closed
`PipelineClients` creates an `httpx.Client` (`clients.py:41`) and `process_imported_run` builds a fresh instance per call (`pipeline_runner.py:49`) with no `close()`. Connections leak per manual click / scheduled tick. Use a context manager or module-level client.

### M8. Post-process Message-ID search is unquoted
`apply_post_process` passes the raw `<...>` Message-ID to `mailbox.search` (`imap_service.py:110`). IDs with spaces/parens/quotes will produce a malformed search (and per H1, an uncaught `imaplib` error). Reuse `_imap_quote`.

---

## Low

- `config.py:103` — invalid `API_PORT` silently becomes `0`; `_parse_int` swallowing `ValueError` for required settings hides typos. Consider failing fast.
- `schedule_rules.parse_time_of_day` clamps `"25:99"` to `23:59` silently; reject invalid input at the API layer instead (`PollingSchedule.time_of_day` has no validator).
- `ingestion_service.py:597` — handoff timeout of 10s may be tight for a 25 MB attachment upload; the pipeline uses 120s.
- `_message_exceeds_fetch_limit` costs one extra IMAP round trip per message; fetch `RFC822.SIZE` in the search/fetch batch if this gets slow.
- `source_profile_service._row_to_profile` — `EmailProvider(row.provider)` raises on unknown DB values → a single bad row 500s the whole list endpoint.
- `routes/sources.py:68` — the saved secret is resolved before checking `supports_imap_provider`; harmless, but reorder to avoid pointless Key Vault/SQL reads.
- `pipeline_runner.py:52-59` — the config-error result uses `processed_count=1, filename=""` as a placeholder; a dedicated error field would be cleaner for the UI.
- Deleting a profile orphans its secret (documented in the docstring) — consider a best-effort delete when the store supports it.
- `secret_service._fernet` derives the key as unsalted SHA-256 of the shared secret; fine for this threat model, but rotation invalidates all rows at once — the `SECRET_UNREADABLE_MESSAGE` path handles it, just make sure ops docs mention it.
- Connection-string translation (`_connection_string`) is copy-pasted in three services; extract a shared helper.

## Duplication worth consolidating
`_connection_string` / `_connect_sql` appear in `secret_service`, `source_profile_service`, and `run_history_service`; `_use_azure_sql` twice. One `app/services/sql.py` helper would remove ~90 lines and keep the ODBC keyword mapping in one place.

---

## Remediation (2026-07-02)

All findings addressed in the same-day fix pass:

- **H1** — `imap_service` now wraps `test_connection`, `fetch_messages`, and `apply_post_process` in an `_imap_errors` context manager that converts `imaplib.IMAP4.error` and `OSError` (timeouts, refused connections, TLS failures) into `ImapProviderError` with a bounded, secret-free message.
- **H2** — IMAP connections use `timeout=IMAP_TIMEOUT_SECONDS` (new setting, default 30s).
- **H3** — Retrieval switched to `UID SEARCH`/`UID FETCH`, and the cross-run dedup key is now `source_id : (internet_message_id or message_id) : (sha256 or attachment_id:filename)`. *Migration note:* previously persisted dedup keys use the old sequence-number format, so the first run after deploying may re-import attachments whose old keys no longer match; subsequent runs dedup correctly.
- **H4** — Runs now apply `SINCE`/`BEFORE` from `received_after`/`received_before`, defaulting the lower bound to `DEFAULT_LOOKBACK_HOURS` (0 disables). Falls back to date-only, then `ALL`, if the server rejects the narrowed search. *Behavior change:* manual runs now only see mail from the last 24h by default.
- **M1** — `ACCESS_TOKEN_ALGORITHM` now maps to the matching HMAC digest (HS256/384/512) and is validated at startup.
- **M2** — `host:port` parsing honors the profile's `use_ssl` flag, supports bracketed IPv6 (`[::1]:993`), and keeps the port-143-is-plaintext guard.
- **M3** — Allowlisted hosts now short-circuit the private-range block (matching the documented "allowlist wins" behavior); the DNS check/connect double-resolution is documented as accepted residual risk.
- **M4** — `POST /email-ingestion-sources` returns 409 for an existing `source_id` (frontend uses PATCH for updates, so this is safe).
- **M5** — Scheduler lock scope (single-replica constraint) and the advance-on-failed-ingest tradeoff are now documented in code.
- **M6 + duplication** — New `app/services/sql_store.py` centralizes the ODBC connection-string translation and schema-qualifies every table via the (startup-validated) `DATABASE_SCHEMA` setting; the three per-service copies were removed.
- **M7** — `PipelineClients.close()` added; `process_imported_run` closes clients it created in a `try/finally`.
- **M8** — Post-process Message-ID searches are quoted via `_imap_quote` and use UID commands.
- **Lows** — required int settings fail fast (`_require_int`); `PollingSchedule.time_of_day` has a pydantic validator (422 on bad input); handoff timeout is configurable (`HANDOFF_TIMEOUT_SECONDS`, default 60s); bad SQL profile rows are skipped with a warning instead of failing the list; test-connection checks provider support before resolving the secret; `ProcessImportedResult` gained a run-level `error` field; deleting a profile best-effort deletes its mailbox secret; the Fernet key-rotation implication is documented.

New regression tests: wrapped login failures (H1), RFC 3501 date criteria (H4), dedup across changing sequence ids (H3), 409 on duplicate create (M4), invalid `time_of_day` rejection. Existing test fakes updated for the new `fetch_messages` keyword args and UID-based size probe.

---

## Follow-up: external (codex) review remediation (2026-07-02)

1. **Test collection SyntaxError (blocker)** — `test_ingestion_service.py` line 1227 had a truncated statement (introduced during the fix pass by an append through a stale file mount). The tail of `test_sender_or_subject_filters_keep_sender_only_match` was restored verbatim; the file collects again and all surrounding tests are intact.
2. **5-minute proxy timeout on the scheduled job path (high)** — the Stats Web proxy now uses a 55-minute `HttpClient` timeout for `email-ingestions/scheduled-runs`, `process-imported`, and `automated-runs` (matching the job's replica timeout) while keeping 5 minutes for all other routes (`Program.cs`, `IsLongRunningEmailIngestionRequest`). The job script already honors `M12_SCHEDULED_RUN_TIMEOUT_SECONDS=3300` from the deploy script, so the whole chain now supports a long real run. (Running the scheduler in-process in the job container was considered, but the job image only receives the minimal env; the proxy-timeout fix keeps a single configuration source in the main app.)
3. **Failed scheduled ingest left files unprocessed forever (high)** — new `run_history_service.list_unprocessed_import_run_ids()` (memory + SQL) finds runs whose handed-off attachments never reached the database; each scheduler tick now retries those runs (oldest first, bounded, injectable as `pending_runs`) after ingesting the new import. Processed-marker idempotency prevents double saves. Covered by `test_run_due_profiles_retries_unprocessed_earlier_runs`.
4. **Deploy script pulled the internal key value locally (medium)** — `deploy-m12-scheduled-ingestion-containerapp-job.ps1` now resolves only the secret's Key Vault URI and binds it as `keyvaultref:...,identityref:...` so the job's user-assigned managed identity reads the value at runtime; the secret never transits the operator session or CLI arguments. The identity needs get-secret access (RBAC `Key Vault Secrets User`) on the vault.

### Second external review pass (P1-P3)

- **P1: locked-PDF hash provenance** — candidate and run-history records now store the hash of the content actually handed to intake (`sha256` = decrypted bytes for rule-unlocked PDFs), with the encrypted-source hash preserved in a new `original_sha256` field (model + SQL column). `pipeline_runner` therefore propagates the hash that matches the stored bytes into Stats Data and parsing. The dedup key intentionally stays on the original mailbox content, since that is what a re-import would produce. Regression assertions added to `test_unlocked_pdf_is_handed_off_with_decrypted_content`.
- **P2: silent oversized-message drops** — `fetch_messages` now reports messages dropped by the pre-fetch RFC822-size guard via a `skipped_messages` out-list, and the run adds a warning finding `EMAIL_MESSAGE_FETCH_SKIPPED_TOO_LARGE` with the message size and limit, so a small PDF inside a large MIME email no longer disappears invisibly. Covered by `test_oversized_message_skip_is_reported_to_caller`.
- **P3: `password_failed_count` SQL evidence column** — added to the `email_ingestion_runs` migration (CREATE + idempotent `ALTER` guard for existing databases) and written by `run_history_service`. The candidates table similarly gains `original_sha256`. **Deploy note:** re-run `email_ingestion_runs.sql` against the dev database before deploying this code — the MERGE/INSERT now reference both new columns.

### Third external review pass

1. **Shared mailbox secret deleted with profile (P1)** — profile deletion now removes the mailbox secret only when no remaining profile references the same `secret_ref` (`_delete_secret_if_unreferenced`); a shared or uncheckable reference keeps the secret (safe default, logged). The module spec's two delete-profile statements were updated to describe the reference-counted best-effort delete and the Key Vault soft-delete caveat, so code and spec agree again. Covered by `test_delete_profile_keeps_secret_shared_by_another_profile`.
2. **Scheduled-run timeout drift (P2)** — `azure-container-apps.env.example` now sets `M12_SCHEDULED_RUN_TIMEOUT_SECONDS=3300` with a comment tying it to the job replica timeout and the 55-minute proxy allowance, so configuring from the example no longer reintroduces the 5-minute curl cutoff.
3. **Diff hygiene (P3)** — removed the stray blank line at the end of `config.py`. The LF→CRLF warnings come from the repository's line-ending normalization on this workstation (`core.autocrlf`), not from content changes; `git add --renormalize .` or committing as-is with autocrlf enabled keeps the diff clean.

### Fourth external review pass

1. **Blob `content_reference` not carried into the database ingest (P1)** — `pipeline_runner` now sets `PipelineRunRequest(storage_reference=candidate.handoff_content_reference)`, which M9 persists into `stats_documents.storage_reference`, so the database row traces back to the imported Blob object. Asserted in `test_process_imported_runs_pipeline_and_saves`. Documents ingested before this fix have an empty `storage_reference`; the evidence script prints a NOTE for those rows.
2. **`DATABASE_SCHEMA` half-implemented (P2)** — documented `dbo` as required for M12: schema notes added to the `email_ingestion_runs.sql` migration header, the `DATABASE_SCHEMA` entry in `azure-container-apps.env.example`, and `sql_store.qualified()`. The runtime honors the setting, but the migrations create dbo objects only, so changing it requires editing the migrations too.
3. **Database evidence under-proves the workflow (P3)** — `m12_email_ingestion_database_evidence_check.py` now also proves: `stats_documents.storage_reference` (Blob linkage), a completed `document_processing_jobs` row with its parse/extraction/validation ids (fails if absent or never completed), and `review_items` rows/counts for the saved document (zero is valid and printed). The evidence test-cases doc's Phase A section was updated to match.

### Fifth external review pass (evidence-gate strictness)

1. **Suite could PASS with core proof skipped** — the suite now has an explicit acceptance gate: the core proofs (unit, runtime, run_history, blob, database, visual) must all run and pass; any skipped core step (missing handed-off run, no `az login`, no visual dir, or an explicit `--skip-*`) downgrades the verdict to `Result: INCOMPLETE` with exit code 2. `--prep` opts into the old diagnostic behavior and is stamped into the summary (`Mode: prep`) so a prep transcript cannot pass as acceptance evidence.
2. **Empty `storage_reference` accepted** — the database check now fails by default when the matched document lacks Blob linkage; `--allow-legacy-storage-reference` (also plumbed through the suite) tolerates documents ingested before the fix, printing an explicit legacy note instead.
3. **Sensitive transaction values printed** — the transaction proof no longer selects or prints descriptions, amounts, currencies, directions, or dates; it prints identifiers (`transaction_id`, `document_id`, `batch_id`), quality/review status, and a matching-count total, which is sufficient for traceability.
4. **Screenshots outside the gate** — new `visual` suite step: `--visual-evidence-dir` must contain the required run-bound screenshots plus `visual-evidence-manifest.json`; coverage and attestation are recorded into `visual.txt`. Absent or invalid visual evidence fails/downgrades the verdict, so the visual proof set is now part of the pass/fail gate. The evidence test-cases doc documents the acceptance gate, the visual manifest, and prep mode.
5. **(follow-up) Visual gate checked count, not coverage** — the visual step now matches each required proof by manifest `proof_key` (`mailbox-before`, `blob-after`, `documents-view`); any required proof with no matching item fails the step and is named in the summary, and `visual.txt` records per-proof coverage plus undeclared extras. Unrelated screenshots can no longer satisfy the gate. The evidence doc gained the naming table and example file set. Optional extras (`run-status`, `mailbox-after`, `db-proof`) are accepted but not required. (Subsequently hardened further with a JSON attestation manifest and anti-synthetic filename checks.)

### Visual evidence refactor: before/after data-state model (2026-07-02)

The screenshot gate was restructured around state transitions of the acted-upon data. Screenshots are now required only where the state lives on a surface the suite cannot query: `mailbox-before` (PDF in the inbox before import), `blob-after` (blob row after import), `documents-view` (app result after database ingest) — three instead of five. Machine-queryable states (run history, blob listing, SQL rows) are proven by transcripts; `run-status`, `mailbox-after`, and `db-proof` became optional extras. New integrity mechanics: the manifest must bind the whole set to one run (`run_id` checked against the discovered run, `subject_file` checked against that run's candidates, optional `subject_sha256` against the recorded content hash), and each capture's sha256 is recorded in `visual.txt` as a permanent text anchor. This is simultaneously stronger (proves the SAME PDF traveled mailbox → Blob → database → app) and cheaper (fewer captures; no screenshots of text that transcripts already prove; reviews stay text-only). The anti-synthetic manifest attestation is preserved, now with per-proof allowed capture methods.

### Cloud evidence target (2026-07-02)

The evidence suite and its checks gained `--target cloud` so the acceptance run can prove the DEPLOYED Azure Container Apps runtime instead of the local container: all API calls go through the Stats Web public ingress (proxy) with the CSRF header on POSTs; the internal key comes from the operator's shell (`STATS_INTERNAL_API_KEY`) since there is no `docker exec` into a replica; the run-history and database SQL proofs execute locally against Azure SQL (requires local pyodbc + ODBC Driver 18, `AZURE_SQL_CONNECTIONSTRING`, and a workstation SQL firewall rule — the same access pattern used for cloud-dev migrations); Blob proof is unchanged (local az CLI). Cloud liveness is proven by the authenticated sources call through the ingress (M12 `/health` is not proxied), and the in-replica secret probe is replaced by the API-level saved-secret test-connection proof. The evidence doc gained a "Cloud Evidence Run" section with prerequisites and the requirement that visual captures show the cloud URL bar. The scheduled-tick proof remains `az containerapp job start` + execution log.
