---
name: module-file-tagging
description: Add a consistent module tag and short purpose comment to new capstone project files. Use when creating files for Module 1 or any later capstone module, including Python, Markdown, config, SQL, migration, test, script, frontend, and documentation files.
---

# Module File Tagging

## Overview

Apply concise module start/end markers to every new file created for a capstone module and to meaningful new code or documentation sections added to existing files. Include the module code/name and one short sentence describing what the file or added section is for.

## Required Format

For Module 1, use this module label:

```text
M1 - User Access Management
```

For later modules, adapt the label to the module code and approved module name, for example:

```text
M2 - Manual Document Upload
```

## Comment Rules

- Add a start tag at the top of each newly created file when the file type supports comments.
- Add a matching end tag at the bottom of each newly created file when the file type supports comments.
- Add a start tag immediately before meaningful new code, config, schema, migration, route, test, or documentation sections added to an existing file.
- Add a matching end tag immediately after the added block.
- The start tag must include the word `Start`, the module label, and one short purpose line.
- The end tag must include the module code and the word `End`; for Module 1, `M1 End` is sufficient.
- Treat existing top-of-file module tags or docstrings as file headers. Do not change, replace, or upgrade an existing file header tag just because the file is edited for a later module.
- In existing files, tag the smallest meaningful added or modified block with its own start/end pair near the changed lines.
- When a module replaces an existing text or code line in a commentable file, keep the prior line commented out inside the tagged block and write the replacement directly below it.
- Keep the commented prior line close to the replacement so the module update is reviewable without Git history.
- Keep the purpose specific to the file, not the whole module.
- Use the native comment syntax for the file type.
- Do not add the tag to generated cache files, binary assets, screenshots, lockfiles, or files where comments are unsupported.
- Do not tag formatting-only changes or generated edits where comments are unsupported.
- In project module files, tag added or modified imports and one-line code changes when they are part of the module work and the file type supports comments.
- Do not repeatedly tag every line in a contiguous added block. One start/end pair should cover the related block.
- When adding to an existing tagged block, reuse the existing nearby tag if it clearly applies.
- When editing existing code inside an older section, do not imply the whole section was created for the module. Tag only the changed block when practical.

## Examples

Python:

```python
# M1 - User Access Management Start
# Defines authentication routes for login and current-user access.

...

# M1 End
```

Markdown:

```markdown
<!-- M1 - User Access Management Start -->
<!-- Specifies user login, roles, permissions, and protected access requirements. -->

...

<!-- M1 End -->
```

Environment example:

```dotenv
# M1 - User Access Management Start
# Documents authentication and PostgreSQL settings for local development.

...

# M1 End
```

SQL:

```sql
-- M1 - User Access Management Start
-- Creates the users table for authenticated application access.

...

-- M1 End
```

YAML:

```yaml
# M1 - User Access Management Start
# Configures migration tooling for user account tables.

...

# M1 End
```

JavaScript or TypeScript:

```ts
// M1 - User Access Management Start
// Provides client helpers for authenticated API requests.

...

// M1 End
```

Added block inside an existing Python file:

```python
"""Existing file header remains unchanged."""

# M1 - User Access Management Start
# Requires an authenticated active user for protected routes.
def get_current_active_user(...):
    ...
# M1 End
```

Modified block inside an existing file with an older module header:

```python
"""M0 Foundation: shared API error definitions."""

class ErrorType(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"

    # M1 - User Access Management Start
    # Adds authentication and authorization error identifiers.
    INVALID_TOKEN = "INVALID_TOKEN"
    FORBIDDEN = "FORBIDDEN"
    # M1 End
```

Updated line inside an existing Python file:

```python
# M1 - User Access Management Start
# Changes the default database target for Module 1 user storage.
# database_url: str = "sqlite:///./stats_ingestion.db"
database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/stats_ingestion"
# M1 End
```

Added block inside an existing Markdown file:

```markdown
<!-- M1 - User Access Management Start -->
<!-- Documents validation rules for user account fields. -->
## User Field Validation Rules

...

<!-- M1 End -->
```
