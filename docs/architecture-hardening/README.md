# Architecture Hardening

This folder records project-level architecture sanity checks for the Stats capstone.

Architecture hardening passes are not feature modules. They exist to keep the specs, configuration surface, runtime rules, logging rules, database boundary, and container-first testing baseline clean before later modules continue.

## How To Use This Folder

- `current-baseline.md` is the latest accepted architecture baseline.
- `passes/` contains dated hardening passes with their own inventory, validation plan, and results.
- Future module chats should read `current-baseline.md` before changing architecture-sensitive behavior.
- When a future architecture decision changes the baseline, create a new dated pass folder and update `current-baseline.md`.

## Current Passes

| Pass | Purpose |
| --- | --- |
| `passes/2026-05-30-architecture-config-logging/` | Establishes the active architecture baseline, central runtime registry, central path registry, central logging registry, and validation tests. |

## Governance Rule

Specs drive development. If a decision changes the architecture itself, update the affected specs and the current baseline first, then resume implementation.
