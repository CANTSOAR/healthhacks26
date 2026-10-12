"""Live simulations and the run registry.

A `Run` owns one HospitalSim (batch 1, CPU) and a lock. Everything that touches the simulator - the
websocket tick loop and the entity routes - takes `run.lock` first.
"""
from __future__ import annotations

import threading
import time
import uuid

from . import cache, catalog, managers

GRACE_S = 600.0            # a run outlives its socket by this long, paused at its tick, and can be re-attached
MAX_IDLE_RUNS = 12          # detached runs kept at most (oldest go first)
LATENT_KEYS = ("true_acuity", "severity", "latent_truth", "true_disposition")
INJECT = {
    "flu_surge": dict(type="flu_wave"),
    "mass_casualty": dict(type="mass_casualty"),
    "ct_outage": dict(type="equipment_outage", equipment="ct"),
    "rn_callouts": dict(type="staff_callouts", roles=["rn"]),
}
INJECT_REQUIRED = {
    "flu_wave": ["arrival_multiplier", "respiratory_share_uplift", "staff_absence_multiplier", "duration_days"],
    "mass_casualty": ["extra_patients", "window_min", "acuity_mix"],
    "equipment_outage": ["equipment", "units_down", "duration_hours"],
    "staff_callouts": ["absence_multiplier", "duration_days"],
}

_reg_lock = threading.RLock()
_runs: dict[str, "Run"] = {}


def sim_available() -> tuple[bool, str | None]:
    try:
        import sim  # noqa: F401
        from sim import HospitalSim, load_scenario  # noqa: F401
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def _f(v):
    """First element of a [B] tensor (or a plain number) as a python number."""
    try:
        if hasattr(v, "flatten"):
            v = v.flatten()[0]
        if hasattr(v, "item"):
            v = v.item()
    except Exception:  # noqa: BLE001
        return None
    return v


def public_live(d: dict) -> dict:
    """Live state without the latent truth (contracts/api.md: never the latent truth itself)."""
    return {k: v for k, v in (d or {}).items() if k not in LATENT_KEYS}


_scn_cache: dict[tuple, object] = {}


def _stamp() -> tuple:
    from .paths import ROOT, catalog_dir
    out = []
    for d, pat in ((catalog_dir(), "*.yaml"), (catalog_dir() / "hospitals", "*"), (ROOT / "sim" / "scenarios", "*.yaml")):
        if d.exists():
            for f in sorted(d.glob(pat)):
                try:
                    st = f.stat()
                    out.append((f.name, st.st_mtime_ns, st.st_size))
                except OSError:
                    pass
    return tuple(out)


def scenario_config(scenario: str, hospital_id: str | None = None):
    """load_scenario with a cache keyed by the catalog/scenario file times: parsing the catalog YAML takes about a
    second, and the web app waits only 2.5 s for the header. Each run gets its own deep copy (runs append events)."""
    import copy
    from sim import load_scenario
    key = (scenario, hospital_id or "", _stamp())
    with _reg_lock:
        scn = _scn_cache.get(key)
    if scn is None:
        scn = load_scenario(scenario, overrides={"hospital_id": hospital_id}) if hospital_id else load_scenario(scenario)
        with _reg_lock:
            for k in [k for k in _scn_cache if k[:2] == key[:2]]:
                del _scn_cache[k]
            _scn_cache[key] = scn
            if not hospital_id and getattr(scn, "hospital_id", None):
                _scn_cache[(scenario, str(scn.hospital_id), key[2])] = scn   # the web app always names the hospital
    try:
        return copy.deepcopy(scn)
    except Exception:  # noqa: BLE001 - not copyable: fall back to a fresh load
        return load_scenario(scenario, overrides={"hospital_id": hospital_id}) if hospital_id else load_scenario(scenario)


def warm() -> None:
    """Ahead of the first socket: import torch and the simulator, parse every scenario, load one rl policy."""
    try:
        Run("normal_week", seed=0, hospital_id=None).advance(1)
        from sim import list_scenarios
        for sc in list_scenarios():
            try:
                scenario_config(sc["id"])
            except Exception:  # noqa: BLE001
                pass
        for m in managers.list_managers():
            if m["id"] != "human" and m.get("available"):
                managers.load_manager(m["id"])
                break
    except Exception:  # noqa: BLE001
        pass


class Run:
    def __init__(self, scenario: str = "normal_week", seed: int = 0, hospital_id: str | None = None, manager: str = "human",
                 days: int | None = None):
        from sim import HospitalSim
        self.run_id = "run-" + uuid.uuid4().hex[:10]
        self.lock = threading.RLock()
        self.b = 0
        self.notes: list[str] = []
        scn = None
        if hospital_id:
            try:
                scn = scenario_config(scenario, hospital_id)
            except KeyError:
                raise
            except Exception as e:  # noqa: BLE001 - unknown hospital: keep the scenario's own
                self.notes.append(f"hospital '{hospital_id}' could not be loaded ({type(e).__name__}: {str(e)[:120]}); "
                                  "using the scenario's default hospital")
        if scn is None:
            scn = scenario_config(scenario)
        self.scenario = scenario
        self.seed = int(seed)
        self.sim = HospitalSim(scn, batch_size=1, device="cpu", seed=self.seed)
        self.hospital_id = str(getattr(scn, "hospital_id", hospital_id or ""))
        self.tph = int(getattr(self.sim, "ticks_per_step", 12))
        self.tick_minutes = int(getattr(self.sim, "tick_minutes", 5))
        self.spec = cache.clean(self.sim.action_spec())
        self.heads = {h["name"]: h for h in self.spec}
        self.t = int(_f(self.sim.t) or 0)
        self.max_ticks = int(days) * 24 * self.tph if days else None
        self.pending: dict[str, int] = {}
        self.policy = None
        self.manager = dict(managers.HUMAN)
        self.layout_version = None
        self.finished = False
        self.connected = True
        self.created = self.last_seen = time.time()
        self.speed, self.paused = 12.0, False   # remembered across sockets so an attach resumes as it was
        self.owner = None                       # the websocket session driving this run
        self.clock = dict(day=0, minute_of_day=0, dow=0)
        if manager and manager != "human":
            self.set_manager(manager)

    # ---------------------------------------------------------------- messages
    def header(self) -> dict:
        with self.lock:
            lay = self.sim.layout(self.b)
            self.layout_version = lay.get("version")
            scn = self.sim.scn
            return dict(type="header", attached=False, speed=self.speed, paused=self.paused, t=self.t, run_id=self.run_id, scenario=self.scenario, seed=self.seed, hospital_id=self.hospital_id,
                        manager=self.manager, tick_minutes=self.tick_minutes, enums=self.sim.enums, layout=lay,
                        action_spec=self.spec, metric_defs=getattr(scn, "metric_defs", None) or (cache.load(_metrics_path()) or {}).get("metrics", {}),
                        ticks_per_hour=self.tph, synthetic=True, notes=self.notes)

    def mask(self) -> dict:
        return {k: bool(_f(v)) for k, v in self.sim.action_mask().items()}

    def hour_msg(self, metrics: dict | None = None, ack: bool = False) -> dict:
        with self.lock:
            m = dict(type="hour", t=self.t, metrics=metrics or {}, pending=dict(self.pending), mask=self.mask(),
                     manager=self.manager["id"])
            if ack:
                m["ack"] = True   # sent in reply to action/manager messages, not at an hour boundary: metrics is empty
            return m

    def summary(self, final: bool = False) -> dict:
        with self.lock:
            s = {k: _f(v) for k, v in self.sim.episode_summary().items()}
            return dict(type="summary", summary=cache.clean(s), t=self.t, days=round(self.t / (24 * self.tph), 3), final=final)

    def snapshot(self) -> dict:
        with self.lock:
            return self.sim.snapshot(self.b)

    # ---------------------------------------------------------------- control
    def set_actions(self, actions: dict) -> list[str]:
        """Merge human knob changes into the pending set. Returns error strings for rejected heads."""
        errs = []
        with self.lock:
            for head, val in (actions or {}).items():
                spec = self.heads.get(head)
                if spec is None:
                    errs.append(f"unknown action head '{head}'")
                    continue
                if isinstance(val, str) and val in spec["options"]:
                    val = spec["options"].index(val)
                if isinstance(val, bool) or not isinstance(val, int) or not 0 <= val < len(spec["options"]):
                    errs.append(f"value {val!r} is out of range for '{head}' (0..{len(spec['options']) - 1})")
                    continue
                if spec.get("implemented") is False:
                    errs.append(f"'{head}' is not implemented by the simulator yet; the setting is kept but has no effect")
                self.pending[head] = val
        return errs

    def set_manager(self, manager_id: str) -> dict:
        policy = managers.load_manager(manager_id, device="cpu")   # raises with a readable message
        info = managers.manager_info(manager_id) or dict(managers.HUMAN)
        if policy is not None:
            policy.reset(1, "cpu")
        with self.lock:
            self.policy, self.manager = policy, info
            if policy is not None:
                self.pending.clear()
        return info

    def _boundary_actions(self, errors: list):
        import torch
        if self.policy is not None:
            try:
                acts = managers.policy_act(self.policy, self.manager, self.sim)
                return {k: torch.as_tensor(v, dtype=torch.long).reshape(-1)[:1] for k, v in acts.items() if k in self.heads}
            except Exception as e:  # noqa: BLE001 - a broken policy hands control back instead of killing the run
                errors.append(f"manager '{self.manager['id']}' failed ({type(e).__name__}: {str(e)[:160]}); control returned to human")
                self.policy, self.manager = None, dict(managers.HUMAN)
                return None
        if not self.pending:
            return None
        mask = self.mask()
        take = {h: v for h, v in self.pending.items() if mask.get(h)}
        for h in take:
            del self.pending[h]
        return {h: torch.tensor([v], dtype=torch.long) for h, v in take.items()} or None

    def advance(self, n: int = 1, snapshot: bool = True) -> list[dict]:
        """Advance n ticks. Returns the messages to send, in order (hour, summary, layout, error, snapshot)."""
        out: list[dict] = []
        with self.lock:
            self.last_seen = time.time()
            for _ in range(max(1, n)):
                if self.finished:
                    break
                errors: list[str] = []
                boundary = self.t % self.tph == 0
                actions = self._boundary_actions(errors) if boundary else None
                self.sim.tick(actions)
                self.t += 1
                out += [dict(type="error", message=m) for m in errors]
                if self.t % self.tph == 0:
                    metrics = cache.clean({k: _f(v) for k, v in self.sim.metrics_last_hour().items()})
                    out.append(self.hour_msg(metrics))
                    if self.t % (24 * self.tph) == 0:
                        out.append(self.summary())
                if self.max_ticks and self.t >= self.max_ticks:
                    self.finished = True
                    out.append(self.summary(final=True))
            if snapshot:
                snap = self.sim.snapshot(self.b)
                self.clock = snap.get("clock") or self.clock
                ver = snap.get("layout_version")
                if ver is not None and self.layout_version is not None and ver != self.layout_version:
                    out.append(dict(type="layout", layout=self.sim.layout(self.b)))
                if ver is not None:
                    self.layout_version = ver
                out.append(dict(type="snapshot", snapshot=snap))
        return out

    def inject(self, event: str, params: dict | None = None) -> dict:
        """Add an exogenous scenario event starting at the next simulated hour.

        The simulator has no injection method; its scenario events are a plain list read once per simulated
        hour (HospitalSim._scenario_state), so the event is appended to this run's own ScenarioConfig.
        Parameters come from catalog/event.yaml; `params` may override them."""
        if event not in INJECT:
            raise ValueError(f"unknown event '{event}'; have {sorted(INJECT)}")
        with self.lock:
            scn = self.sim.scn
            if not isinstance(getattr(scn, "events", None), list):
                raise RuntimeError("event injection is unavailable: the simulator exposes no scenario event list")
            ev = dict(INJECT[event])
            cat = (((getattr(scn, "cat", {}) or {}).get("event") or {}).get("variants") or {}).get(ev["type"]) or {}
            base = {k: a.get("value") for k, a in (cat.get("attributes") or {}).items() if isinstance(a, dict)}
            base.update(ev)
            base.update({k: v for k, v in (params or {}).items() if k not in ("type", "start_day", "start_hour")})
            missing = [k for k in INJECT_REQUIRED[ev["type"]] if base.get(k) is None]
            if missing:
                raise RuntimeError(f"event injection is unavailable: catalog/event.yaml {ev['type']} lacks {missing}")
            hour = self.t // self.tph + 1
            base.update(start_day=hour // 24, start_hour=hour % 24, injected=True)
            base.pop("repeat_every_days", None)
            scn.events.append(base)
            return cache.clean(dict(event=event, type=ev["type"], starts_at_tick=hour * self.tph, params=base))

    # ---------------------------------------------------------------- entities
    def patient(self, patient_id: int) -> dict:
        """{live, latent_truth_available, known_state, interactions, catalog_refs, catalog}. KeyError when not in the hospital."""
        with self.lock:
            sim, b, pid = self.sim, self.b, int(patient_id)
            try:
                live = dict(sim.patient_detail(b, pid))
            except (NotImplementedError, AttributeError):
                live = self._patient_from_snapshot(pid)
            interactions = live.pop("interactions", None)
            refs = live.pop("catalog_refs", None) or []
            if interactions is None:
                interactions = self._try(lambda: sim.interaction_log(b, pid), [])
            known = self._try(lambda: sim.known_state(b, pid), None)
            truth_ok = self._try(lambda: bool(sim.latent_truth(b, pid)), False)
            pend = self._try(lambda: sim.pending_interaction(b, pid), None)
        return cache.clean(dict(live=public_live(live), latent_truth_available=bool(truth_ok), known_state=known,
                                interactions=interactions or [], pending_interaction=pend, catalog_refs=refs,
                                catalog=catalog.resolve_many(refs), synthetic=True))

    def staff(self, staff_id: str) -> dict:
        with self.lock:
            try:
                live = dict(self.sim.staff_detail(self.b, str(staff_id)))
            except (NotImplementedError, AttributeError):
                live = self._staff_from_snapshot(str(staff_id))
        refs = live.pop("catalog_refs", None) or []
        out = dict(live=live, catalog_refs=refs, catalog=catalog.resolve_many(refs), fictional=True)
        if live.get("name"):
            out["profile"] = dict(name=live["name"], role=live.get("role"), fictional=True)
        self._add_attribution(out, "staff", live)
        return cache.clean(out)

    def room(self, room_id) -> dict:
        with self.lock:
            lay, snap = self.sim.layout(self.b), self._quiet_snapshot()
        idx = next((i for i, r in enumerate(lay["rooms"]) if r["id"] == room_id or i == room_id), None)
        if idx is None:
            raise KeyError(f"room {room_id!r} is not in the layout")
        r, E = lay["rooms"][idx], self.sim.enums
        live = dict(r, index=idx)
        rs = snap.get("rooms") or {}
        if idx < len(rs.get("status", [])):
            live["status"] = E["room_status"][rs["status"][idx]]
            live["occupancy"] = rs["occupancy"][idx]
            if rs.get("queue"):
                live["queue"] = rs["queue"][idx]
        p, s = snap.get("patients") or {}, snap.get("staff") or {}
        live["patients"] = [pid for pid, ri in zip(p.get("id", []), p.get("room", [])) if ri == idx]
        live["staff"] = [sid for sid, ri in zip(s.get("id", []), s.get("room", [])) if ri == idx]
        live["equipment"] = [e["id"] for e in lay.get("equipment", []) if e.get("room") == r["id"]]
        refs = [r.get("catalog_ref") or f"space/{r['type']}"]
        return cache.clean(self._add_attribution(dict(live=live, catalog_refs=refs, catalog=catalog.resolve_many(refs)), "room", live, snap, lay))

    def equipment(self, eq_id) -> dict:
        with self.lock:
            lay, snap = self.sim.layout(self.b), self._quiet_snapshot()
        idx = next((i for i, e in enumerate(lay.get("equipment", [])) if e["id"] == eq_id or i == eq_id), None)
        if idx is None:
            raise KeyError(f"equipment {eq_id!r} is not in the layout")
        e = lay["equipment"][idx]
        live = dict(e, index=idx)
        st = (snap.get("equipment") or {}).get("status", [])
        if idx < len(st):
            live["status"] = self.sim.enums["equipment_status"][st[idx]]
        refs = [e.get("catalog_ref") or f"equipment/{e['type']}"]
        return cache.clean(self._add_attribution(dict(live=live, catalog_refs=refs, catalog=catalog.resolve_many(refs)), "equipment", live, snap, lay))

    def detail(self, kind: str, entity_id) -> dict:
        """The websocket `detail` reply."""
        if kind == "patient":
            d = self.patient(int(entity_id))
        elif kind == "staff":
            d = self.staff(str(entity_id))
        elif kind == "room":
            d = self.room(entity_id)
        elif kind == "equipment":
            d = self.equipment(entity_id)
        else:
            raise ValueError(f"unknown entity kind '{kind}'")
        cat = d.get("catalog") or {}
        refs = d.get("catalog_refs") or []
        primary = dict(cat[refs[0]]) if refs and refs[0] in cat else {}
        primary["refs"] = cat
        primary["catalog_refs"] = refs
        out = dict(type="detail", entity=dict(kind=kind, id=entity_id), live=d.get("live"), catalog=primary,
                   interactions=d.get("interactions") or [], run_id=self.run_id, t=self.t)
        for k in ("known_state", "latent_truth_available", "pending_interaction", "profile", "attribution"):
            if k in d:
                out[k] = d[k]
        return out

    # ---------------------------------------------------------------- marginal value (rl/attribution.py; simulated)
    def _add_attribution(self, out: dict, kind: str, live: dict, snap: dict | None = None, lay: dict | None = None) -> dict:
        """Adds `attribution` to an entity payload: the entity's resource class, how busy that class is right now
        and the precomputed marginal value of one unit of it at this hour. Absent when no report exists."""
        try:
            a = self._attribution(kind, live, snap, lay)
        except Exception:  # noqa: BLE001 - the inspector must never fail on an optional block
            a = None
        if a is not None:
            out["attribution"] = a
        return out

    def _attribution(self, kind: str, live: dict, snap: dict | None, lay: dict | None) -> dict | None:
        from . import attribution
        if attribution.load(self.hospital_id) is None:
            return None
        with self.lock:
            snap = snap or self._quiet_snapshot()
            lay = lay or self.sim.layout(self.b)
            group = None
            if kind == "staff":
                group = self._try(lambda: next((s.get("group") for s in self.sim._roster(self.b) if s["id"] == live.get("staff_id")), None), None)
        hour = int((snap.get("clock") or {}).get("minute_of_day", 0)) // 60
        probe = dict(live, group=group) if group else live
        uid, _ = attribution.unit_id(kind, probe, hour)
        return attribution.entity_value(self.hospital_id, kind, probe, self.scenario, hour, self._utilisation_now(uid, snap, lay))

    def _utilisation_now(self, uid: str | None, snap: dict, lay: dict) -> dict | None:
        """How busy the entity's resource class is at this instant of the run (from the live snapshot)."""
        if not uid:
            return None
        k, rooms, rs = snap.get("kpis") or {}, lay.get("rooms") or [], snap.get("rooms") or {}
        status, E = rs.get("status") or [], self.sim.enums
        OCC, CLOSED = E["room_status"].index("occupied"), E["room_status"].index("closed")

        def share(idx, what):
            st = [status[i] for i in idx if i < len(status) and status[i] != CLOSED]
            if not st:
                return dict(value=None, in_use=0, of=0, basis=f"no {what} open right now")
            n = sum(1 for x in st if x == OCC)
            return dict(value=n / len(st), in_use=n, of=len(st), basis=f"{what} occupied right now")

        if uid.startswith("provider"):
            return dict(value=k.get("md_utilization"), of=k.get("providers_on_shift"), basis="share of provider time with a patient, last simulated hour")
        if uid.startswith("nurse"):
            return dict(value=min(1.0, float(k.get("rn_utilization") or 0.0)), of=k.get("nurses_on_shift"),
                        basis="nursing care demanded / nursing time on shift, last simulated hour")
        if uid == "ward_bed":
            return dict(value=k.get("ward_occupancy"), of=k.get("ward_beds"), basis="inpatient beds occupied right now")
        if uid in ("ct_scanner", "xray_room"):
            t = "ct" if uid == "ct_scanner" else "xray"
            es, names = (snap.get("equipment") or {}).get("status") or [], E["equipment_status"]
            mine = [names[es[i]] for i, e in enumerate(lay.get("equipment") or []) if e.get("type") == t and i < len(es)]
            on = [x for x in mine if x in ("idle", "in_use")]
            n = sum(1 for x in on if x == "in_use")
            return dict(value=(n / len(on) if on else None), in_use=n, of=len(on), basis=f"{t.upper() if t == 'ct' else 'X-ray'} units scanning right now, of those up and staffed")
        types = dict(bay_resus=("resus_bay",), bay_fast=("fast_track",), bay_peds=("peds_ed",), triage_station=("triage",), bay_main=("treatment_bay",),
                     bay_hall=("treatment_bay",)).get(uid)
        if types:
            hall = uid == "bay_hall"
            idx = [i for i, r in enumerate(rooms) if r.get("type") in types and (("hallway" in str(r.get("catalog_ref") or "")) == hall or uid not in ("bay_main", "bay_hall"))]
            return share(idx, dict(triage_station="triage stations", bay_hall="hallway spaces").get(uid, "spaces of this class"))
        return None

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _try(fn, default):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - optional simulator methods degrade to "not available"
            return default

    def _quiet_snapshot(self) -> dict:
        """A snapshot that does not consume the events/decisions the next streamed snapshot should carry."""
        sim, b = self.sim, self.b
        keep = None
        try:
            if getattr(sim, "record", False):
                keep = (sim._events[b][:], sim._decisions[b][:])
        except Exception:  # noqa: BLE001
            keep = None
        snap = sim.snapshot(b)
        if keep is not None:
            try:
                sim._events[b], sim._decisions[b] = keep
            except Exception:  # noqa: BLE001
                pass
        return snap

    def _patient_from_snapshot(self, pid: int) -> dict:
        snap, E = self._quiet_snapshot(), self.sim.enums
        p = snap["patients"]
        if pid not in p["id"]:
            raise KeyError(f"patient {pid} is not in the hospital")
        i = p["id"].index(pid)
        acu = p["acuity"][i]
        cond = E["condition_group"][p["condition"][i]]
        return dict(patient_id=pid, display_id=f"P-{pid:06d}", acuity=acu, condition_group=cond, state=E["patient_state"][p["state"][i]],
                    exit=E["patient_exit"][p["exit"][i]], room_index=p["room"][i], x=p["x"][i], z=p["z"][i], age_min=p["age_min"][i],
                    state_min=p["state_min"][i], flags=p["flags"][i], catalog_refs=[f"patient/esi{acu}", f"conditions/{cond}"], synthetic=True)

    def _staff_from_snapshot(self, sid: str) -> dict:
        snap, E = self._quiet_snapshot(), self.sim.enums
        s = snap["staff"]
        if sid not in s["id"]:
            raise KeyError(f"staff {sid} is not on shift")
        i = s["id"].index(sid)
        role = E["staff_role"][s["role"][i]]
        return dict(staff_id=sid, name=(s.get("name") or [None] * (i + 1))[i], role=role, state=E["staff_state"][s["state"][i]],
                    room_index=s["room"][i], x=s["x"][i], z=s["z"][i], catalog_refs=[f"staff/{role}"], fictional=True)

    def info(self, now: float | None = None) -> dict:
        now = now or time.time()
        return dict(run_id=self.run_id, scenario=self.scenario, seed=self.seed, hospital_id=self.hospital_id, manager=self.manager["id"],
                    manager_info=self.manager, t=self.t, clock=self.clock,
                    expires_in_s=None if self.connected else max(0, int(GRACE_S - (now - self.last_seen))),
                    connected=self.connected, speed=self.speed, paused=self.paused, finished=self.finished)


def _metrics_path():
    from .paths import CONTRACTS
    return CONTRACTS / "metrics.yaml"


# ---------------------------------------------------------------- registry
def register(run: Run) -> Run:
    with _reg_lock:
        sweep()
        _runs[run.run_id] = run
    return run


def sweep(now: float | None = None) -> list[str]:
    """Drop detached runs past their grace period, and the oldest detached runs beyond MAX_IDLE_RUNS."""
    now = now or time.time()
    gone = []
    with _reg_lock:
        for rid, r in list(_runs.items()):
            if not r.connected and now - r.last_seen > GRACE_S:
                gone.append(rid)
        idle = sorted((r for r in _runs.values() if not r.connected and r.run_id not in gone), key=lambda r: r.last_seen)
        gone += [r.run_id for r in idle[:max(0, len(idle) - MAX_IDLE_RUNS)]]
        for rid in gone:
            _runs.pop(rid)
    return gone


def get_run(run_id: str) -> Run:
    with _reg_lock:
        sweep()
        r = _runs.get(run_id)
    if r is None:
        raise KeyError(f"run '{run_id}' is not live (unknown, or expired after its socket closed)")
    return r


def disconnect(run: Run) -> None:
    """The socket went away: the run stays, paused at its current tick, until it is attached again or swept."""
    run.connected = False
    run.owner = None
    run.last_seen = time.time()


def remove(run_id: str) -> None:
    with _reg_lock:
        _runs.pop(run_id, None)


def list_runs() -> list[dict]:
    with _reg_lock:
        sweep()
        return sorted((r.info() for r in _runs.values()), key=lambda i: (not i["connected"], -(i["expires_in_s"] or 0)))


def clear() -> None:
    with _reg_lock:
        _runs.clear()
