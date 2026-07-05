<!-- M11 - Stats Dashboard and Reporting Code Review Start -->

# M11 Code Review — 2026-07-04

Scope reviewed: `StatsReportingKpis` and `StatsReportingEmbedConfig` in `apps/stats-web/Program.cs`, `wwwroot/js/reporting.js`, `Pages/Index.cshtml(.cs)`, `Pages/Reports.cshtml(.cs)`, `apps/stats-data/reporting/financial_reporting_read_models.sql`, `appsettings.json`, and `tests/integration/test_stats_web_orchestration_config.py`. Working-tree diffs are line-ending churn only; the M11 work lives in commits `fe5443e`, `b8d20d5`, `fa82cab`, `e0cf244`.

## What is done well

- Controlled UX states are implemented consistently: `not_configured`, `unavailable` (502 with safe payload), and pending states on both KPI and embed paths. A test enforces that raw Power BI error details never reach the browser.
- DAX injection is handled: currency is normalized to 3 ASCII letters, the as-of date is built from a parsed `DateOnly`, and FX rates are parsed decimals — no raw user input reaches the query.
- No secrets committed: `appsettings.json` holds empty placeholders; the client secret is read through configuration/env only and never echoed in responses or logs.
- `SanitizePayload` whitelists the external embed response fields instead of passing the payload through — good defensive posture.
- Read models exclude duplicates, expose only `source_text_redacted` and `masked_account_or_card`, and carry `uploaded_by_user_id` on every view (test-enforced).
- Boundary compliance holds: KPIs come from Power BI over curated M9 views; no calls to M3/M5/M7/M8 for report totals; Reports is native-first with embed as secondary, per spec.
- Cross-currency bridge derivation (`AddCrossCurrencyRates`) implements the spec's bridge-pair requirement correctly, including inverse rates.

## Findings

### High

**H1. Embed-config endpoint is not admin-gated while the KPI endpoint is.**
`GetKpisAsync` returns 403 for non-admins (Program.cs:593), but `GetEmbedConfigAsync` only checks authentication (Program.cs:1238). In `AppOwnsData` mode, `GenerateToken` is called with `{"accessLevel": "View"}` and no `identities`, so the returned embed token grants view access to the entire semantic model — all users' financial data. Any authenticated non-admin can call `/api/v1/reporting/embed-config` and extract `access_token`. Fix: apply the same admin gate until row-level security exists, or add RLS roles + `EffectiveIdentity` to the token request.

**H2. No user scoping anywhere in the analytics path.**
The read models expose `uploaded_by_user_id`, but the DAX query never filters on it and the semantic model has no RLS. Admin-only gating is the implicit mitigation, but the spec requires "scope ordinary users to their own documents and transactions" — as designed, the dashboard can never be opened to ordinary users. This deserves an explicit spec note (interim admin-only decision) and an RLS plan; otherwise H1-style leaks will recur on every new reporting surface.

### Medium

**M1. Unconvertible currencies are silently zeroed.**
`COALESCE(ExchangeRate, 0)` multiplies amounts by 0 when no FX rate exists for a source currency (e.g., anything outside NZD/PHP/AUD/USD, or when `FxRates` config is empty). The spec explicitly requires conversion "instead of filtering records out" — zeroing is filtering with extra confusion, and it understates totals with no warning. Surface an "unconverted amounts excluded" flag, or fail visible.

**M2. "This month running" can silently show an old month.**
`LatestReportingMonth` is the max month *with data*, not the as-of month. With no current-month data, the "This month running" card shows the latest historical month, "Last month expenses" shows the month before that, and the trend delta compares the wrong pair. Useful for `STATS_AS_OF_DATE` testing, misleading in production. Show 0 for a data-less current month, or label the month actually displayed on the card.

**M3. `vw_reporting_recent_notable_expenses` puts `TOP (100)` inside the view.**
The top-100 is computed across all users before any consumer filter, so a per-user (or per-currency) filter applied on top can return zero rows for a user who has data. Move the TOP/ORDER BY to the consumer query; keep the view unbounded.

**M4. No AAD token caching.**
Every KPI and embed-config request performs a fresh client-credentials round trip. Home + Reports loading together means multiple token requests per page view — latency plus AAD throttling risk. Cache the access token until near expiry.

**M5. "Last updated" fabricates freshness.**
`last_refreshed_at_utc` is always null server-side, and reporting.js falls back to `new Date().toISOString()` when status is configured — the header shows page-load time as data freshness. Either query the dataset refresh history or display "Refresh time unknown".

### Low

**L1. Non-admin KPI response has no body.** `Results.StatusCode(403)` makes `response.json()` throw, collapsing to a generic "Unavailable" state. Return a controlled JSON payload (e.g. `status: "not_authorized"`) so the UI can be honest about why.

**L2. String-packed DAX results are fragile.** `monthly_history` and `spending_categories` are CONCATENATEX-packed with `:`/`|` delimiters. `SUBSTITUTE` guards `|` in category names but not `:`; a category containing `:` misparses. Prefer returning rows (separate query/table) over delimiter packing.

**L3. `IsNotConfiguredResult` uses reflection on an anonymous type.** Works, but brittle against refactors; a typed result record would be safer.

**L4. Read-model SQL still lives outside migrations.** Acknowledged in the file header; M9 promotion (or a managed reporting-view deployment step) remains open per spec.

**L5. Test approach is source-string assertion, not behavior.** `test_stats_web_orchestration_config.py` greps `Program.cs`/JS for exact source fragments — including whitespace-sensitive assertions like the `TOPN(\n        6,` check — which break on formatting changes and pass even if the code is behaviorally wrong. There is no C# test project for Stats Web at all, while the spec's test plan requires unit tests for view models, formatting, and query construction. This is the largest test-plan gap.

**L6. Committed resource identifiers in docs.** The spec doc records the real semantic model ID, report ID, capacity name, and tenant account UPN. These are low-sensitivity, but the repo's own rule says real resource identifiers must not be committed — either relax the rule's wording or move the IDs to untracked notes.

## Spec acceptance status (delta only)

Met: controlled deferred states, native-first Reports, no processing-module calls for totals, no secrets in code, KPI cards Power BI-backed, currency toggle beside last-updated, classification/category sections wired to read models.

Not yet met: user-scoped queries (H2); Source coverage and Review impact tabs still render static explanatory copy, not the planned summary strips/queues; M9 endpoints `GET /transactions`, `/documents/summary`, `/documents/{id}`, `/review-items`, `/findings` remain unimplemented; Documents provenance rollups pending; M12 email-ingestion reporting shapes absent; evidence traceability (drilldown from KPI to transaction/document) not yet wired.

## Recommended fix order

1. H1 — gate embed-config to admin (one-line parity fix) now; plan RLS.
2. M5 + L1 — honest freshness and honest 403 payloads (small, user-facing trust fixes).
3. M1 + M2 — FX zeroing and month labeling (correctness of displayed numbers).
4. M3 — move TOP out of the notable-expenses view before per-user scoping lands.
5. M4, L2, L3 — hardening.
6. L5 — stand up a Stats Web C# unit test project before Phase 2 endpoint work grows the surface.

---

# Pass 2 — 2026-07-05

Pass 2 covered areas not opened in pass 1 (migrations vs read models, semantic-model contract vs DAX, options/auth/proxy wiring, JS reachability) and verified the uncommitted working-tree fixes that landed in response to pass 1.

## Pass-1 fix verification (uncommitted working tree)

| Finding | Status | Notes |
| --- | --- | --- |
| H1 embed-config admin gate | Fixed | Admin check with controlled 403 payload, parity with KPI path |
| H2 user scoping | Groundwork landed | Proxy strips inbound `X-Stats-User-*` and injects resolved id/email/role; M9 `require_user_id` + scoped `GET /transactions`, `/documents/summary`, `/documents/{id}`, `/review-items`, `/findings`. M1 `/auth/me` returns `id`, so the chain works end-to-end. Analytics (Power BI) path still unscoped — admin-only remains the mitigation |
| M1 FX zeroing | Partially fixed | Current-month unconverted total surfaced with a banner warning. History months, categories, top contributor, and notable expense still zero unconverted amounts silently |
| M2 month relabeling | Fixed | `this_month_label`/`last_month_label` now shown in card detail text |
| M3 `TOP (100)` in view | Fixed | Removed from `vw_reporting_recent_notable_expenses`. The updated SQL must be re-applied to cloud-dev — the deployed views are now stale |
| M4 token caching | Open | And the proxy adds a second `/auth/me` round trip per proxied request — see P2-6 |
| M5 fabricated freshness | Fixed | JS no longer substitutes page-load time; server-side real refresh timestamp still TODO (always null) |
| L1 empty 403 body | Fixed | Controlled `not_authorized` payloads on both endpoints |
| L2 delimiter packing | Mitigated | `:` and `|` both substituted in category names; packing itself remains |
| L3, L5 | Open | Reflection helper unchanged; none of the new fixes/endpoints have tests |

## New findings

### High

**P2-1. Trend delta compares the wrong months.**
`expense_trend_delta = CurrentMonthExpenses - PreviousMonthExpenses`, but `PreviousMonthExpenses` filters `PriorReportingMonth` (the *third*-latest month), while `LastMonthExpenses` (second-latest) is computed and unused for the delta. With ≥3 months of data the "Change vs prior month" card shows latest-minus-two-months-back — a wrong number under the label "This month spending minus the previous month". Likely a naming collision (`Last`/`Previous`/`Prior` all mean "the one before"). Fix: use `CurrentMonthExpenses - LastMonthExpenses` and rename the variables.

**P2-2. Save path trusts client-supplied ownership while reads trust the proxy header.**
`POST /api/v1/transactions/batches` persists `uploaded_by_user_id` from the request body, which upload.js populates from the browser (`user.id`). Reads now scope by the server-injected `X-Stats-User-Id`. A tampered client can save records under another user's id, which the victim's scoped reads will then display — an integrity-then-confidentiality hole that undermines the new scoping. Fix: derive owner from the trusted header on save endpoints too (or reject body ids that don't match it).

### Medium

**P2-3. Pre-existing rows with NULL `uploaded_by_user_id` vanish from scoped reads.**
`GET /api/v1/documents` now filters by owner. Documents saved before ownership was captured (or with empty `user.id`) have NULL owner and will silently disappear from the Documents page after deployment. Decide: backfill, show-unowned-to-admin, or explicit migration note — before this ships.

**P2-4. Contract/code divergence in KPI logic.**
The semantic-model contract defines calendar-anchored measures (`PREVIOUSMONTH`, `DATESMTD` over a Date table); the code re-derives data-anchored months in inline DAX. Native cards and any report visual built on the contract measures can disagree on the same screen. Move the KPI logic into model measures and have the endpoint query them, so there is one definition.

**P2-5. Reports page ignores `IsAdmin`; Home hides the section.**
`ReportsModel` computes `IsAdmin` but `Reports.cshtml` never uses it — non-admins get the full report chrome with every metric "No data" plus a not-authorized banner, while Home hides the KPI section entirely. Pick one pattern (recommend the Home one) for a coherent non-admin experience.

**P2-6. Per-request identity fan-out.**
`GetCurrentUserAsync` hits M1 `/auth/me` with no caching, and is now called by the page model, the KPI/embed endpoints, *and* the proxy — several identity round trips per page view, on top of the uncached AAD token (M4). Cache the resolved user in `HttpContext.Items` per request, and the AAD token until expiry.

### Low

**P2-7. KPI endpoint demands `PowerBiReportId` unnecessarily.** `DirectPowerBiEmbedConfigured` requires ReportId, but `executeQueries` needs only tenant/client/secret/workspace/dataset. A KPI-only deployment without a report configured incorrectly shows not-configured.

**P2-8. Embed path is dead code in the product UI.** No page renders `#reporting-embed-host`, so `renderPowerBiReport`, `ensurePowerBiClient`, the embed-config fetch, the `surface` parameter, and vendored `powerbi.min.js` (324 lines) are unreachable from Index/Reports. Consistent with native-first, and the endpoint is now gated — but keep-or-cut should be explicit (validation-only page, or remove until Phase 4 needs it).

**P2-9. DAX `FORMAT` is model-culture-dependent.** `FORMAT(..., "0.####")` emits the model culture's decimal separator; the C# parser assumes invariant. Fine for en-* cultures, breaks silently otherwise. Another reason to retire string packing (L2).

**P2-10. New read models missing from the boundary test.** `vw_reporting_review_items` and `vw_reporting_findings` carry `uploaded_by_user_id` but aren't in the view list asserted by `test_reporting_read_models_carry_owner_boundary_and_debit_quality_scope`. Add them.

**P2-11. `X-Stats-User-Email` is injected into every proxied request.** Downstream modules that don't need the email now receive PII on every call. Inject id/role only; add email where a consumer actually uses it.

## Verified clean in pass 2

Schema drift: every column referenced by the reporting views exists in migrations 001–013. Contract table names match the DAX friendly names. Proxy header stripping happens before injection (spoof-safe on the read path). No secrets or real identifiers in the new working-tree changes. `/auth/me` returns `id`, so identity injection functions end-to-end.

## Updated fix order

1. P2-2 — make save-path ownership server-derived (do before the scoped reads ship).
2. P2-1 — one-line DAX fix for the trend delta.
3. P2-3 — decide NULL-owner backfill before deploying scoped `GET /documents`.
4. Re-apply updated read-model SQL to cloud-dev (M3 fix is local-only until then).
5. P2-5, M1-remainder (unconverted warning for history/categories), P2-6.
6. P2-4 during Phase 4 semantic-model work; P2-7/8/9/10/11 as clean-up.

---

# Pass 3 — Codex findings reconciliation (2026-07-05)

An external Codex review produced four findings. All four verified against the current working tree (which has evolved again since pass 2: `require_admin_flag` and admin cross-user reads in `api.py` are new since then).

**C1 (High) — Source coverage / Review impact tabs still static: CONFIRMED.** Matches the pass-1 acceptance delta. `reporting.js` fetches only KPI/monthly/category/classification data; no frontend calls `/api/v1/documents/summary`, `/review-items`, or `/findings` even though the M9 endpoints now exist. Agree with the gate recommendation: wire the two tabs or exclude them from RQ3 dashboard scoring.

**C2 (High) — Proxy forwards raw role, not effective admin status: CONFIRMED, new finding.** `StatsCurrentUser.IsAdmin` requires `!MustChangePassword`, but the proxy injects `proxyUser.Role` verbatim, and `require_admin_flag` in api.py string-compares `X-Stats-User-Role == "admin"` to grant cross-user visibility (`include_all`/`owner_user_id=None`). A must-change-password admin is denied analytics in Stats Web UI but still receives cross-user data through every proxied scoped read. Fix: inject the effective status — either send `X-Stats-User-Role` only when `proxyUser.IsAdmin`, or add `X-Stats-User-Is-Admin` derived from `IsAdmin` and consume that in `require_admin_flag`.

**C3 (Medium) — Cloud-dev read models stale: CONFIRMED.** Same as the pass-2 "re-apply" action item, now covering ten views including `vw_reporting_review_items` and `vw_reporting_findings`.

**C4 (Medium) — FX warning narrower than the zeroing: CONFIRMED.** Same as pass-2 "M1 partially fixed": `has_unconverted_amounts` covers only the latest month while monthly history, categories, top contributor, and notable expense still zero unconverted amounts silently.

**Note on P2-3 (NULL-owner rows):** now partially addressed — `require_admin_flag`'s admin path keeps NULL-owner legacy rows visible to administrators. Regular users still lose any legacy rows saved without an owner id; acceptable if documented, but it interacts with C2 (the flag doing that work must be trustworthy) and with P2-2, which remains open: saves still take `uploaded_by_user_id` from the client body, and admin `include_all` reads now surface spoofed rows more widely. P2-2 + C2 should be fixed together as one trusted-identity pass.

**Consolidated pre-commit gate:** C2 + P2-2 (trusted identity end-to-end), P2-1 (trend-delta DAX), C1 decision (wire or exclude tabs), C3 (apply + verify ten views on cloud-dev), C4 (broaden unconverted warning or verify FX coverage for the RQ3 dataset).

<!-- M11 End -->
