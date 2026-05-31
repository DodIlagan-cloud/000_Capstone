# Architecture Baseline For This Pass

This pass established the baseline that is now published as:

```text
docs/architecture-hardening/current-baseline.md
```

The accepted baseline covers:

- Active architecture roots only: `apps/`, `modules/`, `contracts/`, `config/`, `infrastructure/`, `tests/`, `docs/`, and `samples/`.
- Central runtime configuration through `config/stats.runtime.json`.
- Central path resolution through `config/stats.paths.json` and `STATS_APP_ROOT`.
- Central logging governance through `config/stats.logging.json`.
- Module-local configuration as projections of the central runtime registry.
- Container-first official testing and evidence from M13 onward.
- Separate database runtime: `stats-runtime` for application/module APIs and `stats-db` for PostgreSQL locally.
- Cloud-ready target direction: app runtime, managed PostgreSQL, blob storage, and managed secrets/config.

See `../../current-baseline.md` for the current source of truth.
