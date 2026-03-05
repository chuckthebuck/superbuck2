"""Tests for auth-token handling in backend/app.py.

Focuses on the interaction with the MediaWiki action API:
  - _fetch_userinfo must forward the OAuth Bearer token to the MW action API
  - auth_callback must reject users whose token proves they lack rollback rights
  - require_session must enforce the rollback right on every protected endpoint
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.app as backend
from backend.app import (
    COMMONS_API,
    WIKIMEDIA_AUTH_BASE,
    Session,
    _fetch_userinfo,
    app,
    require_session,
)

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def _session(username="Rollbacker", rights=None, expired=False):
    import uuid
    sid = f"sess-{username}-{uuid.uuid4().hex}"
    backend.state.sessions[sid] = Session(
        session_id=sid,
        access_token="bearer-token",
        username=username,
        rights=rights if rights is not None else {"rollback"},
        expires_at=time.time() - 1 if expired else time.time() + 60,
    )
    return sid


def _httpx_client_mock(profile_payload, rights_payload):
    """Return a patched httpx.AsyncClient that captures called URLs and headers."""
    captured: list[tuple[str, dict]] = []

    async def fake_get(url, **kwargs):
        captured.append((url, kwargs))
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=profile_payload if "profile" in url else rights_payload)
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client, captured


# ── _fetch_userinfo: MW action API token forwarding ───────────────────────────

def test_fetch_userinfo_forwards_bearer_token_to_mw_action_api():
    """_fetch_userinfo must include Authorization: Bearer in the call to the
    Commons action API so the server can authenticate the request."""
    profile_payload = {"username": "TestUser"}
    rights_payload = {"query": {"userinfo": {"rights": ["read", "rollback"]}}}
    mock_client, captured = _httpx_client_mock(profile_payload, rights_payload)

    async def _run():
        with patch("backend.app.httpx.AsyncClient", return_value=mock_client):
            return await _fetch_userinfo("MY_BEARER_TOKEN")

    username, rights = asyncio.run(_run())

    assert username == "TestUser"
    assert "rollback" in rights

    # Both calls must carry Authorization: Bearer
    assert len(captured) == 2
    for url, kwargs in captured:
        auth_header = kwargs.get("headers", {}).get("Authorization")
        assert auth_header == "Bearer MY_BEARER_TOKEN", (
            f"Expected Bearer token in call to {url}"
        )


def test_fetch_userinfo_sends_rights_request_to_mw_action_api():
    """One of the two _fetch_userinfo calls must target COMMONS_API (action=query)."""
    profile_payload = {"username": "TestUser"}
    rights_payload = {"query": {"userinfo": {"rights": ["rollback"]}}}
    mock_client, captured = _httpx_client_mock(profile_payload, rights_payload)

    async def _run():
        with patch("backend.app.httpx.AsyncClient", return_value=mock_client):
            return await _fetch_userinfo("TOKEN")

    asyncio.run(_run())

    action_api_calls = [url for url, _ in captured if COMMONS_API in url]
    assert action_api_calls, "Expected at least one call to the Commons action API"


def test_fetch_userinfo_extracts_rights_from_mw_action_api_response():
    """_fetch_userinfo must parse the nested rights list returned by the MW API."""
    profile_payload = {"username": "PowerUser"}
    rights_payload = {"query": {"userinfo": {"rights": ["read", "edit", "rollback", "patrol"]}}}
    mock_client, _ = _httpx_client_mock(profile_payload, rights_payload)

    async def _run():
        with patch("backend.app.httpx.AsyncClient", return_value=mock_client):
            return await _fetch_userinfo("TOKEN")

    _, rights = asyncio.run(_run())
    assert {"read", "edit", "rollback", "patrol"} == rights


def test_fetch_userinfo_raises_when_username_missing_in_api_response():
    """_fetch_userinfo must raise RuntimeError when the profile response has no
    username field (e.g. token is invalid / expired)."""
    profile_payload = {}  # no "username"
    rights_payload = {"query": {"userinfo": {"rights": []}}}
    mock_client, _ = _httpx_client_mock(profile_payload, rights_payload)

    async def _run():
        with patch("backend.app.httpx.AsyncClient", return_value=mock_client):
            await _fetch_userinfo("BAD_TOKEN")

    with pytest.raises(RuntimeError, match="username"):
        asyncio.run(_run())


# ── auth_callback: rejects tokens without rollback right ─────────────────────

def test_auth_callback_rejects_user_without_rollback_right():
    """auth_callback must return 403 when the token belongs to an account that
    does not have the rollback right on Commons."""
    # Seed a valid OAuth state so the state-check passes
    backend.state.oauth_states["csrf-state-abc"] = time.time() + 600

    profile_payload = {"username": "RegularUser"}
    # No "rollback" in rights
    rights_payload = {"query": {"userinfo": {"rights": ["read", "edit"]}}}
    token_payload = {"access_token": "live-token", "expires_in": 3600}

    async def fake_post(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=token_payload)
        return resp

    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(
            return_value=profile_payload if "profile" in url else rights_payload
        )
        return resp

    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=fake_post)
    mock_http.get = AsyncMock(side_effect=fake_get)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.httpx.AsyncClient", return_value=mock_http), \
         patch("backend.app._oauth_client", return_value=("cid", "csec", "http://cb")):
        resp = client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "csrf-state-abc"},
        )

    assert resp.status_code == 403


# ── require_session: enforces rollback right ─────────────────────────────────

def test_require_session_rejects_unauthenticated_request():
    """A request without a session cookie must receive 401."""
    resp = client.post(
        "/api/v1/jobs",
        json={"requested_by": "x", "items": [{"title": "File:T.jpg", "user": "V"}]},
    )
    assert resp.status_code == 401


def test_require_session_rejects_expired_session():
    """An expired session must be rejected with 401."""
    backend.REQUESTER_POLICIES = {
        "OldUser": backend.RequesterPolicy(jobs_per_minute=3, max_items_per_job=10)
    }
    sid = _session("OldUser", expired=True)
    resp = client.post(
        "/api/v1/jobs",
        cookies={"unbuckbot_session": sid},
        json={
            "requested_by": "OldUser",
            "items": [{"title": "File:T.jpg", "user": "V"}],
        },
    )
    assert resp.status_code == 401


def test_require_session_rejects_session_missing_rollback_right():
    """A valid, unexpired session whose user lacks the rollback right gets 403."""
    backend.REQUESTER_POLICIES = {
        "NoRollback": backend.RequesterPolicy(jobs_per_minute=3, max_items_per_job=10)
    }
    sid = _session("NoRollback", rights={"read", "edit"})  # no "rollback"
    resp = client.post(
        "/api/v1/jobs",
        cookies={"unbuckbot_session": sid},
        json={
            "requested_by": "NoRollback",
            "items": [{"title": "File:T.jpg", "user": "V"}],
        },
    )
    assert resp.status_code == 403


def test_require_session_accepts_session_with_rollback_right():
    """A session whose user has rollback right must be allowed through."""
    backend.REQUESTER_POLICIES = {
        "Rollbacker": backend.RequesterPolicy(jobs_per_minute=5, max_items_per_job=20)
    }
    sid = _session("Rollbacker", rights={"read", "rollback"})
    resp = client.post(
        "/api/v1/jobs",
        cookies={"unbuckbot_session": sid},
        json={
            "requested_by": "Rollbacker",
            "items": [{"title": "File:T.jpg", "user": "V"}],
        },
    )
    # 200 = authenticated and authorized (job created)
    assert resp.status_code == 200

