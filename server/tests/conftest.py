import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# state (human runs, validation cache) goes to a temp dir; the validation baseline never spawns a process in tests
os.environ["HG_STATE_DIR"] = tempfile.mkdtemp(prefix="hg-server-state-")
os.environ["HG_VALIDATION_INPROCESS"] = "1"
os.environ["HG_NO_WARM"] = "1"
os.environ.setdefault("ENCOUNTER_DATA_DIR", tempfile.mkdtemp(prefix="hg-server-enc-"))   # keep test encounters out of data/

from fastapi.testclient import TestClient  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402
from referencing import Registry, Resource  # noqa: E402

from server import runs, validation  # noqa: E402
from server.app import app  # noqa: E402

CONTRACTS = ROOT / "contracts"


def validator(name):
    """Same approach as contracts/fixtures/make_fixture.py."""
    store = {}
    for f in CONTRACTS.glob("*.schema.json"):
        s = json.loads(f.read_text())
        store[s["$id"]] = Resource.from_contents(s)
    reg = Registry().with_resources(store.items())
    return Draft202012Validator(json.loads((CONTRACTS / name).read_text()), registry=reg)


@pytest.fixture(scope="session")
def validators():
    return {n: validator(f"{n}.schema.json") for n in ("snapshot", "layout", "rollout", "catalog")}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
    runs.clear()


@pytest.fixture(autouse=True)
def _fresh_validation():
    validation.reset()
    yield
    validation.reset()


def recv_until(ws, pred, limit=4000):
    """Read messages until pred(msg) is true; returns (that message, everything read)."""
    seen = []
    for _ in range(limit):
        m = ws.receive_json()
        seen.append(m)
        if pred(m):
            return m, seen
    raise AssertionError(f"no matching message in {limit}; types seen: {sorted({m['type'] for m in seen})}")
