<!-- M12 - Email Ingestion Module Start -->
<!-- End-to-end automation design: mailbox -> Azure SQL with no human in the loop. -->

# M12 Email-to-Database Automation Plan (Phase 7/8)

## Status

Decision record and implementation plan for making the Email Ingestion Module run
**automatically from mailbox to database**. The manual *Run import* / *Dry run*
controls on the Email Setup page stay as an operator override; this plan adds the
unattended pathway that is the module's true purpose.

## Additive / No-Regression Principle

There are **two independent workflows**, and this plan only adds the second:

1. **Existing manual Upload flow (unchanged).** Browser upload -> Stats Web
   `RunProcessingJobAsync` -> M5 -> M7 -> M8 -> stops at validation
   ("Review the results before saving") -> user reviews -> user-confirmed save to M9.
   Its code, behaviour, screens, and evidence stay exactly as they are today.
2. **New automated email flow (additive).** Mailbox -> M12 -> Blob intake ->
   automated processing -> M5 -> M7 -> M8 -> M9 persistence. The current Phase A
   code supports manual process-to-database from imported email files; the final
   unattended pathway must add recognition-governed persistence before it can be
   called governed auto-save.

Hard rules for this work:

- **Do not modify** `RunProcessingJobAsync` or the Upload page behaviour. The
  automated orchestrator reuses the **module API contracts** (the stable
  `/api/v1/parses`, `/api/v1/extractions`, `/api/v1/validations`, and M9 persistence
  endpoints) — **not** the existing C# orchestration code.
- The future **governed auto-save** is automated-path only. The manual flow keeps
  its human-reviewed save; the automated flow never changes how a manually uploaded
  document is reviewed or saved. Until the governance gate exists, evidence must
  label database ingestion as a Phase A process-to-database scaffold.
- Existing Upload unit/integration tests and evidence must stay green and unchanged.
  A regression guard confirms the manual path is untouched.

Reusing the HTTP module contracts instead of the C# code means the two flows share
only the proven step endpoints, so the automated path cannot regress the manual one.

### Already-shipped Phase 6 work is compliant

The completed M12 run-history / deduplication / secret-error / Recent-runs work also
falls under this principle:

- All changes are confined to the M12 module
  (`modules/email-ingestion-module/`), the Email Setup page
  (`EmailSetup.cshtml`, `email-setup.js`), a new additive migration
  (`email_ingestion_runs.sql`, CREATE-only), and docs.
- `apps/stats-web/Program.cs`, the Upload page, and M3/M4/M5/M7/M8/M9 are **not**
  modified, so the manual Upload flow behaves identically.
- The one intentional behaviour change — persistent dedup making a repeated email
  *Run import* skip already-imported attachments — is scoped to the email path only
  and was an explicit Phase 6 requirement.
- Shared deploy surfaces (the common SQL migration runner and the shared runtime
  container that also hosts M12) are additive and structurally verified; the
  container test run confirms the migration applies and M12 health passes, which
  protects the Upload flow at deploy time.

## Decision Summary

- **Trigger:** Azure **Event Grid** on Blob-Created over the intake container/prefix.
  When M3/M4 writes an accepted attachment to Blob intake, the write itself starts
  the pipeline. M12 needs no queue credentials and stays decoupled from the
  downstream chain.
- **Orchestrator:** **Python**, folded into the Email Ingestion Module at
  `modules/email-ingestion-module/app/pipeline/`. It runs the M5 -> M7 -> M8 -> M9
  workflow by calling the existing module HTTP contracts. The unattended runtime is
  **Python Durable Functions on the existing Container Apps environment**
  (Functions-on-ACA) for per-step state/retries/checkpoints, or a Python KEDA /
  Event-Grid-triggered Container Apps Job if the durable engine is not warranted.
- **Language:** Python throughout. C# is used only in the Stats Web frontend/shell
  (`apps/stats-web`); every backend module and the data layer are Python. Because the
  orchestrator is folded into M12 (Python) and does not reuse the C# Upload
  orchestration code, no C# is introduced for this work.
- **Mailbox trigger (the "both together" piece):** M12 polling runs as an Azure
  **Container Apps Job (cron)** for enabled source profiles. The existing manual
  buttons remain.
- **Why this combination:** every component scales to zero (cost floor), reuses the
  existing storage account, honours the container-first runtime, and reuses the
  already-tested M5-M9 step sequence.

## Cost Rationale

The expensive pattern is always-on compute (min replicas >= 1). This design avoids
it everywhere:

| Component | Billing shape | Notes |
| --- | --- | --- |
| Container Apps Job (M12 cron) | Per execution (vCPU-s, GiB-s); scales to zero | Runs only on the schedule. |
| Event Grid (Blob-Created) | Per operation | Effectively pennies at this volume. |
| Durable Functions on ACA | Per execution + small Storage for orchestration state | Scales to zero between documents. |
| Azure Storage Queue (if used) | Per operation + negligible storage | Only if a queue is added in front of Durable Functions. |

KEDA is built into Container Apps and is free; a KEDA-scaled job also scales to zero.
KEDA does **not** cost more — scale-to-zero is exactly why it is cheap. Durable
Functions replaces the need for a separate KEDA worker here, so we do not pay for
both. Confirm current per-unit rates in the Azure Pricing Calculator before sign-off,
since rates change.

## Target Architecture

```text
[Mailbox]  --IMAP SSL-->  M12 Email Ingestion (Container Apps Job, cron)
                                 |  (manual Run import button = same path, on demand)
                                 v
                         M3/M4 File Intake  --stores original PDF-->  Azure Blob (intake/)
                                                                          |
                                                          Blob-Created event
                                                                          v
                                                              Azure Event Grid
                                                                          v
                                          Durable Functions orchestration (on Container Apps)
                                                                          |
        +-----------------+----------------------+----------------------+-----------------------+
        v                 v                      v                      v                       v
   M5 document_parsing  M7 transaction_extraction  M8 data_validation   Governed persist     processing-jobs/steps
   (/api/v1/parses)     (/api/v1/extractions)      (/api/v1/validations)  to M9 Azure SQL     written for UI/evidence
                                                                          |
                                                                          v
                                                          Stats Web Documents / Reports / Power BI
```

The orchestration calls the same module APIs the Upload flow already uses, sourcing
the file from Blob intake by `ingestion_id` instead of a browser temp file.

## The Persistence Gap — governed by taking the *unreviewed* path

Today's `RunProcessingJobAsync` (Stats Web) stops at **validation** with status
"Review the results before saving." In the Upload flow a human reviews and confirms
the save into M9, and **that flow stays exactly as-is**. The unattended email path has
no reviewer.

The key correction (validated against the module specs): **the governance is not
something M12 builds** — it is already specified and implemented in M8/M9, and M12 must
not own classification (see its Non-Goals). The automated save becomes governed simply
by flowing the **unreviewed** route:

- M8 already marks records for review when labels are unknown, out-of-vocabulary,
  pending, ambiguous, or below the confidence threshold, and emits `review_items` +
  `document_review_status` (M8 spec).
- M9 already treats the Upload review/accept/save as the **human-confirmation event**
  that activates labels and bypasses the `/Admin/Classifications` pending path, and
  learns merchants only from `classification_human_confirmed = true` (M9 spec,
  "Recognition Label Suggestions And Synchronization").

So the automated orchestration must:

- **Not** set `classification_human_confirmed` / `classification_confirmed_by_user_id`,
  and pass the `active_recognition_context` it already fetches. Then confident,
  known-vocabulary rows save as transactions, while unknown / low-confidence /
  out-of-vocabulary rows become **pending** recognition suggestions + `review_items`,
  routed to the `/Admin/Classifications` workflow (the deferred *Post-MVP Admin
  Recognition Workflow For Automated Ingestion*). Merchant learning stays
  uncontaminated because it requires human confirmation.

> **Status.** `app/pipeline/orchestrator.py` currently persists the M8 validation result
> via the M9 endpoint with a system identity ("process to database"). The remaining work
> is a **verification, not a new engine**: confirm the automated save does not claim
> human confirmation (so M8/M9 govern it), and confirm `_classification_activation_allowed`
> keys on human-confirmation / known vocabulary. Reporting of what was routed to review vs
> saved (source coverage / review-impact) is an **M11** deliverable, backed by an
> M12-side pending/excluded record for `password_required` / `skipped` / `failed`.
> Cross-run dedup (`is_ingestion_processed`) prevents re-saving the same attachment.

## Idempotency and Deduplication Across the Chain

- M12 already deduplicates at the source (run-local + persistent "already imported"
  check) and sends `idempotency_key` / `source_id` to M3/M4.
- The Durable Functions orchestration uses the **`ingestion_id` as the orchestration
  instance id**, so a duplicate Blob event (Event Grid is at-least-once) cannot start
  a second pipeline for the same document.
- The governed persist step keys on ingestion/transaction identity so a retried
  orchestration does not double-write M9 rows.

Net effect: at-least-once delivery anywhere in the chain still yields exactly-once
persistence.

## Security

- **Managed identity** for all service-to-service access: Blob intake read, Event
  Grid, Azure SQL, and Key Vault. No connection strings in code.
- Mailbox app passwords and reusable PDF passwords stay in **Key Vault**, referenced
  by `secret_ref` only (already implemented). The saved-secret decrypt failure now
  surfaces as an actionable operator message rather than a 500.
- The orchestration never logs secrets, full email bodies, or raw attachment content;
  it propagates the M12 `correlation_id` for end-to-end tracing.
- Original encrypted PDFs stay private in Blob; locked PDFs follow the existing
  password workflow before parse.

## Azure Resources

| Resource | New or existing | Purpose |
| --- | --- | --- |
| Azure Container Apps environment | Existing (`ca-stats-dev-001`) | Hosts M12 job + Durable Functions app. |
| Azure Container Registry | Existing (`acrstatsdev001`) | Stores the Functions/orchestrator image. |
| Azure Blob Storage | Existing | Intake storage + Durable Functions state. |
| Azure Key Vault | Existing (`kv-stats-dev-001`) | Mailbox/PDF secrets. |
| Azure SQL | Existing (`sqldb-stats-dev`) | M9 persistence + M12 run history. |
| Log Analytics | Existing | Redacted pipeline + run traces. |
| **Container Apps Job (M12 cron)** | New (within existing env) | Scheduled mailbox polling. |
| **Durable Functions app (on ACA)** | New (within existing env) | M5-M9 orchestration. |
| **Event Grid system topic + subscription** | New (lightweight) | Blob-Created -> orchestration. |
| Azure Storage Queue (optional) | New (in existing account) | Only if buffering before Durable Functions is wanted. |

Per the M12 spec, creating new Azure resources needs explicit approval. The new items
above live inside the existing environment/account and should be provisioned via IaC
(Bicep) in one reviewed change.

## Phased Implementation Plan

### Phase A - Headless pipeline (repo, testable without new Azure resources) — scaffolded

Implemented inside the M12 module at `modules/email-ingestion-module/app/pipeline/`
(folded into Email Ingestion; additive, new files only; `Program.cs` and the Upload
flow untouched). The orchestration core runs and is unit-tested with fakes; live
module calls are integration-tested by Codex in the container. The current save
contract calls the existing `POST /api/v1/transactions/batches` endpoint with a
system `saved_by_user_id`. This proves the email path can process imported files to
the database, but it does **not** yet apply the final recognition-governed
auto-save policy.

1. Build a **new, independent** automated orchestration that sources the file from
   Blob intake by `ingestion_id` and calls the **module API contracts** in the same
   order the manual flow uses (`/api/v1/parses` -> `/api/v1/extractions` ->
   `/api/v1/validations`), writing the same processing-job/step records so the
   Documents UI shows automated runs too. `RunProcessingJobAsync` and the Upload page
   are **not** modified.
2. Built now: add the Phase A process-to-database action using the existing M9
   batch-save contract and system provenance.
3. Remaining: add the **governed persist step** (M9 save with recognition
   governance + admin routing for low-confidence rows) **on the automated path
   only**.
4. Expose an internal, key-protected trigger (`source_type=email_attachment`,
   `ingestion_id`) so the automated run can be driven headlessly and unit/integration
   tested.
5. Regression guard: existing Upload-flow tests/evidence run unchanged and green,
   proving the manual path behaves identically.

Built in this slice: a **manual "Ingest to database" button** beside Run import
(`process_imported_run` + `POST /api/v1/email-ingestions/process-imported`) that runs
the pipeline for an import run's handed-off attachments. It reads the original bytes
back from intake via a new additive M3/M4 endpoint `GET /api/v1/ingestions/{id}/content`
(local + Azure Blob), which also resolves the Phase C content-source need: the
event-driven trigger can fetch stored bytes by `ingestion_id` the same way.

The Email Setup UI and scheduler now pass the exact import `run_id` into
`process-imported` whenever it is known. This keeps the database ingest tied to the
run that just imported files, instead of accidentally processing an older latest run
for the same source.

### Evidence Guard - One Browser, Two Workflows

Manual evidence for this plan must use one visible Microsoft Edge browser session:

1. Sign in once.
2. Visit `/Upload` first and capture the manual workflow checkpoint.
3. Navigate to `/EmailSetup` in the same browser session.
4. Run the M12 mailbox checks from that page.
5. For the current M12 acceptance boundary, continue through `Run import` and Blob
   proof. Capture both the source mailbox attachment before the run and the Blob row
   after the run.
6. If the Phase A database-ingest scaffold is being tested in the same session,
   continue through `Ingest to database` and Azure SQL proof. Label this as
   process-to-database scaffold evidence, not final governed auto-save evidence.
7. If an intentional failure occurs, such as saved-secret decrypt failure or a
   case-sensitive folder mismatch, capture the failed UI state, the specific reason,
   the corrective action, and the successful rerun after the fix.

This prevents the evidence from accidentally mixing independent sessions and keeps the
review focused on the product rule: M12 is an added intake pathway while the existing
manual Upload pathway remains intact.

### Failure-Stop Rule

Evidence execution is a step-by-step loop:

```text
Run one step -> verify expected result -> capture evidence -> continue.
If the step fails -> stop -> inspect -> report findings -> wait for direction.
```

Do not continue to later evidence steps after an unexpected failure. The tester must
pause the run, inspect the visible UI state, runtime logs, API response, and database
state as applicable, then report:

- the failed step,
- the expected result,
- the actual result,
- the likely cause,
- the recommended fix or decision,
- whether continuing would risk bad evidence or data mutation.

Intentional failure checks are still allowed, but they must be labelled as intentional
failure evidence and must include the corrective action and successful rerun before
the walkthrough is marked complete.

### Current Evidence-Driven Test Plan

Evidence set name:

```text
M12 Email Ingestion Evidence - Manual Import, Blob Handoff, and Database Processing
```

| Step | Target | Evidence | Expected Result |
| --- | --- | --- | --- |
| 1 | Runtime readiness | Terminal screenshot of container health and M12 health | `stats-runtime` is running and M12 returns healthy metadata. |
| 2 | Manual Upload no-regression | Edge screenshot of `/Upload` with address bar visible | Existing manual upload workflow is still available before M12 testing starts. |
| 3 | Mailbox source proof | Browser screenshot of the mailbox message/attachment, redacted as needed | A PDF expected for ingestion exists before the import run. |
| 4 | Email Setup profile | Edge screenshot of `/EmailSetup` with selected profile | Profile shows saved-secret behavior without exposing the mailbox app password. |
| 5 | Test connection | Edge screenshot near the Test connection button/status | Success, or a specific actionable failure with the fix documented. |
| 6 | Dry run | Edge screenshot of run status and paginated result table | Candidate list uses profile folder/sender/subject filters and only PDFs enter results. |
| 7 | Run import | Edge screenshot of run summary and imported candidates | Eligible PDFs are handed off to M3/M4; skipped/duplicate/locked items have specific findings. |
| 8 | Blob proof | Azure Portal or terminal screenshot with account/container/prefix visible | Imported PDFs appear under the configured Blob intake prefix or ingestion id. |
| 9 | Ingest to database | Edge screenshot of current step/status near the run controls plus terminal screenshot from inside `stats-runtime` querying Azure SQL | The exact imported `run_id` is processed; UI shows processed/succeeded/failed/saved/review counts; SQL rows show `source_type=email_attachment` and `saved_by_user_id=system-email-automation`; evidence is labelled Phase A scaffold. |
| 10 | Database validation | Terminal screenshot from inside `stats-runtime` querying processing jobs, documents, transactions, and review counts | The imported email PDF is traceable from M12 run/correlation id to processing job and persisted database rows. |
| 11 | Failure handling | Edge screenshot of an intentional failed dry run/import/process-imported state, if exercised | The visible failure includes the reason, the corrective action is documented, and the successful rerun is captured. Configuration failures report `failed_count = 1`. |
| 12 | Logs/security | Terminal screenshot or redacted log excerpt | Logs contain run/correlation/ingestion ids, not secrets, passwords, tokens, email bodies, or raw content. |

Prerequisites for the run:

- `STATS_INTERNAL_API_KEY` is configured for file-intake readback, process-imported,
  and scheduled-run tests.
- `STATS_TESTDATA_DIR` points to a directory with top-level PDFs when file-intake
  real-PDF unit tests are included.
- The selected source profile has a saved mailbox app password secret, so the
  password field can be blank for connection/import checks.
- PDF password tests use configured saved PDF password rules in M12. Full locked-PDF
  parsing/database proof is in scope only when the downstream M3/M4/M5 path receives
  the unlocked/decrypted file for that test run; one-time password retry remains
  deferred.

### Phase B - Unattended runtime (Python)

1. Host the Phase A orchestration (`app/pipeline`, Python) as the unattended runtime:
   **Python Durable Functions** on the existing Container Apps environment
   (instance id = `ingestion_id`, retry policies and checkpoints per activity), or a
   **Python KEDA / Event-Grid-triggered Container Apps Job** if the durable engine is
   not warranted. No C# is introduced — the orchestration code is reused as-is.
2. Containerize and run it on the existing Container Apps environment.

### Phase C - Event Grid trigger

1. Add an Event Grid subscription on Blob-Created for the intake prefix that starts
   the orchestration (client function).
2. Idempotency guard on duplicate events.

### Phase D - Scheduled mailbox polling (M12) — app-side built

App-side partly done: per-profile cadence (Off / Hourly / Daily + time, UTC) is
configured on the Email Setup page and stored on the profile; `schedule_rules.is_schedule_due`
decides due-ness; `POST /api/v1/email-ingestions/scheduled-runs` is internal-key
protected. `scheduler.run_due_profiles` now processes only the exact import `run_id`
produced by the current tick; failed/no-run-id imports do not call database ingest
and do not stamp `last_auto_run_at`, so the next tick retries instead of processing
an older latest run.

Repo scaffold now includes the scheduled Azure Container Apps Job pieces:

- `/app/run-m12-scheduled-ingestion.sh` calls the Stats Web proxy route with
  `X-Stats-CSRF: 1` and `X-Stats-Internal-Key`.
- `infrastructure/cloud/deploy-m12-scheduled-ingestion-containerapp-job.ps1`
  creates/updates `job-stats-m12-email-ingestion` on an hourly cron by default.
- The scheduled endpoint uses an app-side non-blocking lock, and the job is
  configured with single-replica execution settings to reduce overlap risk.

Remaining:

1. Live Azure provisioning: run the deployment script with the actual Stats Web URL,
   registry identity resource id, and image tag.
2. Runtime evidence: prove the scheduler endpoint in the container/cloud path with
   disabled/off-cadence profiles, due profiles, exact `run_id` propagation, failed
   imports, and no `last_auto_run_at` advance on failed/no-run-id imports.

### Phase E - Observability and evidence

1. Emit `correlation_id` across M12 run history, processing-jobs, and Durable
   Functions to Log Analytics.
2. Failure alerting on `failed`/`blocked` runs and orchestration failures.
3. Current cloud smoke: an email lands a PDF that flows mailbox -> Blob, with
   before/after visual evidence and redacted logs.
4. Phase A database smoke: the same imported file can be processed to Azure SQL with
   system provenance, clearly labelled as process-to-database scaffold.
5. Process-imported failure smoke: capture a visible failed state and reason for a
   controlled configuration or profile error, then capture the corrected successful
   rerun.
6. Future final smoke: the unattended flow runs mailbox -> Blob -> parse -> extract ->
   validate -> governed save -> Azure SQL -> Documents/Reports, with redacted logs.

## Repo Changes (by file area)

- `apps/stats-web/Program.cs` - **unchanged**. The manual Upload orchestration
  (`RunProcessingJobAsync`) and page behaviour are not touched.
- New automated orchestration code (Python) folded into M12 at
  `modules/email-ingestion-module/app/pipeline/`, calling the module API contracts
  directly. Phase B wraps it in the unattended runtime; no separate C# project.
- `infrastructure/` (Bicep) - Container Apps Job, Functions-on-ACA app, Event Grid
  subscription, role assignments (managed identity).
- `modules/email-ingestion-module/config/defaults.env` - polling/schedule + post-process
  flags.
- Tests/evidence under the existing container-first runner.

## Open Risks

- The governed persist step is genuinely new behaviour; auto-saving unreviewed
  financial data must be conservative (governance-gated) to avoid wrong rows.
- Functions-on-ACA cold starts add latency to the first document after idle; acceptable
  for this workload but worth measuring.
- Event Grid is at-least-once; the `ingestion_id` instance-id guard is mandatory, not
  optional.
- Exact Azure costs must be validated against current pricing before sign-off.

<!-- M12 End -->
