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
| Evidence folder | `test-results/<module-or-regression-session>/` |

## Business Alignment

Describe the business-analysis area this module supports and the reason it is separated as this building block.

## Goals

- `<goal>`

## Non-Goals

- `<explicitly deferred behavior>`

## Architecture Boundary

State what this module owns, what it calls, and what it must not absorb from neighboring modules.

Project-wide documentation and evidence belong in root `docs/` and root `test-results/`. The owner folder should contain only module/app implementation code, module-local automated tests, runtime configuration samples, local run instructions, and assets required by that module/app.

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
- Local run command: `<command>`
- Local test command: `<command>`
- Configuration sample: `<path>`
- External dependencies: `<dependencies>`

<!-- M0 Foundation Start -->
<!-- Prompts each module spec to declare config-driven runtime values. -->
- Runtime values owned by this module: `<URLs, hosts, ports, database/resource targets, secrets, limits, paths, feature switches>`
- Config override path or provider: `<config file, environment variables, managed secrets, or other provider>`
- Hardcoded runtime values allowed in source: `none unless explicitly justified as a stable code constant`
<!-- M0 Foundation End -->

## Tasks

1. `<implementation task>`
2. `<test or evidence task>`

## Test Plan

Store test summaries, raw output, manual checklists, screenshot indexes, and screenshots under root `test-results/<module-or-regression-session>/`.

| Check | Level | Evidence |
| --- | --- | --- |
| `<behavior>` | `<unit / direct / integration / manual>` | `<test result, raw output, screenshot, checklist>` |

## Acceptance Criteria

- `<observable completion criterion>`

## Deferred Items

- `<future module or later pass>`
