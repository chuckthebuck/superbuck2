# unbuckbot

Toolforge-first async mass rollback API for Wikimedia Commons.

## Repository layout

- `backend/app.py` – FastAPI application (OAuth, authorization, queueing)
- `config/requester_policies.json` – default requester policy/whitelist map
- `requirements.txt` – Python dependencies consumed by Toolforge Buildpacks
- `toolforge/start.sh` – application start script (optionally runs tests first)
- `userscript/mass-rollback.user.js` – Commons userscript client

## Toolforge deploy (Build Service)

Do **not** run `pip install` in your Toolforge webservice container. Dependencies should be installed by Toolforge Buildpacks from `requirements.txt` during build.

1. Enter your tool checkout and copy env config:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set at minimum:
   - `OAUTH_CLIENT_ID`
   - `OAUTH_CLIENT_SECRET`
   - `OAUTH_CALLBACK_URL` (must end in `/api/v1/auth/callback`)
   - `BOT_USERNAME`
   - `BOT_PASSWORD`
3. Build and deploy:
   ```bash
   toolforge build start
   webservice --backend kubernetes buildservice start
   ```
4. For updates, commit changes and rebuild:
   ```bash
   toolforge build start
   ```

The included `Procfile` defines both build-time dependency install and web startup:

```procfile
build: python3 -m pip install -r requirements.txt
web: ./toolforge/start.sh
```

## Local development

Use a local virtualenv when running outside Toolforge Build Service:

```bash
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
python3 -m pip install -r requirements.txt
./toolforge/start.sh
```

## Optional startup self-test

Set `SELF_TEST_ON_BOOTUP=1` to run tests before `uvicorn` starts.

```bash
SELF_TEST_ON_BOOTUP=1 ./toolforge/start.sh
```

## Tests

```bash
pytest -q
```
