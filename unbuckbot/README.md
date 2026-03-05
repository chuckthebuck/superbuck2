# unbuckbot userscript

This directory now contains only the Wikimedia Commons userscript that submits rollback jobs to the `bucksaltbot` API.

## What was removed

The legacy `unbuckbot` FastAPI backend and related tests/configuration were removed. Rollback job creation, queueing, and execution now live in `bucksaltbot`.

## Userscript

- `userscript/mass-rollback.user.js` – Commons userscript client

The userscript opens the bucksaltbot login flow and submits jobs to:

- `GET /login?referrer=/rollback-queue`
- `POST /api/v1/rollback/jobs`

Set `TOOL_ENDPOINT` in the userscript to your bucksaltbot deployment URL.
