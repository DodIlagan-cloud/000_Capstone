# Module Spec Template

<!-- M0 Foundation: reusable starting template for later Stats modules. -->

## Module Identity

| Field | Value |
| --- | --- |
| Module number | `<Mx>` |
| Module name | `<name>` |
| Build order | `<order>` |
| Type | `<standalone module / encompassing app / integration / infrastructure / project>` |
| Owner folder | `<apps/... or modules/...>` |

## Business Alignment

Describe the business-analysis area this module supports and the reason it is separated as this building block.

## Goals

- `<goal>`

## Non-Goals

- `<explicitly deferred behavior>`

## Architecture Boundary

State what this module owns, what it calls, and what it must not absorb from neighboring modules.

## Spec-First Build Authority

This spec is the source of truth for the module implementation.

- Architecture decisions that affect this module must be reflected here before code or tests are changed.
- Implementation, tests, UI behavior, and evidence must align with this spec.
- If the code and this spec disagree, treat it as a defect until the spec is intentionally updated or the implementation is corrected.
- From M13 onward, official acceptance evidence must use the container-first path declared in this spec.

## Inputs and Outputs

| Direction | Contract or Input | Description |
| --- | --- | --- |
| Input | `<contract>` | `<description>` |
| Output | `<contract>` | `<description>` |

## Error and Status Results

| Result | Caller Meaning |
| --- | --- |
| `<status or error>` | `<visible behavior>` |

## Dependencies and Configuration

- Runtime: `<runtime>`
- Official runtime command: `<container-first command after M13; diagnostic host command only if useful>`
- Official test command: `<container-first command after M13; diagnostic host command only if useful>`
- Configuration sample: `<path>`
- External dependencies: `<dependencies>`

<!-- M0 Foundation Start -->
<!-- Prompts each module spec to declare config-driven runtime values. -->
- Runtime values owned by this module: `<URLs, hosts, ports, database/resource targets, secrets, limits, paths, feature switches>`
- Runtime registry alignment: `<entries added to or reused from config/stats.runtime.json>`
- Config override path or provider: `<config file, environment variables, managed secrets, or other provider>`
- Directory path policy: `<logical paths from config/stats.paths.json resolved from STATS_APP_ROOT; storage provider from STATS_STORAGE_PROVIDER when durable files are used>`
- Logging policy: `<config/stats.logging.json entries used; redaction/correlation/stdout behavior>`
- Real-data test input variables: `<environment variables or config keys such as STATS_TESTDATA_DIR; state failure/setup behavior when unavailable>`
- Hardcoded runtime values allowed in source: `none unless explicitly justified as a stable code constant`
<!-- M0 Foundation End -->

## Tasks

1. `<implementation task>`
2. `<test or evidence task>`

## Test Plan

| Check | Level | Evidence |
| --- | --- | --- |
| `<behavior>` | `<unit / direct / integration / manual>` | `<test result, raw output, screenshot, checklist>` |
| Real-data processing with configured local/anonymized dataset | `<automated / evidence>` | `<raw output showing configured test data was processed and relevant handoff/assertion passed>` |

## Acceptance Criteria

- `<observable completion criterion>`

## Deferred Items

- `<future module or later pass>`
