# superbuck2 monorepo

This repository now contains the bucksaltbot rollback tool and the related Commons userscript.

- `bucksaltbot/`: Rollback queue tooling with a MariaDB/ToolsDB-backed job queue and web interface.
- `unbuckbot/userscript/`: Commons userscript that authenticates with bucksaltbot and submits rollback jobs.

## Why this top-level README exists

The subprojects each have their own runtime and deployment docs, but this file gives a single starting point for local contributors.

## Setup

For full setup instructions, see [`SETUP.md`](./SETUP.md).

Quick start:

```bash
./scripts/setup_all.sh
# Toolforge deploy using Procfile/buildpacks
./scripts/setup_all.sh --toolforge
```

## Continuous integration

GitHub Actions CI runs for bucksaltbot:

- `bucksaltbot` Python tests (`pytest`)
- `bucksaltbot` Node dependency install check (`npm ci`)

Workflow file: `.github/workflows/ci.yml`.
