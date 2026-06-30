<!-- Cloud-Dev User Flow Tracking Start -->
<!-- Versioned tracking rules for segmented cloud-dev user-flow evidence. -->

# Cloud-Dev User Flow Tracking

## Purpose

This document defines how segmented cloud-dev user-flow tests are tracked.

The user-flow plan defines the test scope:

```text
docs/cloud-dev-user-flow-evidence-plan.md
```

The local live tracker records active run state:

```text
tests/results/CloudDevUserFlows/USER-FLOW-TRACKER.md
```

`tests/results/` is ignored by Git because evidence folders can contain screenshots and generated output. The live tracker is therefore a local execution log, while this document is the committed tracking contract.

## Tracking Model

Each user-flow segment has three records:

| Record | Location | Purpose | Git status |
| --- | --- | --- | --- |
| Plan | `docs/cloud-dev-user-flow-evidence-plan.md` | Defines segments, expected steps, stop conditions, and evidence requirements. | Committed |
| Live tracker | `tests/results/CloudDevUserFlows/USER-FLOW-TRACKER.md` | Tracks current status, run log, next action, and evidence folder paths. | Local evidence, ignored |
| Evidence folder | `tests/results/CloudDevUserFlows/<segment-name>-YYYY-MM-DD-HHMMSS/` | Stores screenshots, raw output, redacted JSON, and walkthrough for one run. | Local evidence, ignored until selected for final evidence check-in |

## Required Tracker Updates

Before a segment starts:

1. Mark the segment `Running`.
2. Record the run timestamp.
3. Record the planned evidence folder.
4. Confirm the previous segment state supports continuing.

During a segment:

1. Write checkpoint screenshots and state summaries as soon as they are captured.
2. Add notes for long waits, retries, or blockers.
3. Do not wait until the end of a long run to create evidence.
4. After Segment 1, do not recapture login pages unless the segment is testing authentication, role switching, session expiry, or access control.
5. Reuse the shared browser/session when it is already available; launch a new browser only when no reusable debug session exists.
6. Record elapsed time for each major setup/action/wait step, especially processing waits.
7. For document-processing segments, include product-side `document_processing_steps` timings in the segment result.

After a segment:

1. Mark the segment `Passed`, `Passed with classification gap`, `Failed`, `Blocked`, `Deferred`, `Merged`, or `Superseded`.
2. Add the final evidence folder path.
3. Add a run-log row with the outcome and summary.
4. Mark the next valid segment `Ready` only when the current segment result allows it.

Walkthrough files must embed screenshots inline. A table of screenshot links is useful for scanning, but it is not enough for evidence review. Each `walkthrough.md` should include an `Embedded Screenshots` section with one Markdown image per retained segment-specific screenshot, followed by the reviewer check and visual result note. Login screenshots are embedded in Segment 1 only; later segments should reference Segment 1 as the authentication baseline and record authenticated role/user details in state or raw output.

Walkthrough files should also include an `Elapsed Timings` table sourced from `state-summary.json`. Timing rows should be human-readable major steps, not every low-level browser command.

For document-processing segments, walkthroughs should include a separate `Product Processing Timings` table from the app/backend `document_processing_steps` records. Keep this separate from runner timing so product performance is not mixed with browser/test overhead.

Browser lifecycle is intentionally shared across segment runs. A segment may navigate, sign in, switch user, or refresh prerequisite state as setup, but should keep the Edge session open after completion so the next segment can reuse it. Cleanup/reset segments are the only normal place to close the shared browser.

Docker is not part of cloud-dev user-flow evidence. Earlier runners used local `stats-runtime` as a convenient Azure SQL query helper, but that mixed local runtime tooling into a cloud test path. Cloud segments should run against the live Container App with Azure SQL online. Backend diagnostics, when needed, should come from cloud app APIs, Azure resource checks, or direct Azure SQL diagnostics.

## Status Board Template

```markdown
| Order | Segment | Status | Evidence Folder | Last Updated | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Fresh-state setup | Ready | Pending | YYYY-MM-DD | Reset and bootstrap required. |
| 1 | Sign in and navigation | Planned | Pending | YYYY-MM-DD | Admin and standard user required. |
| 2 | Valid document upload | Planned | Pending | YYYY-MM-DD | One approved fixture first. |
| 3 | Processing, review, accept, and save | Planned | Pending | YYYY-MM-DD | Stable M5/M7/M8 result, accept/save, Documents proof, and suggestion status required. |
| 4 | Edit and accept review items | Merged | Segment 3 evidence | YYYY-MM-DD | Covered by Segment 3 unless edit-form depth is specifically required. |
| 5 | Save transactions | Merged | Segment 3 evidence | YYYY-MM-DD | Covered by Segment 3 unless save-only behavior is specifically required. |
| 6 | Duplicate handling | Planned | Pending | YYYY-MM-DD | Requires saved baseline. |
| 7 | Documents management | Planned | Pending | YYYY-MM-DD | List/detail/remove. |
| 8 | Reports | Planned | Pending | YYYY-MM-DD | Saved-data or blocked-state proof. |
| 9 | Final cleanup | Planned | Pending | YYYY-MM-DD | Return cloud-dev to known state. |
```

## Run Log Template

```markdown
| Date/Time | Segment/Run | Status | Evidence/Output | Notes |
| --- | --- | --- | --- | --- |
| YYYY-MM-DD HH:MM | Segment name | Passed/Failed/Blocked | `tests/results/CloudDevUserFlows/...` | Short result summary. |
```

## Current Tracking Note

As of 2026-06-17, the previous all-input cloud runner is superseded by segmented cloud evidence plus the MVP cloud regression run.

Current local evidence state:

| Segment | Status | Local Evidence |
| --- | --- | --- |
| 0 - Fresh-state setup | Passed | `tests/results/CloudDevUserFlows/segment-0-fresh-state-setup-20260612-164552` |
| 1 - Sign in and navigation | Passed | `tests/results/CloudDevUserFlows/segment-1-signin-navigation-20260612-165529` |
| 2 - Valid document upload | Passed | `tests/results/CloudDevUserFlows/segment-2-valid-document-upload-20260612-170828` |
| 3 - Processing, review, accept, and save | Passed | `tests/results/CloudDevUserFlows/segment-3-processing-review-20260613-073637` |
| 4 - Edit and accept review items | Merged | `tests/results/CloudDevUserFlows/segment-3-processing-review-20260613-073637` |
| 5 - Save transactions | Merged | `tests/results/CloudDevUserFlows/segment-3-processing-review-20260613-073637` |
| MVP cloud regression | Accepted with deferred regression defects | `tests/results/MVP-CloudRegression/mvp-cloud-regression-20260617-082920` |
| Post-MVP fresh upload/save retest | Passed | `tests/results/MVP-CloudRegression/mvp-cloud-regression-20260617-082920` |
| Post-MVP duplicate-proof retest | Partial / failed | `tests/results/MVP-CloudRegression/mvp-cloud-regression-20260617-082920` |
| MVP Segment 6 - Reporting/Fabric | Passed | `tests/results/MVP-CloudRegression/mvp-cloud-regression-20260617-082920` |

Segment 3 passed on 2026-06-13 using the cloud-only/shared-browser runner and the fixture `recpt.jpeg`. It now includes processing, transaction review, accept, save, Documents proof, product timings, and AI/suggestion status in one walkthrough. The previous blocked Segment 3 run with `20260528_083213.jpg` is retained as historical evidence. Segment 4 and Segment 5 are merged for this receipt flow.

Screenshot scope update: Segment 1 is now the canonical evidence for admin and standard-user sign-in/navigation. Segment 2 onward should avoid repeated login-page screenshots and focus on the user-facing function being tested.

Browser reuse update: Segment runners should attach to the shared Edge debugging session on the configured port, reuse the existing standard-user session when present, and leave the shared browser open after each segment.

Docker scope update: Segment runners should not use Docker Desktop for cloud UI testing or cloud database diagnostics. Docker is reserved for local/container regression evidence, not cloud-dev user-flow evidence.

AI classification cloud-dev update: cloud-dev should keep M5 and M7 AI-assisted classification enabled through Container App env vars and secret-backed provider keys. If a segment expects AI categorisation, the walkthrough must record the active Container App revision, AI enablement state, recognition-settings availability, and any explicit AI skip reason surfaced by the app. A previous segment with `Unknown` or `Uncategorized` output remains `Passed with classification gap` until a fresh normal UI rerun proves the categorisation path.

MVP cloud regression update: run `mvp-cloud-regression-20260617-082920` used image `acrstatsdev001.azurecr.io/stats-runtime:dev-fa82cab`. The environment, inventory, navigation, classification visibility, and reporting/Fabric segments passed. Fresh upload/save and duplicate proof failed, but M10/MVP was accepted on June 17, 2026; those two behaviours are deferred as post-MVP regression defects. Segment 6 captured Fabric active state, Azure SQL reporting source records, and screenshots for Financial overview, Spending categories, Classification quality, Source coverage, and Review impact.

Post-MVP deferred test update: the fresh upload/save scenario was continued with `202311_BPICCBE20231108.pdf`. The user-visible review flow was completed by editing missing spending subcategories, accepting rows, and saving. Azure SQL proof shows one saved document and 13 transactions, so fresh upload/save is now passed for the realistic review-edit path. Duplicate-proof remains partial/failed: reuploading the same file shows the pre-save duplicate guard after review edits and blocks duplicate transactions, but Azure SQL briefly created a second zero-transaction `stats_documents` row with the same filename/hash. The extra duplicate document row was cleaned up and documented; the remaining defect belongs to the post-MVP duplicate persistence boundary.

Cloud-dev WIP context update as of 2026-06-18: after MVP acceptance, cloud-dev was parked for cost control. Fabric capacity `capstatsdev001` was paused, Container App `ca-stats-dev-001` scaling was reduced to idle-friendly settings, Azure SQL serverless auto-pause remains configured, stale ACR image tags were removed, local stale Docker image tags/build cache were cleaned, and temporary `C:\000_Capstone_acr_context_*` folders were deleted. Future cloud evidence runs must explicitly resume the required cloud resources before execution.

Wk12 update as of 2026-06-24: M12 Email Ingestion has local implementation and runtime packaging, but no cloud-dev user-flow or cloud smoke segment has been recorded for the new email-ingestion path. Any future M12 cloud evidence must resume cloud-dev intentionally, apply the Azure SQL email-ingestion migration/configuration, verify secret references without exposing secret values, and capture Email Setup plus source-profile/test-run evidence through the live Container App.

<!-- Cloud-Dev User Flow Tracking End -->
