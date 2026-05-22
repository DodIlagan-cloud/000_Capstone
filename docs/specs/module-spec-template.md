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

## Tasks

1. `<implementation task>`
2. `<test or evidence task>`

## Test Plan

| Check | Level | Evidence |
| --- | --- | --- |
| `<behavior>` | `<unit / direct / integration / manual>` | `<test result, raw output, screenshot, checklist>` |

## Acceptance Criteria

- `<observable completion criterion>`

## Deferred Items

- `<future module or later pass>`
