"""Mounting the encounter router and giving it the live simulation.

`encounter.api.router` is mounted under /api when importable. The encounter package needs the running
simulation for `POST /api/encounters {run_id, patient_id}`; this module offers it three ways and uses
whichever the package supports (see server/README.md):

1. a hook on the package: `encounter.api.register_sim_lookup(fn)` (what encounter/api.py ships; a few other
   names are tried too, also on `encounter` itself), with fn(run_id) -> (sim, b) or None;
2. plain imports from the encounter side: `server.runs.get(run_id) -> (sim, b)` and `server.runs.lock(run_id)`,
   or `server.encounter_glue.sim_provider(run_id) -> SimHandle`;
3. no support in the router: the server's own `POST /api/encounters` handler (registered ahead of the router)
   takes the `{run_id, patient_id}` form and drives `encounter.session.EncounterManager` directly.
"""
from __future__ import annotations

import importlib
import sys
import threading

from . import runs

HOOK_NAMES = ("register_sim_lookup", "set_sim_provider", "set_run_provider", "register_sim_provider", "set_sim_registry")
ATTR_NAMES = ("sim_provider", "SIM_PROVIDER", "run_provider")
state = dict(mounted=False, hook=None, error=None, routes=0)
_lock = threading.Lock()


class SimHandle:
    """What the encounter side gets for a run: `sim` (a runs.LockedSim: thread-safe, defers early results),
    the hospital index `b`, the run id and the lock. Unpacks as `sim, b = handle`."""

    def __init__(self, run: runs.Run):
        self.run, self.run_id, self.b, self.lock = run, run.run_id, run.b, run.lock
        self.sim = runs.LockedSim(run)

    def __iter__(self):
        return iter((self.sim, self.b))

    def latent_truth(self, patient_id):
        return self.sim.latent_truth(self.b, int(patient_id))

    def known_state(self, patient_id):
        return self.sim.known_state(self.b, int(patient_id))

    def pending_interaction(self, patient_id):
        return self.sim.pending_interaction(self.b, int(patient_id))

    def hold_for_play(self, patient_id) -> bool:
        return self.sim.hold_for_play(self.b, int(patient_id))

    def release_hold(self, patient_id) -> bool:
        return self.sim.release_hold(self.b, int(patient_id))

    def apply_interaction_result(self, result: dict) -> str:
        """ "applied", or "deferred" when the patient has not reached a provider yet (see Run.apply_result)."""
        return self.sim.apply_interaction_result(self.b, result)


def sim_provider(run_id: str) -> SimHandle:
    """KeyError when the run is not live."""
    return SimHandle(runs.get_run(str(run_id)))


def sim_lookup(run_id: str):
    """The callable handed to the encounter package: (LockedSim, b) for a live run, None otherwise."""
    try:
        return runs.get(str(run_id))
    except KeyError:
        return None


def wire(*modules) -> str | None:
    """Give the encounter package our provider through whichever hook it has. Returns the hook used."""
    for mod in modules:
        if mod is None:
            continue
        for name in HOOK_NAMES:
            fn = getattr(mod, name, None)
            if callable(fn):
                try:
                    fn(sim_lookup)
                    return f"{mod.__name__}.{name}"
                except Exception:  # noqa: BLE001
                    continue
        for name in ATTR_NAMES:
            if name in vars(mod):
                setattr(mod, name, sim_lookup)
                return f"{mod.__name__}.{name}"
    return None


def try_mount(app) -> bool:
    """Mount encounter.api.router under /api once. Safe to call repeatedly; never raises."""
    with _lock:
        if state["mounted"]:
            return True
        try:
            importlib.invalidate_caches()
            for name in ("encounter.api",):
                if name in sys.modules and not hasattr(sys.modules[name], "router"):
                    del sys.modules[name]
            api = importlib.import_module("encounter.api")
            router = api.router
            before = len(app.router.routes)
            app.include_router(router, prefix="/api")
            state.update(mounted=True, error=None, routes=len(app.router.routes) - before,
                         hook=wire(api, sys.modules.get("encounter")))
            app.openapi_schema = None
            return True
        except Exception as e:  # noqa: BLE001 - the encounter package is optional
            state.update(mounted=False, error=f"{type(e).__name__}: {str(e)[:200]}")
            return False


def router_handles_sim() -> bool:
    """True when the mounted encounter router deals with `{run_id, patient_id}` itself: it took our provider
    through a hook, or its source mentions run_id (it imports server.runs on its own)."""
    if not state["mounted"]:
        return False
    if state["hook"]:
        return True
    if "self_sim" not in state:
        try:
            import inspect
            state["self_sim"] = "run_id" in inspect.getsource(sys.modules["encounter.api"])
        except Exception:  # noqa: BLE001
            state["self_sim"] = False
    return bool(state["self_sim"])


# ---------------------------------------------------------------- fallback: the server starts the encounter itself
def start_from_sim(body: dict) -> tuple[int, dict]:
    """`POST /api/encounters {run_id, patient_id}` when the encounter router has no simulator support.
    Returns (http status, json). Drives encounter.resolver.ClinicianEncounterResolver with the run's LockedSim."""
    try:
        h = sim_provider(str(body.get("run_id")))
        pid = int(body.get("patient_id"))
    except KeyError as e:
        return 404, dict(detail=str(e.args[0]))
    except (TypeError, ValueError):
        return 422, dict(detail="patient_id must be an integer")
    try:
        pend = h.pending_interaction(pid)
    except KeyError as e:
        return 404, dict(detail=str(e.args[0]))
    except (NotImplementedError, AttributeError) as e:
        return 501, dict(detail=f"the simulator does not expose the interaction contract yet: {e}")
    if pend is None:
        return 409, dict(detail=f"patient {pid} has no playable clinician encounter right now (already seen, or has left)")
    try:
        from encounter.resolver import ClinicianEncounterResolver
        resolver = ClinicianEncounterResolver()
    except Exception as e:  # noqa: BLE001
        return 503, dict(detail=f"encounter package unavailable: {type(e).__name__}: {str(e)[:200]}")
    try:
        out = resolver.start(h.sim, h.b, pid, run_id=h.run_id, learner=body.get("learner"))
    except Exception as e:  # noqa: BLE001
        h.release_hold(pid)
        status = getattr(e, "status", None)
        return (status if isinstance(status, int) else 500), dict(detail=f"{type(e).__name__}: {str(e)[:300]}")
    return 200, out


def precheck(data: dict) -> tuple[int, dict] | None:
    """`POST /api/encounters {run_id, patient_id}`: refuse a patient who cannot be played, with a readable reason.
    None = go ahead. The error shape is the encounter router's: {"detail": {"message": ...}}."""
    try:
        run = runs.get_run(str(data.get("run_id")))
    except KeyError:
        return 404, dict(detail=dict(message=f"run '{data.get('run_id')}' is not live any more", code="run_gone"))
    try:
        pid = int(data.get("patient_id"))
    except (TypeError, ValueError):
        return 422, dict(detail=dict(message="patient_id must be an integer"))
    if data.get("force"):
        return None
    try:
        ok, code, reason = run.playable(pid)
    except Exception:  # noqa: BLE001 - simulator without the needed calls: let the router decide
        return None
    if ok:
        return None
    return (404 if code == "not_in_hospital" else 409), dict(detail=dict(message=reason, code=code, playable=False, patient_id=pid))


def annotate(payload: dict, encounter_id: str | None) -> dict:
    """Add `write_back: {status, detail}` to an encounter response and make `written_back` true only when applied."""
    if not isinstance(payload, dict) or "written_back" not in payload:
        return payload
    eid = str(encounter_id or payload.get("encounter_id") or "")
    wb = runs.write_back(eid)
    if wb is None:
        fb = payload.get("feedback") if isinstance(payload.get("feedback"), dict) else {}
        from_sim = bool((payload.get("sim") or {}).get("run_id")) or bool(payload.get("written_back")) or bool(fb.get("writeback_error"))
        if payload.get("written_back"):
            wb = dict(status="applied", detail="Applied: the simulated patient continues with your decision.")
        elif fb.get("writeback_error"):
            wb = dict(status="rejected", detail="The simulation did not accept the result.", error=fb["writeback_error"])
        elif payload.get("interaction_result") is None:
            return payload                       # not finished yet: nothing to say
        else:
            wb = dict(status="not_applicable" if not from_sim else "rejected",
                      detail="This case is not a patient of a running simulation, so there is nothing to write back." if not from_sim
                      else "The simulation run is no longer available, so the result was not used.")
    payload["write_back"] = {k: wb[k] for k in ("status", "detail", "run_id", "patient_id", "error") if k in wb}
    payload["written_back"] = wb["status"] == "applied"
    return payload


class SimEncounterMiddleware:
    """ASGI middleware around the encounter routes:

    - `POST /api/encounters` with run_id + patient_id: 409 with a clear reason when the patient is not playable; when the
      encounter router has no simulator support at all, the request is answered here (start_from_sim);
    - `POST /api/encounters/{id}/finish` and `GET /api/encounters/{id}`: the JSON answer gets `write_back`
      ({status: applied | queued | rejected | not_applicable, detail}) and `written_back` is true only when applied.
    Everything else passes through untouched."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        import re
        path, method = scope.get("path", "").rstrip("/"), scope.get("method")
        if method == "POST" and path == "/api/encounters":
            await self._start(scope, receive, send)
            return
        m = re.fullmatch(r"/api/encounters/([^/]+)(/finish)?", path)
        if m and ((method == "POST" and m.group(2)) or (method == "GET" and not m.group(2))):
            await self._annotated(scope, receive, send, m.group(1))
            return
        await self.app(scope, receive, send)

    async def _start(self, scope, receive, send):
        import asyncio
        import json
        from starlette.responses import Response
        from . import cache
        body, more = b"", True
        while more:
            msg = await receive()
            if msg["type"] != "http.request":
                break
            body += msg.get("body", b"")
            more = msg.get("more_body", False)
        try:
            data = json.loads(body or b"null")
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("run_id") is not None and data.get("patient_id") is not None:
            refused = await asyncio.to_thread(precheck, data)
            if refused is None and not router_handles_sim():
                refused = await asyncio.to_thread(start_from_sim, data)
            if refused is not None:
                await Response(cache.dumps(refused[1]), status_code=refused[0], media_type="application/json")(scope, receive, send)
                return
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        await self.app(scope, replay, send)

    async def _annotated(self, scope, receive, send, encounter_id: str):
        import asyncio
        import json
        from . import cache
        start, chunks = None, []

        async def capture(msg):
            nonlocal start
            if msg["type"] == "http.response.start":
                start = msg
                return
            if msg["type"] != "http.response.body":
                await send(msg)
                return
            chunks.append(msg.get("body", b""))
            if msg.get("more_body"):
                return
            body = b"".join(chunks)
            ctype = dict(start.get("headers") or []).get(b"content-type", b"")
            if start["status"] == 200 and ctype.startswith(b"application/json"):
                try:
                    data = json.loads(body)
                    body = cache.dumps(await asyncio.to_thread(annotate, data, encounter_id)).encode()
                except Exception:  # noqa: BLE001 - never break the encounter's own answer
                    pass
            headers = [(k, v) for k, v in (start.get("headers") or []) if k.lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode()))
            await send(dict(start, headers=headers))
            await send({"type": "http.response.body", "body": body, "more_body": False})
        await self.app(scope, receive, capture)
