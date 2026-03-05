# superbuck2 monorepo

This repository contains two related rollback tools:

- `bucksaltbot/`: Match-and-split and rollback queue tooling with a MariaDB/ToolsDB-backed job queue.
- `unbuckbot/`: Async rollback API service (FastAPI) with in-memory job/session state.

## Why this top-level README exists

The subprojects each have their own runtime and deployment docs, but this file gives a single starting point for local contributors working across both directories.

## Database separation summary

There is no shared local database file across the two directories:

- `bucksaltbot` connects to MariaDB/ToolsDB and scopes its schema to `<username>__match_and_split`.
- `unbuckbot` currently does not initialize SQL/SQLite storage; runtime state is held in memory.

Because of that split, keeping both projects in separate directories does **not** introduce cross-directory database collisions by default.

For full setup instructions, see [`SETUP.md`](./SETUP.md).

## Continuous integration

GitHub Actions CI now runs across the whole monorepo:

- `bucksaltbot` Python tests (`pytest`)
- `bucksaltbot` Node dependency install check (`npm ci`)
- `unbuckbot` Python tests (`pytest`)

Workflow file: `.github/workflows/ci.yml`.
