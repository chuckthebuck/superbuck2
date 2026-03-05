import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# In minimal local environments, unbuckbot runtime deps may be absent.
# Skip this test package instead of failing during collection.
try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    pytest.skip("unbuckbot test deps are not installed (missing fastapi)", allow_module_level=True)

# httpx is patched in tests; provide a tiny placeholder so backend imports cleanly
# when this optional dependency is missing locally.
try:
    import httpx  # noqa: F401
except ModuleNotFoundError:
    class _HttpxPlaceholderClient:
        def __init__(self, *args, **kwargs):
            pass

    sys.modules["httpx"] = SimpleNamespace(AsyncClient=_HttpxPlaceholderClient)

import backend.app as backend
from backend.app import AppState


@pytest.fixture(autouse=True)
def reset_backend_state():
    backend.state = AppState()
    backend.REQUESTER_POLICIES = {}
    backend.WHITELIST_ONLY = True
    yield
