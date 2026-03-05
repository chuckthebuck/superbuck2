# Top-level setup guide

This guide helps you run the rollback tooling in this repository.

## 1) Project map

- `bucksaltbot/` (Python + Node + Redis + MariaDB)
- `unbuckbot/userscript/` (Wikimedia Commons userscript only)

## 2) One-command setup

From repo root:

```bash
./scripts/setup_all.sh
```

Useful flags:

```bash
./scripts/setup_all.sh --no-install-deps
./scripts/setup_all.sh --no-venv
```

## 3) Setup: bucksaltbot

1. Enter directory:
   ```bash
   cd bucksaltbot
   ```
2. Create environment files:
   ```bash
   cp .env.tmpl .env
   cp replica.my.cnf.tmpl replica.my.cnf
   ```
3. Install dependencies:
   ```bash
   npm ci
   python3 -m pip install -r requirements.txt
   ```
4. Start required services (Redis + MariaDB), then start app:
   ```bash
   ./scripts/run_dev_env.sh
   ```

## 4) Setup: Commons userscript

1. Open `unbuckbot/userscript/mass-rollback.user.js`.
2. Set `TOOL_ENDPOINT` to your bucksaltbot deployment URL.
3. Install the userscript in your browser userscript manager.
4. On Commons, use the "Mass rollback" action; it authenticates with bucksaltbot and submits jobs to bucksaltbot's rollback API.
