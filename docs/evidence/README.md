# Evidence

<!-- M0 Foundation: documentation lane for evidence guidance and indexes. -->

Use this folder for project-level evidence guidance or indexes when evidence spans modules.

All concrete test artefacts belong under the root `tests/` tree:

- `tests/scripts/` for evidence runners and helper scripts.
- `tests/results/` for raw output, checklists, screenshots, JSON summaries, and Markdown evidence indexes.
- `tests/input/` for local real-data fixtures.

Do not create new module-local `test-results/` folders under `modules/` or `apps/`. Screenshot evidence should use actual Windows browser or terminal captures when screenshots are required.
