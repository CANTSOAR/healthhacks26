"""Played resolver for the `clinician_encounter` interaction (contracts/interaction.schema.json).

Given a simulator handle (sim, b, patient_id) coded against contracts/sim_api.md:

    resolver = ClinicianEncounterResolver()
    started = resolver.start(sim, b, patient_id)          # hold_for_play -> latent_truth -> known_state -> case -> session
    ... the learner plays through the HTTP API or resolver.manager.turn / .request ...
    done = resolver.finish(started["encounter_id"], disposition="admit", orders=[...], summary="...")
                                                           # grades, builds the result, sim.apply_interaction_result(b, result)

The patient the student interviews is the patient occupying the bed: the case is generated only from that
patient's latent truth and its condition template, deterministically (same patient, same case).
The simulator never receives anything a language model computed except through the fixed result fields,
all of which are computed by deterministic code here (duration, quality) or chosen by the learner (decision).
"""
from __future__ import annotations

from typing import Any

from .session import EncounterManager, default_manager
from .store import CaseStore, default_store
from .templates import get_template, instantiate_case, playability


class ResolverError(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def _as_int(v) -> int | None:
    try:
        if hasattr(v, "ndim") and getattr(v, "ndim", 0) > 0:      # a batched tensor: take this hospital's entry
            v = v.flatten()[0]
        return int(v.item() if hasattr(v, "item") else v)
    except Exception:
        return None


class ClinicianEncounterResolver:
    interaction_type = "clinician_encounter"

    def __init__(self, store: CaseStore | None = None, manager: EncounterManager | None = None):
        self.store = store or default_store()
        self.manager = manager or default_manager()

    def build_case(self, latent_truth: dict, known_state: dict | None = None) -> dict:
        tid = str(latent_truth.get("condition_template") or latent_truth.get("condition_group") or "other_medical")
        try:
            template = get_template(tid)
        except KeyError:
            try:
                template = get_template(str(latent_truth.get("condition_group") or "other_medical"))
            except KeyError:
                template = get_template("other_medical")
        return instantiate_case(template, latent_truth, known_state)

    def playable(self, sim: Any, b: int, patient_id: int) -> dict:
        """{"playable": bool, "reason": str|None} without holding the patient: lets the UI hide or explain the Play button."""
        try:
            return playability(sim.latent_truth(b, patient_id))
        except Exception as e:  # noqa: BLE001
            return {"playable": False, "reason": f"{type(e).__name__}: {str(e)[:160]}"}

    def start(self, sim: Any, b: int, patient_id: int, run_id: str | None = None, learner: str | None = None,
              require_hold: bool = True) -> dict:
        check = playability(sim.latent_truth(b, patient_id))
        if not check["playable"]:
            raise ResolverError("this patient cannot be played: " + check["reason"], 409)
        held = bool(sim.hold_for_play(b, patient_id))
        if not held and require_hold:
            raise ResolverError(f"patient {patient_id} cannot be played right now (no clinician encounter pending or already resolved)")
        truth = sim.latent_truth(b, patient_id)
        known = dict(sim.known_state(b, patient_id) or {})
        try:                                    # the triage level the hospital view shows for this patient
            shown = sim.patient_detail(b, patient_id)
            shown = (shown.get("live") or shown).get("acuity") if isinstance(shown, dict) else None
            if isinstance(shown, int) and 1 <= shown <= 5:
                known["triage_acuity"] = shown
        except Exception:
            pass
        case = self.store.save_published(self.build_case(truth, known))
        t_start = None
        try:
            t = sim.t
            t_start = _as_int(t[b] if hasattr(t, "__getitem__") and getattr(t, "ndim", 1) > 0 else t)
        except Exception:
            t_start = None
        binding = {"run_id": run_id, "b": int(b), "patient_id": int(patient_id), "held": held}
        if t_start is not None:
            binding["t_start"] = t_start

        def writeback(result: dict) -> None:
            sim.apply_interaction_result(b, result)

        out = self.manager.start(case, sim=binding, known_state=known, writeback=writeback, learner=learner)
        out["held"] = held
        return out

    def finish(self, encounter_id: str, disposition: str | None = None, orders: list[str] | None = None, summary: str | None = None) -> dict:
        return self.manager.finish(encounter_id, disposition, orders, summary)

    def resolve(self, sim: Any, b: int, patient_id: int, script: list[str], disposition: str = "undecided",
                orders: list[str] | None = None, summary: str | None = None) -> dict:
        """Scripted play-through (tests, demos): lines starting with '!' are requests, the rest are learner turns."""
        started = self.start(sim, b, patient_id)
        eid = started["encounter_id"]
        for line in script:
            if line.startswith("!"):
                self.manager.request(eid, line[1:])
            else:
                self.manager.turn(eid, line)
        return self.finish(eid, disposition, orders, summary)
