from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

WIKIMEDIA_AUTH_BASE = "https://meta.wikimedia.org/w/rest.php/oauth2"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


@dataclass
class RequesterPolicy:
    jobs_per_minute: int = 3
    max_items_per_job: int = 200


def _load_requester_policies() -> dict[str, RequesterPolicy]:
    raw = os.environ.get("REQUESTER_POLICIES_JSON", "").strip()
    if not raw:
        policies_file = os.environ.get("REQUESTER_POLICIES_FILE", "config/requester_policies.json")
        if os.path.exists(policies_file):
            with open(policies_file, "r", encoding="utf-8") as handle:
                raw = handle.read().strip()

    if not raw:
        return {}

    parsed = json.loads(raw)
    policies: dict[str, RequesterPolicy] = {}
    for username, value in parsed.items():
        jobs = int(value.get("jobs_per_minute", 3))
        max_items = int(value.get("max_items_per_job", 200))
        policies[username] = RequesterPolicy(jobs_per_minute=max(jobs, 1), max_items_per_job=max(max_items, 1))
    return policies


REQUESTER_POLICIES = _load_requester_policies()
DEFAULT_POLICY = RequesterPolicy(
    jobs_per_minute=max(int(os.environ.get("DEFAULT_JOBS_PER_MINUTE", "2")), 1),
    max_items_per_job=max(int(os.environ.get("DEFAULT_MAX_ITEMS_PER_JOB", "100")), 1),
)
WHITELIST_ONLY = os.environ.get("WHITELIST_ONLY", "1") == "1"


@dataclass
class Session:
    session_id: str
    access_token: str
    username: str
    rights: set[str]
    expires_at: float


@dataclass
class RollbackTask:
    title: str
    user: str
    summary: str | None = None


@dataclass
class RollbackJob:
    id: str
    owner: str
    requested_by: str
    tasks: list[RollbackTask]
    dry_run: bool = False
    status: str = "queued"
    wiki: str = "commonswiki"
    created_at: float = field(default_factory=time.time)


class AppState:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.oauth_states: dict[str, float] = {}
        self.jobs: dict[str, RollbackJob] = {}
        self.per_user_timestamps: dict[str, deque[float]] = defaultdict(deque)


state = AppState()
app = FastAPI(title="Toolforge Commons Async Mass Rollback")


def _get_state() -> AppState:
    """Return the module-level AppState.

    auth_callback accepts a ``state`` query-parameter (the OAuth CSRF token)
    which shadows the module-level ``state`` object inside the function body.
    Using this helper avoids that name collision.
    """
    return state


class RollbackItem(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    user: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=500)


class CreateJobRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=255)
    items: list[RollbackItem] = Field(min_length=1, max_length=500)
    dry_run: bool = False


def _requester_policy(username: str) -> RequesterPolicy:
    if username in REQUESTER_POLICIES:
        return REQUESTER_POLICIES[username]
    if WHITELIST_ONLY:
        raise HTTPException(status_code=403, detail="Requester is not whitelisted for this tool")
    return DEFAULT_POLICY


async def require_session(request: Request) -> Session:
    sid = request.cookies.get("unbuckbot_session")
    if not sid or sid not in state.sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = state.sessions[sid]
    if session.expires_at <= time.time():
        state.sessions.pop(sid, None)
        raise HTTPException(status_code=401, detail="Session expired")

    if "rollback" not in session.rights:
        raise HTTPException(status_code=403, detail="Missing rollback right on Commons")

    return session


def _oauth_client() -> tuple[str, str, str]:
    client_id = os.environ.get("OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("OAUTH_CLIENT_SECRET", "")
    callback = os.environ.get("OAUTH_CALLBACK_URL", "")
    if not client_id or not client_secret or not callback:
        raise RuntimeError("Missing OAUTH_CLIENT_ID/OAUTH_CLIENT_SECRET/OAUTH_CALLBACK_URL")
    return client_id, client_secret, callback


async def _fetch_userinfo(access_token: str) -> tuple[str, set[str]]:
    async with httpx.AsyncClient(timeout=30) as client:
        profile_resp = await client.get(
            f"{WIKIMEDIA_AUTH_BASE}/resource/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_resp.raise_for_status()
        username = profile_resp.json().get("username")
        if not username:
            raise RuntimeError("OAuth profile did not include username")

        rights_resp = await client.get(
            COMMONS_API,
            params={
                "action": "query",
                "meta": "userinfo",
                "uiprop": "rights",
                "format": "json",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        rights_resp.raise_for_status()
        rights = set(rights_resp.json().get("query", {}).get("userinfo", {}).get("rights", []))

    return username, rights


@app.get("/api/v1/auth/start")
async def auth_start() -> RedirectResponse:
    client_id, _, callback = _oauth_client()
    csrf_state = secrets.token_urlsafe(24)
    state.oauth_states[csrf_state] = time.time() + 600
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback,
        "scope": "basic",
        "state": csrf_state,
    }
    return RedirectResponse(f"{WIKIMEDIA_AUTH_BASE}/authorize?{urlencode(params)}")


@app.get("/api/v1/auth/callback")
async def auth_callback(code: str, state_token: str | None = None, state: str | None = None) -> JSONResponse:
    incoming_state = state_token or state
    if not incoming_state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    app_state = _get_state()
    expires = app_state.oauth_states.pop(incoming_state, 0)
    if expires < time.time():
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    client_id, client_secret, callback = _oauth_client()
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            f"{WIKIMEDIA_AUTH_BASE}/access_token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": callback,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

    access_token = token_data["access_token"]
    expires_in = int(token_data.get("expires_in", 3600))
    username, rights = await _fetch_userinfo(access_token)
    if "rollback" not in rights:
        raise HTTPException(status_code=403, detail="Account does not have rollback right on Commons")

    sid = secrets.token_urlsafe(32)
    app_state.sessions[sid] = Session(
        session_id=sid,
        access_token=access_token,
        username=username,
        rights=rights,
        expires_at=time.time() + min(expires_in, 3600),
    )

    response = JSONResponse({"ok": True, "username": username, "wiki": "commonswiki"})
    response.set_cookie(
        "unbuckbot_session",
        sid,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=min(expires_in, 3600),
    )
    return response


@app.post("/api/v1/jobs")
async def create_job(payload: CreateJobRequest, session: Session = Depends(require_session)) -> dict[str, str]:
    if payload.requested_by != session.username:
        raise HTTPException(status_code=403, detail="requested_by must match authenticated user")

    policy = _requester_policy(session.username)
    if len(payload.items) > policy.max_items_per_job:
        raise HTTPException(status_code=400, detail=f"Too many items for requester policy ({policy.max_items_per_job})")

    now = time.time()
    recent = state.per_user_timestamps[session.username]
    while recent and recent[0] < now - 60:
        recent.popleft()
    if len(recent) >= policy.jobs_per_minute:
        raise HTTPException(status_code=429, detail=f"Submission throttled: max {policy.jobs_per_minute} jobs per minute")
    recent.append(now)

    job_id = str(uuid.uuid4())
    job = RollbackJob(
        id=job_id,
        owner=session.username,
        requested_by=payload.requested_by,
        tasks=[RollbackTask(title=i.title, user=i.user, summary=i.summary) for i in payload.items],
        dry_run=payload.dry_run,
    )
    state.jobs[job_id] = job
    return {"job_id": job_id}


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, session: Session = Depends(require_session)) -> dict[str, Any]:
    job = state.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner != session.username:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {
        "id": job.id,
        "wiki": job.wiki,
        "owner": job.owner,
        "requested_by": job.requested_by,
        "dry_run": job.dry_run,
        "status": job.status,
        "total": len(job.tasks),
    }

