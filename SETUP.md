# Top-level setup guide

This guide helps you run one or both projects in this repository.

## 1) Project map

- `bucksaltbot/` (Python + Node + Redis + MariaDB)
- `unbuckbot/` (Python/FastAPI; Toolforge-oriented)

## 2) Setup: bucksaltbot

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

## 3) Setup: unbuckbot

1. Enter directory:
   ```bash
   cd unbuckbot
   ```
2. Prepare Python environment and env vars:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   cp .env.example .env
   ```
3. Install dependencies and run:
   ```bash
   python3 -m pip install -r requirements.txt
   ./toolforge/start.sh
   ```

## 4) Database isolation verification (separate directories)

The repository layout itself does not cause DB conflicts; configuration does.

### What was verified

- `bucksaltbot` database connections are explicit and scoped to:
  - host from `cnf.py` config (`localhost` / `mariadb` / Toolforge host), and
  - database name `<username>__match_and_split` in `toolsdb.py`.
- `unbuckbot` has no SQL/SQLite initialization in `backend/app.py`; it uses in-memory state containers (`sessions`, `jobs`, etc.).

### Practical implication

Running both directories side by side is safe from accidental shared-DB collisions unless you manually point both apps at the same external service and add new overlapping schema behavior.

### Quick checks you can rerun

From repo root:

```bash
rg -n "database=|CREATE DATABASE|\.db|sqlite|sqlalchemy" bucksaltbot unbuckbot
pytest -q bucksaltbot/tests/test_toolsdb.py
```

These checks confirm explicit DB naming in `bucksaltbot` and expected DB helper behavior.
