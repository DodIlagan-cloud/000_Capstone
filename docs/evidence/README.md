# Evidence

<!-- M0 Foundation: documentation lane for evidence guidance and indexes. -->

Use this folder for project-level evidence guidance or indexes when evidence spans modules.

Testing and evidence are part of the build loop, not an end-of-project activity. See `docs/testing-build-loop-policy.md` for the project-wide rule and `docs/M13-container-first-testing-policy.md` for the official container-first acceptance boundary from M13 onward.

Evidence must also follow `docs/privacy-security-data-governance-policy.md`: do not expose full raw financial document text, secrets, private local paths, or unnecessary personal data in assessment artefacts.

All concrete test artefacts belong under the root `tests/` tree:

- `tests/scripts/` for evidence runners and helper scripts.
- `tests/results/` for raw output, checklists, screenshots, JSON summaries, and Markdown evidence indexes.
- `tests/input/` for local real-data fixtures.

Do not create new module-local `test-results/` folders under `modules/` or `apps/`. Screenshot evidence should use actual Windows browser or terminal captures when screenshots are required.
