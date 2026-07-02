<!-- M12 - Email Ingestion Module Start -->
<!-- Defines cloud-hosted mailbox attachment ingestion into Blob-backed file intake. -->

# Module 12 Email Ingestion Module Specification

## Module Summary

Module 12 establishes the **Email Ingestion Module** for the Stats project. It is a standalone reusable source adapter that connects to configured mailbox source profiles, retrieves eligible email attachments, preserves email source metadata, and hands accepted attachments to the existing File Validation and Ingestion Module.

The production direction for the current project is **cloud-hosted mailbox ingestion**:

- M12 runs inside the Azure-hosted Stats runtime, not on a local developer machine.
- Mailboxes are accessed through provider-specific IMAP profiles over SSL.
- Mailbox app passwords and reusable PDF passwords are stored in Azure Key Vault.
- Original attachments are stored through the Azure Blob-backed intake storage provider.
- Password-protected PDFs enter a controlled `password_required` workflow instead of failing invisibly.
- Multiple email source profiles are supported from the same Email Ingestion setup page.

## Architecture Alignment

M12 aligns with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `contracts/documents/README.md`
- `docs/M3-file-validation-module-spec.md`
- `docs/M5-document-parsing-module-spec.md`
- `docs/M9-stats-data-persistence-module-spec.md`
- `docs/M14-cloud-readiness-module-spec.md`
- `infrastructure/cloud/README.md`

The building-block plan defines this module as:

| Field | M12 Direction |
| --- | --- |
| Build order | `12` |
| Module | Email Ingestion Module |
| Type | Standalone reusable module |
| Main responsibility | Retrieve authorized attachments and submit them to file intake |
| Reusable output | Email source adapter and intake contract |

## Current Azure Runtime Assumptions

M12 is designed to use the provisioned Azure cloud-dev resources:

| Resource | M12 Use |
| --- | --- |
| Azure Container App `ca-stats-dev-001` | Hosts the Stats runtime and M12 API/process. |
| Azure Container Registry `acrstatsdev001` | Stores the rebuilt `stats-runtime` image that includes M12. |
| Azure Key Vault `kv-stats-dev-001` | Stores mailbox app passwords, PDF passwords, and future mailbox-source secrets. |
| Azure Container Apps secrets | Runtime secret references for the Container App. |
| Azure Blob Storage | Durable storage for original accepted email attachments. |
| Azure SQL Database `sqldb-stats-dev` | Stores Stats document/workflow results and, when implemented, M12 source profiles/run history. |
| Log Analytics | Captures redacted M12 runtime logs and cloud evidence. |
| Managed identity | Preferred long-term access pattern for Key Vault and Blob Storage. |

No production M12 path may require Outlook Desktop, a local mailbox profile, local scheduled tasks, local files, or a developer workstation.

## Additive Workflow Principle

M12 adds an email-driven intake pathway; it does not replace the existing manual document Upload workflow.

| Workflow | Owner | Behavior |
| --- | --- | --- |
| Manual Upload | Stats Web plus M3/M4/M5/M7/M8/M9 | The existing `/Upload` page remains user-driven. A user uploads a file, reviews validation/extraction results, and controls the save behavior exactly as before. |
| Email Ingestion | M12 plus downstream module APIs | Admin-configured mailbox profiles retrieve eligible PDF attachments and hand accepted files to the existing Blob-backed intake path. |

Implementation and evidence rules:

- M12 changes must not alter `RunProcessingJobAsync`, Upload page controls, manual review behavior, or user-confirmed save behavior.
- Automated email processing may reuse downstream module API contracts, but it must not route through or rewrite the manual Upload UI workflow.
- Evidence-driven tests for M12 must include a manual Upload checkpoint before the Email Setup flow to prove the existing behavior remains available.
- Manual and email pathway failures must remain distinguishable in logs and UI evidence through `source_type`, source profile/run metadata, and correlation/run identifiers.

## Goals

- Provide a standalone Email Ingestion API with health, source-profile, test-connection, dry-run, and run endpoints.
- Support multiple configured mailbox source profiles.
- Support provider-neutral IMAP source profiles, including custom IMAP and common provider presets.
- Keep mailbox credentials outside Git, browser storage, logs, screenshots, and committed config.
- Allow each source profile to define folder, sender filters, subject filters, attachment rules, deduplication policy, and PDF password-handling behavior.
- Retrieve attachment candidates from configured IMAP mailboxes in Azure.
- Filter attachments by extension, MIME type, size, empty-content checks, and duplicate identity before handoff.
- Store original accepted attachments through the Blob-backed intake storage provider.
- Hand retrieved attachments to M3/M4 File Validation and Ingestion API with `source_type=email_attachment`, `source_id`, `idempotency_key`, and source metadata.
- Detect password-protected PDFs before parsing proceeds, and route them to a controlled pending-password workflow.
- Preserve controlled candidate statuses, run summaries, and findings for UI and evidence.
- Redact email subjects and sensitive mailbox metadata by default.
- Run unit/API tests through the container-first module runner after M13.

## Non-Goals

- Using a local desktop email client, local mailbox cache, local scheduled task, or developer machine as part of production ingestion.
- Committing real mailbox credentials, app passwords, mailbox contents, email attachments, PDF passwords, OAuth tokens, or webhook secrets.
- Brute-forcing, guessing, or deriving unknown PDF passwords without an explicit configured source rule.
- Parsing, OCR, transaction extraction, data validation, dashboarding, or reporting. These remain owned by M5, M7, M8, M9, M11.
- Creating new Azure resources without explicit approval. This spec uses existing cloud-dev resources first.
- Production-grade mailbox webhooks. IMAP polling/manual runs are the first production pathway.
- Multi-user permission design beyond admin-managed source profiles for this slice.

## Owner Folder

```text
modules/email-ingestion-module/
```

Module-local unit tests belong under:

```text
tests/unit/email_ingestion_module/
```

## Core Concepts

### Email Source Profile

An email source profile is the saved configuration for one mailbox/folder/rule set.

Required fields:

| Field | Purpose |
| --- | --- |
| `source_id` | Stable identifier used in dedupe keys, run history, and downstream handoff metadata. |
| `display_name` | Human-readable name shown in Stats Web. |
| `provider` | `custom_imap`, `gmail_imap`, `outlook_imap`, `yahoo_imap`, or `synthetic` for tests. |
| `email_address` | Full mailbox address. |
| `enabled` | Whether scheduled/manual runs are allowed. |
| `secret_ref` | Key Vault secret reference for the mailbox app password. |
| `folder` | IMAP folder such as `Inbox` or `Statements`. |
| `connection_settings` | Optional IMAP host, port, and SSL settings for custom providers. |
| `sender_allowlist` | Optional sender filter. |
| `subject_contains` | Optional subject keyword filter. |
| `attachment_policy` | Allowed extensions, MIME types, maximum size. |
| `pdf_password_policy` | How locked PDFs are handled for this source, including reusable password rules. |
| `post_process_policy` | Optional mark-read/move-email behavior after successful handoff. |
| `polling_schedule` | Automatic-ingestion cadence for this profile: `off`, `hourly`, or `daily` with an optional `time_of_day` (UTC). Default `off`. Drives the later scheduled-automation slice; a runtime `last_auto_run_at` tracks the last automatic run. |

One user can configure multiple profiles, for example:

- `personal-inbox`
- `bank-statements`
- `bills-folder`
- `receipt-mailbox`

### IMAP Providers

M12 treats IMAP as a provider-neutral adapter. Preset providers supply known hosts, while custom IMAP profiles store their host, port, and SSL choice in `connection_settings`.

| Provider | Default host |
| --- | --- |
| Custom IMAP | Saved per profile. |
| Gmail | `imap.gmail.com` |
| Outlook / Microsoft 365 | `outlook.office365.com` |
| Yahoo Mail | `imap.mail.yahoo.com` |

The normal mailbox account password must not be used by Stats when a provider requires an app password.

### Attachment Candidate

Each attachment becomes an attachment candidate with:

- source profile ID,
- message ID,
- attachment ID or attachment sequence,
- sender,
- received timestamp,
- redacted subject,
- original filename,
- MIME type,
- size,
- content hash when available,
- Blob/file-intake handoff result,
- findings and status.

## Planned Cloud Workflow

```text
Stats Web Email Setup
  -> M12 source profile saved
  -> mailbox app password stored as Azure Key Vault secret
  -> M12 manual or scheduled run
  -> IMAP SSL mailbox scan
  -> email/attachment candidates normalized
  -> unsupported/duplicate/oversize files skipped
  -> original accepted attachment handed to M3/M4
  -> M3/M4 stores file through Azure Blob-backed intake storage
  -> M5 detects parse-ready vs password-protected PDF
  -> password-required PDFs pause for source rule or user password
  -> unlocked PDFs continue to parse/OCR
  -> M7 extraction
  -> M8 validation
  -> M9 Azure SQL persistence
  -> Stats Web document/report views
```

## Email Ingestion Setup Tab

The existing Email Setup page becomes the M12 control panel.

### Source Profiles List

The first view should show multiple profiles:

| Column | Purpose |
| --- | --- |
| Profile | Display name. |
| Email | Mailbox address. |
| Provider | Mailbox provider. |
| Folder | Folder scanned. |
| Enabled | On/off state. |
| Connection | Connected, needs setup, failed. |
| Last Run | Latest run time and status. |
| Imported | Count from latest run. |
| Issues | Duplicates, skipped files, password-required files, failures. |

Actions:

- Add profile.
- Edit profile.
- Test connection.
- Dry run.
- Run import now.
- Ingest imported run to database (scaffold; process-to-database, not yet governed auto-save).
- Disable profile.
- Delete profile (removes the source row; the referenced mailbox secret is deleted best-effort only when no other profile references the same secret reference, otherwise it is left in the secret provider to rotate/purge separately).
- Rotate app password.

### Profile Settings

Profile edit fields:

- Display name.
- Provider: Custom IMAP, Gmail, Outlook / Microsoft 365, or Yahoo Mail.
- Email address.
- Mailbox app password input for initial setup/rotation only.
- Secret destination/reference.
- Folder to scan.
- Lookback window.
- Sender allowlist.
- Subject keyword filters.
- Allowed attachment types.
- Maximum attachment size.
- Duplicate policy.
- Post-success behavior: leave email unchanged, mark as read, or move to processed folder.
- Automatic ingestion cadence: off, hourly, or daily with a UTC time-of-day (drives the later scheduled-automation slice; default off).
- PDF password handling policy.
- PDF password rules for different bill/document types.

### Password-Protected PDF Queue

The setup tab should expose pending locked PDFs:

| Column | Purpose |
| --- | --- |
| Document | Filename. |
| Source Profile | Which mailbox profile found it. |
| Sender | Redacted or safe sender display. |
| Received | Received timestamp. |
| Status | `password_required`, `password_failed`, `unlocked`, `skipped`. |
| Attempts | Unlock attempt count. |
| Action | Enter password, retry, skip, or save source rule. |

Passwords entered in the UI must not be displayed after submission and must not be logged.

### Run Summary

Each run should show:

- messages scanned,
- attachments found,
- attachments imported,
- skipped attachments,
- duplicates,
- password-required PDFs,
- failed handoffs,
- connection errors,
- link to document status records created from the run.

## API Contract

### Health

`GET /health`

Returns module status, service name, version, provider, and ingestion mode.

### Source Profiles

`GET /api/v1/email-ingestion-sources`

Returns configured source profiles without secret values.

`POST /api/v1/email-ingestion-sources`

Creates a source profile. If a mailbox app password is provided, the backend must store it in the configured secret provider and retain only a secret reference.

`pdf_password_policy.password_rules` accepts zero or more reusable password rules. Each rule has `rule_id`, `display_name`, `password_secret_ref`, optional `sender_contains`, optional `subject_contains`, optional `filename_contains`, and `enabled`. Multiple rules may exist for one mailbox so different bill types can map to different Key Vault secrets.

`PATCH /api/v1/email-ingestion-sources/{source_id}`

Updates safe profile settings or rotates the secret reference.

`DELETE /api/v1/email-ingestion-sources/{source_id}`

Removes a source profile (returns 404 when it does not exist). Deletes the profile row from the configured store. The referenced mailbox secret is then deleted best-effort, but only when no remaining profile references the same secret reference; a shared or undeletable secret remains in the secret provider to be rotated or purged separately (Key Vault deletions are soft-deletes and may need purge/recover before the same secret name is reused).

`POST /api/v1/email-ingestion-sources/{source_id}/test-connection`

Attempts IMAP login and folder access without importing attachments.

### Automated Email Run

`POST /api/v1/email-ingestions/automated-runs`

Input:

| Field | Purpose |
| --- | --- |
| `source_id` | Stable source profile identifier. |
| `mode` | `dry_run` or `handoff`. |
| `lookback` | Optional override for scan window. |
| `max_messages` | Optional run limit. |
| `messages` | Synthetic/provider-normalized messages for tests only. Production runs retrieve messages from IMAP. |

Output:

| Field | Purpose |
| --- | --- |
| `run_id` | Stable identifier for this automated ingestion run. |
| `status` | `completed`, `completed_with_warnings`, `failed`, or `blocked`. |
| `source_id` | Source profile used. |
| `candidates` | Per-attachment status, source metadata, hash, findings, handoff result, and password state when relevant. |
| `summary` | Message, attachment, retrieved, skipped, duplicate, failed, handed-off, and password-required counts. |
| `evaluation` | Run metadata and finding counts for test/evidence reporting. |
| `findings` | Run-level and candidate-level findings. |

### Password Unlock

`POST /api/v1/email-ingestions/documents/{document_id}/password-attempts`

Attempts to unlock a password-protected PDF using a one-time password entered by the user or a configured source rule.

The request must not return, log, or persist the raw password unless the user explicitly saves it as a source-level secret rule.

## Candidate Status Rules

| Condition | Candidate Status |
| --- | --- |
| Supported extension, MIME type, size, and non-empty attachment | `retrieved` |
| Unsupported type, empty attachment, or over size limit | `skipped` |
| Same source/message/attachment/hash already processed | `duplicate` |
| Handoff requested and M3/M4 returns queued | `handed_off` |
| Handoff requested and M3/M4 is unavailable or does not return queued | `failed` |
| PDF is encrypted and no password is available | `password_required` |
| PDF password attempt fails | `password_failed` |
| PDF is unlocked and ready for parsing | `unlocked` |

Run status is:

- `failed` when mailbox connection or handoff failures prevent the run from completing,
- `blocked` when all eligible work is blocked by required PDF passwords,
- `completed_with_warnings` when candidates are skipped, duplicated, or password-required but the run otherwise completes,
- `completed` when all eligible candidates are processed successfully.

## Password-Protected PDF Handling

**Canonical model:** passwords live only in M12. An encrypted PDF is unlocked
*before* Blob, so an unlockable PDF becomes a clean, readable PDF in intake and the
rest of the pipeline needs no password logic - identical to the manual Upload path.
A PDF with no matching saved secret is parked as `password_required` (not handed off)
and surfaced through reporting coverage rather than silently dropped.

Cross-module responsibilities:

| Module | Responsibility |
| --- | --- |
| M12 | Detect encrypted PDFs during retrieval and unlock them in memory using the profile's saved PDF password secrets, then hand off the *decrypted* PDF. If no saved secret opens it, park the attachment as `password_required` and do not hand it off. |
| M3/M4 | Store the accepted (decrypted) file through Blob-backed intake and create the ingestion record. |
| M5-M9 | Process a normal, readable PDF - no password logic. The email path converges with manual Upload at "clean PDF in intake". |
| M11 | Surface parked/excluded documents (`password_required`, `skipped`, `failed`) as source-coverage / review-impact so reported totals stay honest. |
| Stats Web | Configure source-level PDF password rules. (One-time user password entry + retry queue is deferred - see Deferred Items.) |

Password sources:

| Source | Rule |
| --- | --- |
| One-time user entry | Used for a single unlock attempt; do not persist raw password. |
| Source-level secret | Stored in Key Vault/Container Apps secrets and referenced by source profile. |
| Pattern rule | Allowed only when explicitly configured and auditable; do not infer silently. |

Security requirements:

- Never commit PDF passwords.
- Never log PDF passwords.
- Never return PDF passwords from API responses.
- Store reusable passwords as secrets only.
- Allow multiple password rules per source profile, matched by sender, subject, and/or filename keywords.
- Store only `password_secret_ref` values in source profiles; actual reusable passwords remain in Key Vault.
- Audit who supplied a password, when, for which document/source, and whether it succeeded.
- Unlocked PDFs are stored decrypted in Blob under the same access controls as manually uploaded files; the raw password is never persisted. Parked `password_required` files are not handed off.

## Deduplication

M12 must deduplicate at two levels:

| Level | Key |
| --- | --- |
| Run-local | `source_id + message_id + attachment_id + sha256` |
| Persistent/source-level | `source_id + provider_message_id + attachment_id` and/or `sha256` after M9 stores run history |

Duplicate candidates are terminal unless a future explicit reprocess action is added.

## Configuration

Committed defaults live in `modules/email-ingestion-module/config/defaults.env`.

| Variable | Purpose |
| --- | --- |
| `EMAIL_PROVIDER` | Default provider adapter label. Source profiles choose the active provider; `synthetic` remains the safe test default. |
| `EMAIL_INGESTION_MODE` | Runtime mode such as `dry_run` or `handoff`. |
| `FILE_INGESTION_BASE_URL` | M3/M4 API target for accepted attachment handoff. |
| `DOCUMENT_PARSING_BASE_URL` | M5 parse API target for the database-ingest path (process-imported / scheduled ingest). |
| `TRANSACTION_EXTRACTION_BASE_URL` | M7 extraction API target for the database-ingest path. |
| `DATA_VALIDATION_BASE_URL` | M8 validation API target for the database-ingest path. |
| `STATS_DATA_BASE_URL` | M9 Stats Data API target (processing jobs, recognition context, transaction save) for the database-ingest path. |
| `EMAIL_SOURCE_CONFIG_STORE` | Source profile store, initially `azure_sql` or local test fixture. |
| `EMAIL_SECRET_PROVIDER` | Secret provider. Production uses `azure_key_vault`; local/test may use `environment`, `memory`, or SQL-backed encrypted storage. |
| `EMAIL_KEY_VAULT_URL` | Azure Key Vault URL used when `EMAIL_SECRET_PROVIDER=azure_key_vault`. |
| `EMAIL_SECRET_ENCRYPTION_KEY` | Secret key material used only when mailbox/PDF password values are stored by the SQL-backed fallback store. |
| `ALLOWED_ATTACHMENT_EXTENSIONS` | Attachment extension allowlist. |
| `ALLOWED_ATTACHMENT_MIME_TYPES` | Attachment MIME allowlist. |
| `MAX_ATTACHMENT_SIZE_BYTES` | Email attachment size limit before file intake. |
| `DEFAULT_MAILBOX_FOLDER` | Default folder when profile omits one. |
| `DEFAULT_LOOKBACK_HOURS` | Default retrieval window hint for provider adapters. |
| `POLLING_ENABLED` | Enables scheduled polling only when a cloud trigger exists. |
| `REDACT_EMAIL_SUBJECTS` | Redacts subject values in API output by default. |
| `PDF_PASSWORD_SECRET_PREFIX` | Prefix for reusable source-level PDF password secrets. |

Real mailbox credentials belong in Azure Key Vault. Source profile rows store only normalized secret references.

Recommended secret names:

| Secret | Purpose |
| --- | --- |
| `stats-email-{provider}-email-{source_id}` | Optional mailbox username secret when email address is treated as sensitive. |
| `stats-email-{provider}-app-password-{source_id}` | Mailbox app password for a source profile. |
| `stats-pdf-password-{source_id}-{rule_id}` | Optional reusable PDF password secret. |

## Implementation Plan

### Phase 1 - Spec and UI Contract

- Update M12 spec and file inventory.
- Define source profile fields.
- Define Email Setup tab requirements.
- Define cloud-secret and password PDF handling contracts.

### Phase 2 - Source Profile API

- Add source profile models.
- Add list/create/update/test-connection endpoints.
- Store profile metadata without secrets.
- Store/resolve mailbox app passwords through the configured secret boundary.

### Phase 3 - Generic IMAP Adapter

- Implement IMAP SSL connection for common provider presets and custom IMAP profiles.
- List folders and test selected folder.
- Search messages by date/sender/subject.
- Fetch attachment metadata and content.
- Normalize messages into M12 attachment candidates.

### Phase 4 - Blob/File Intake Handoff

- Ensure accepted attachments enter M3/M4 as `source_type=email_attachment`.
- Preserve email metadata in source fields.
- Confirm Blob-backed intake storage is used in cloud.
- Add dry-run and real-handoff evidence.

### Phase 5 - Password-Protected PDF Workflow

- Add encrypted-PDF detection checkpoint. (done)
- Add `password_required` / `password_failed` / `unlocked` statuses. (done)
- Unlock in M12 using saved source-level password secrets before Blob handoff, so the
  decrypted PDF flows through the pipeline like a manual upload. (done)
- Optional source-level password secret rules. (done)
- Deferred: the UI queue for password-required documents and the one-time
  password-attempt endpoint (see Deferred Items under the Completion Plan).

### Phase 6 - Run History and Persistent Deduplication

- Persist source profile run history in Azure SQL.
- Persist candidate status, findings, and dedupe keys.
- Prevent re-import of already processed source attachments.
- Add document status links from run history.

### Phase 7 - Scheduling

- Keep manual runs as the first cloud path.
- Add scheduled polling through Azure Container Apps Job only after explicit approval.
- Capture cloud smoke evidence and redacted logs.

## Completion Plan (Remaining Work)

The build phases above delivered the email-to-Blob adapter (the current acceptance
slice) plus scaffolds for database ingest and scheduling. Remaining work to full
completion, in dependency order:

### C1 - Make the manual email-to-database path run + close cheap gaps (done)

- Wire the pipeline base URLs (`DOCUMENT_PARSING_BASE_URL`,
  `TRANSACTION_EXTRACTION_BASE_URL`, `DATA_VALIDATION_BASE_URL`, `STATS_DATA_BASE_URL`)
  into the M12 runtime. (done - container start script derives them from the module
  port vars; committed `defaults.env` fallbacks; registered in `stats.runtime.json`.)
- Execute `post_process_policy` (mark-as-read / move-to-folder) after successful
  handoff so scheduled polling does not rescan the same messages. (done -
  `imap_service.apply_post_process`, invoked only for real IMAP non-dry runs that
  handed files off; failures are a warning finding, not a run failure; default no-op.)
- Keep the container unit suite green. (Codex runs the suite.)

### C2 - Trusted automated persistence + reporting (M12 side verified)

**Verified against M9:** `_classification_confirmation_allowed` requires
`classification_human_confirmed = true` **and** `classification_source =
user_confirmed_*` **and** `classification_confirmation_mode = upload_transaction_review`;
otherwise M9 creates **pending** recognition suggestions + `review_items` and does not
activate labels or learn merchants. The M12 automated save (`PipelineClients.save`)
sends only the M8 `validation_result` + system identities and sets none of those
markers, so the automated path is governed-by-default. Locked by
`tests/unit/email_ingestion_module/test_pipeline_save_governance.py`. Excluded/parked
candidates (`password_required`, `skipped`, `failed`) are already persisted per run in
`email_ingestion_run_candidates`, so the coverage data exists. **Remaining is an M11
deliverable:** the `review-items` / source-coverage read surface (M11 spec lists it as
needed but not yet implemented).


M12 does **not** own classification or governance (see Non-Goals). The governance is
already specified and implemented downstream: M8 marks records for review when labels
are unknown, out-of-vocabulary, pending, ambiguous, or below the confidence threshold
and emits `review_items` + `document_review_status` (M8 spec, "Review items" and
"Mark records for review"); M9 treats the Upload review/accept/save as the
human-confirmation event that activates labels and bypasses the `/Admin/Classifications`
pending path, and learns merchants only from `classification_human_confirmed = true`
(M9 spec, "Recognition Label Suggestions And Synchronization"). So the automated save
becomes governed simply by taking the **unreviewed** route, not by adding a new engine.

- **Ensure the automated save flows the unreviewed path.** The orchestrator must not
  set `classification_human_confirmed` / `classification_confirmed_by_user_id`, and
  must pass the `active_recognition_context` it already fetches. Then M8 flags review
  and M9 writes **pending** recognition suggestions + `review_items` for unknown /
  low-confidence / out-of-vocabulary rows, while confident known-vocabulary rows save
  as transactions. Merchant learning stays uncontaminated (it requires human
  confirmation). This promotes next-items' *Post-MVP Admin Recognition Workflow For
  Automated Ingestion*.
- **Verify, don't rebuild:** confirm `_classification_activation_allowed` keys on
  human-confirmation / known vocabulary and that the automated `transactions/batches`
  save does not leak a confirmed flag. Only if it does is a code fix needed.
- **Surface saved-vs-review** in the run/UI (`ProcessImportedResult` already carries
  `saved_record_count` + `review_item_count`).
- **Reporting coverage is an M11 deliverable.** M12 persists a lightweight
  pending/excluded record for `password_required` / `skipped` / `failed` (documents
  seen but not ingested); M11 delivers the source-coverage / review-backlog surface it
  already specs, including the `GET /api/v1/review-items` read API it lists as needed
  but not yet implemented (M11 spec).

### C3 - Unattended trigger infrastructure

- Repo scaffold is built:
  `infrastructure/cloud/deploy-m12-scheduled-ingestion-containerapp-job.ps1`
  creates/updates the scheduled Azure Container Apps Job,
  `/app/run-m12-scheduled-ingestion.sh` performs the internal-key POST, and the
  scheduled endpoint uses an app-side non-blocking lock.
- Remaining live-infra step: run the deployment script with the actual Stats Web
  URL, registry identity resource id, image tag, and Key Vault secret in Azure.
- Optional later: Event Grid on Blob-Created to decouple the intake-to-database half.

### C4 - Cloud evidence and acceptance

- Slice 1 cloud smoke: mailbox PDF visible in Blob before/after, redacted logs.
- Database-ingest cloud proof: Azure SQL rows from a governed run
  (`source_type=email_attachment`, system `saved_by_user_id`, and any review-routed
  rows).
- Update evidence and tick the acceptance criteria per slice.

### Deferred Items

- One-time user PDF password entry: the
  `POST /api/v1/email-ingestions/documents/{document_id}/password-attempts` endpoint
  and the Password-Protected PDF queue UI. Needed only if admins must unlock PDFs that
  have no matching saved secret; the endpoint contract is already defined in the API
  Contract section above.

## Testing

M12 testing is split by implementation boundary so the evidence does not overstate
the current build. The current evidence set is named:

```text
M12 Email Ingestion Evidence - Manual Import, Blob Handoff, and Database Processing
```

The current acceptance boundary is:

1. **Manual Upload regression remains unchanged.** `/Upload` must still load and
   remain the user-driven upload/review/save workflow.
2. **M12 email import reaches Blob-backed intake.** `/EmailSetup` must prove the
   configured mailbox profile can retrieve eligible PDF attachments and hand them to
   M3/M4 intake, where the accepted files are visible in Blob storage.
3. **Phase A database-ingest scaffold is verified after import.** The
   "Ingest to database" action processes the exact imported run into M9 through
   the existing module APIs. This is currently process-to-database using a system
   identity. It is not yet the final governed auto-save pathway.
4. **Full unattended automation remains future acceptance.** Container Apps Job,
   Event Grid/Durable orchestration, and recognition-governed persistence are not
   accepted as complete until their infrastructure and governance checks exist.

Unit/API tests must verify:

- Health endpoint reports provider and mode.
- Source profiles are returned without secret values.
- IMAP adapter can be mocked for successful connection, failed auth, missing folder, and retrieval errors.
- Allowed PDF attachment becomes a retrieved candidate.
- Messages without attachments create an informational finding.
- Unsupported attachments are skipped with explicit findings.
- Duplicate attachments are terminal for that run/source.
- File-intake handoff maps a queued M3/M4 response to `handed_off`.
- Password-protected PDF candidates become `password_required`.
- Failed unlock attempts return `password_failed` without logging the password.
- Source-level password secret references are returned, but secret values are never returned.
- Source profile deletion removes the selected source from the configured mailbox
  list and returns 404 for a missing source without exposing or deleting raw secret
  values through the UI/API response.
- `process_imported_run` uses the explicit import `run_id`, rejects a run id from
  another source, and does not reprocess an ingestion already marked processed.
- `process_imported_run` reports successful database-ingest counts (`processed`,
  `succeeded`, saved records, review items), `already_processed` retry behavior,
  `no_imported_files`, and configuration failures such as missing
  `STATS_INTERNAL_API_KEY` with `failed_count = 1`.
- Scheduled ingestion only processes the run it just imported; if import fails or
  produces no run id, it must not fall back to an older latest run.
- Scheduled ingestion tests include disabled/off-cadence profiles, due profiles,
  exact returned `run_id` propagation, failed imports, and the guarantee that failed
  imports do not advance `last_auto_run_at`.
- File-intake readback `GET /api/v1/ingestions/{id}/content` rejects missing or
  wrong `X-Stats-Internal-Key` values and streams stored bytes only to an internal
  caller.

Test prerequisites:

- `STATS_INTERNAL_API_KEY` must be configured for process-imported and scheduled
  database-ingest tests.
- `STATS_TESTDATA_DIR` must point to a folder with top-level PDF files for
  file-intake real-PDF unit tests.
- The selected email source profile must already have its mailbox app password
  saved behind `secret_ref`, so the UI password field can remain blank for later
  test connection/import checks.
- PDF password handling is tested inside M12 up to unlock/handoff using configured
  saved PDF password rules. Full locked-PDF parse/extraction/database evidence is
  only in scope after the M3/M4/M5 path accepts the unlocked/decrypted file for that
  run; one-time password queue/retry remains deferred.

Current container/cloud evidence should verify:

- Evidence execution follows the failure-stop rule: after each step, verify the
  expected result before continuing. If an unexpected failure occurs, stop the test
  loop, inspect UI/log/API/database evidence, report the failed step, expected
  result, actual result, likely cause, recommended fix, and whether continuing would
  risk bad evidence or data mutation. Resume only after the failure is understood or
  the user approves the next action.
- Container App starts with M12 health check passing.
- One visible Edge browser session is used for the whole walkthrough.
- `/Upload` is captured first as the unchanged manual-flow checkpoint.
- `/EmailSetup` is captured with the configured source profile selected.
- Configured mailboxes show `Select` and `Delete` row actions; Delete uses an
  inline confirmation before removing the selected profile from the table.
- Test connection either succeeds or shows a specific actionable error, such as
  saved-secret decrypt failure or folder-name mismatch. Failed evidence is valid
  only when the failure reason and corrective action are captured.
- Dry run lists redacted candidate metadata and shows sender/subject filters in
  the result summary.
- Run import stores accepted PDF attachments through Blob-backed intake.
- Blob evidence includes a before/after proof: the mailbox PDF exists before the
  run, and the imported PDF appears under the configured Blob intake prefix or
  ingestion id after the run.
- "Ingest to database" evidence includes current-step/status proof in the UI and
  Azure SQL proof from inside `stats-runtime`: database/server identity, query text,
  matching processing job/document/transaction rows, `source_type=email_attachment`,
  `saved_by_user_id=system-email-automation`, and any review-item counts emitted by
  M8/M9.
- Process-imported failure evidence, when intentionally exercised, captures the
  visible reason and result counts (`failed_count = 1`) for setup/configuration
  failures such as a missing internal service key.
- Password-required or password-failed candidates are visible when a locked PDF
  cannot be opened by configured saved PDF password rules. The later one-time
  password queue/retry workflow is not part of the current M12 acceptance boundary.
- Logs do not contain mailbox app passwords, PDF passwords, full email bodies, or raw attachment contents.

### Evidence-Driven Test Cases

The current M12 evidence-driven test matrix is maintained in:

```text
tests/scripts/M12-EmailIngestion/m12-email-ingestion-evidence-test-cases-2026-06-29.md
```

The repeatable runtime evidence check is maintained in:

```text
tests/scripts/M12-EmailIngestion/m12_email_ingestion_runtime_evidence_check.py
```

The repeatable Blob container evidence check is maintained in:

```text
tests/scripts/M12-EmailIngestion/m12_email_ingestion_blob_evidence_check.py
```

This evidence set includes the M12 behavior tightened during the 2026-06-29 to
2026-07-01 build loop:

- mailbox app password is centrally saved behind `secret_ref` and never returned to the browser,
- Test connection can use the saved secret with the password field left blank,
- typed mailbox folder is sent to connection tests and manual runs,
- IMAP port and SSL controls are hidden from users and inferred by the runtime,
- Saved PDF passwords are collapsed by default,
- source profile action text is `Select`,
- source profile delete action and inline confirmation are covered by UI/API
  evidence,
- configured mailboxes and run results are paginated at 10 rows per page,
- non-PDF email assets are ignored before candidate validation so only PDF attachments enter the run results,
- run message limits are explicit and can be disabled with `max_messages = 0`,
- real import evidence includes terminal Blob listing plus a browser screenshot of
  the imported blob row in the configured container,
- database-ingest scaffold evidence proves the persisted rows in Azure SQL without
  claiming final governed auto-save,
- scheduled automation unit evidence proves stale latest runs are not processed when
  import fails and `last_auto_run_at` is not advanced,
- process-imported unit evidence proves success, already-processed retry,
  no-imported-files, and configuration-failure result shapes.

Official module acceptance after M13 uses:

```powershell
.\tests\scripts\regression\run_module_unit_tests.ps1
```

## Acceptance Criteria

M12 is complete for the current email-to-Blob intake slice when:

- `modules/email-ingestion-module/` contains a standalone FastAPI runtime.
- `/health` returns healthy module metadata.
- Stats Web Email Setup supports multiple email source profiles.
- IMAP source profiles can be created, selected, tested, disabled, updated, deleted,
  and run.
- Mailbox app passwords and reusable PDF passwords are stored only in the configured secret provider.
- Manual dry run retrieves redacted candidate metadata from the configured mailbox.
- Manual import run sends valid attachments to M3/M4 with email source metadata.
- Original accepted files are stored in Blob-backed intake storage in cloud-dev.
- Evidence includes a Blob container screenshot showing imported email PDFs under the configured intake prefix or ingestion id.
- Evidence includes Azure SQL proof for the process-to-database scaffold when the
  "Ingest to database" action is in scope for the run.
- Unsupported, empty, oversized, duplicate, and failed candidates do not proceed.
- Locked PDFs are unlocked only by configured saved PDF password rules or are
  reported as password-related candidates instead of silently failing.
- Run summaries and findings are visible in Stats Web.
- Unit and contract tests pass.
- Cloud smoke evidence confirms M12 runs in Azure Container Apps without local-machine dependency.

The later unattended automation slice is accepted only after:

- scheduled import does not process stale runs when import fails and does not
  advance `last_auto_run_at` for failed/no-run-id imports,
- Container Apps Job/Event Grid/Durable or equivalent trigger infrastructure exists,
- the automated persistence policy gates unreviewed data through recognition
  governance instead of plain process-to-database,
- database proof shows the automated provenance and any review-routed rows.

<!-- M12 End -->
