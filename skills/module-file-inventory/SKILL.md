---
name: module-file-inventory
description: Create consistent file inventory summary documents for capstone modules. Use when the user asks for a Module 0-style summary, file inventory, list of created and modified files, implementation summary, or documentation of what changed for any capstone module.
---

# Module File Inventory

## Overview

Create a Markdown inventory that lists files created or modified for a capstone module and explains each change in assessment-ready language.

## File Naming

Use this pattern:

```text
docs/M<module-number>-<short-module-name>-file-inventory.md
```

Examples:

```text
docs/M0-foundation-file-inventory.md
docs/M1-user-management-file-inventory.md
```

## Required Tagging

Use the module file tagging convention if available. Wrap the whole inventory with module start/end comments.

Example:

```markdown
<!-- M1 - User Access Management Start -->
<!-- Documents the files created or modified for Module 1 user access management. -->

...

<!-- M1 End -->
```

## Standard Structure

Use the same broad shape as the Module 0 inventory:

```markdown
# M<module-number> <Module Name> File Inventory

## Summary

## Specification and Documentation

## Reusable Project Convention

## Environment Setup

## Application Configuration and Startup

## Models and Schemas

## Security and Services

## Routes

## Tests

## API Endpoints Added

## Test Results and Evidence

## Verification

## Notes
```

Omit sections that are not relevant. Add module-specific sections when helpful, such as `Database and Migrations`, `Frontend`, `Reports`, `Cloud`, or `Evidence Artefacts`.

## Table Format

For file sections, use:

```markdown
| File | Change Type | Description |
| --- | --- | --- |
| `path/to/file.py` | Created | Explains why the file exists and what it contributes to the module. |
```

Use change types consistently:

- `Created`
- `Modified`
- `Created or Modified`
- `Existing Supporting File`
- `Existing Test File`
- `Committed Separately`

## Writing Rules

- Group files by purpose, not alphabetically.
- Mention whether setup or environment documents were committed separately when relevant.
- Include endpoint tables for backend API modules.
- Include verification commands and exact result summaries.
- Keep descriptions concise but specific enough for assessment review.
- Do not include generated cache files, `__pycache__`, screenshots unless they are evidence artefacts, or transient local files.
- If Git is available, use status/diff output to avoid missing files. If Git is unavailable, use file listing and recent work context.

## Verification Section

Use this form, with fenced blocks in the final inventory:

- Heading: `## Verification`
- Sentence: `The M<module-number> <Module Name> module was verified with:`
- Command block containing the verification command, such as `pytest`
- Sentence: `Result:`
- Result block containing the exact result summary, such as `27 passed`

If tests were not run, state that plainly and explain why.
