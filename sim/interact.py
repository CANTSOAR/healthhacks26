"""The interaction contract on the simulator side (contracts/interaction.schema.json).

latent truth, known state, hold-for-play and played write-back. Plain python on one hospital
of the batch; the tick path only sees the tensors these functions write.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

CAT_OK = ["identity", "chief_complaint", "hpi", "pmh", "medications", "allergies", "social", "family", "ros", "exam",
          "vitals", "lab", "imaging", "diagnosis", "risk", "concealed"]
_TEMPLATES: dict = {}


def _u(seed: int, tag: str) -> float:
    h = hashlib.sha256(f"{seed}:{tag}".encode()).digest()
    return (int.from_bytes(h[:8], "big") + 0.5) / float(1 << 64)


def _template(group: str):
    path = Path(__file__).resolve().parent.parent / "catalog" / "conditions" / f"{group}.yaml"
    key = (str(path), path.stat().st_mtime if path.exists() else None)
    if _TEMPLATES.get(group, (None, None))[0] != key:
        data = None
        if path.exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
            except Exception:
                data = None
        _TEMPLATES[group] = (key, data if isinstance(data, dict) else None)
    return _TEMPLATES[group][1]


def _find_facts(tpl):
    """Locate the fact list in a condition template, whatever its exact nesting."""
    if not isinstance(tpl, dict):
        return []
    f = tpl.get("facts")
    if isinstance(f, dict):
        f = [dict(v, fact_id=v.get("fact_id", v.get("id", k))) if isinstance(v, dict) else dict(fact_id=k, value=v) for k, v in f.items()]
    if isinstance(f, list):
        return [x for x in f if isinstance(x, dict)]
    for v in tpl.values():
        if isinstance(v, dict):
            r = _find_facts(v)
            if r:
                return r
    return []


def _pick_value(item: dict, seed: int, severity: float, fid: str):
    sev_i = 0 if severity < 1 / 3 else (1 if severity < 2 / 3 else 2)
    for k in ("by_severity", "value_by_severity", "severity_values"):
        v = item.get(k)
        if isinstance(v, dict) and v:
            for name in (("low", "mild"), ("moderate", "medium", "mid"), ("high", "severe"))[sev_i]:
                if name in v:
                    return _pick_value(dict(value=v[name]) if not isinstance(v[name], dict) else v[name], seed, severity, fid)
            vals = list(v.values())
            return vals[min(len(vals) - 1, sev_i * len(vals) // 3)]
        if isinstance(v, list) and v:
            return v[min(len(v) - 1, int(severity * len(v)))]
    for k in ("options", "values", "choices", "variants"):
        v = item.get(k)
        if isinstance(v, list) and v:
            return v[int(_u(seed, fid) * len(v)) % len(v)]
    rngv = item.get("range")
    lo, hi = (rngv[0], rngv[1]) if isinstance(rngv, (list, tuple)) and len(rngv) == 2 else (item.get("low"), item.get("high"))
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        w = _u(seed, fid)
        if item.get("severity_scaled", item.get("scale_with_severity", False)):
            w = min(1.0, max(0.0, 0.7 * severity + 0.3 * w))
        val = lo + (hi - lo) * w
        return int(round(val)) if isinstance(lo, int) and isinstance(hi, int) else round(val, 2)
    if "value" in item:
        v = item["value"]
        if isinstance(v, dict) and ("options" in v or "range" in v or "by_severity" in v):
            return _pick_value(v, seed, severity, fid)
        return v
    for k in ("text", "statement", "finding", "label", "description"):
        if k in item:
            return item[k]
    return None


class InteractMixin:
    # ---- latent truth ---------------------------------------------------------------------
    def latent_truth(self, b: int, patient_id: int) -> dict:
        s = self._slot(b, patient_id)
        if s is None:
            raise KeyError(f"patient {patient_id} is not in hospital {b}")
        E, p = self.enums, self.p
        g = lambda k: p[k][b, s].item()   # noqa: E731
        seed = int(g("pseed")) & 0x7FFFFFFF
        group = E["condition_group"][int(g("cond"))]
        sev = round(float(g("sev")), 4)
        acu = int(g("acu"))
        band = int(g("age"))
        lo, hi = [(1, 17), (18, 44), (45, 64), (65, 92)][band]
        age = lo + int(_u(seed, "age") * (hi - lo + 1))
        sex = "female" if _u(seed, "sex") < 0.5 else "male"
        needs_bits = int(g("needs"))
        needs = [nm for bit, nm in ((1, "xray"), (2, "ct"), (4, "lab")) if needs_bits & bit]
        tdisp = ["discharge", "admit", "transfer"][int(g("tdisp"))]
        tpl = _template(group)
        facts = []
        diagnosis = group.replace("_", " ")
        if tpl:
            # preferred: the encounter engine's own sampler, so the case a student plays has exactly these values
            try:
                from encounter.templates import sample_fact_values
                got = sample_fact_values(group, sev, seed, age, sex)
                facts = [f for f in got if isinstance(f, dict) and str(f.get("fact_id", "")).startswith("f.") and f.get("category") in CAT_OK]
            except Exception:
                facts = []
            dx = tpl.get("diagnoses") or tpl.get("diagnosis_options")
            band = "mild" if sev < 1 / 3 else ("moderate" if sev < 2 / 3 else "severe")
            banded = [d for d in dx if isinstance(d, dict) and d.get("band") == band] if isinstance(dx, list) else []
            if banded:
                diagnosis = str(banded[0].get("diagnosis") or banded[0].get("label") or diagnosis)
            elif isinstance(dx, list) and dx:
                d = dx[min(len(dx) - 1, int(sev * len(dx)))] if tpl.get("diagnoses_ordered_by_severity") else dx[int(_u(seed, "dx") * len(dx)) % len(dx)]
                diagnosis = d.get("label", d.get("name", d.get("id", diagnosis))) if isinstance(d, dict) else str(d)
            for item in ([] if facts else _find_facts(tpl)):
                fid = str(item.get("fact_id") or item.get("id") or "")
                if not fid:
                    continue
                cat = item.get("category")
                if cat not in CAT_OK:
                    cat = fid.split(".")[1] if fid.startswith("f.") and fid.split(".")[1] in CAT_OK else "hpi"
                if not fid.startswith("f."):
                    fid = f"f.{cat}.{fid}"
                pr = item.get("p", item.get("prob", item.get("probability", item.get("prevalence"))))
                if isinstance(pr, (int, float)) and _u(seed, "p:" + fid) >= pr:
                    continue
                val = _pick_value(item, seed, sev, fid)
                f = dict(fact_id=fid, category=cat, value=val)
                if isinstance(item.get("unit"), str):
                    f["unit"] = item["unit"]
                if isinstance(item.get("critical"), bool):
                    f["critical"] = item["critical"]
                db = item.get("discoverable_by")
                if isinstance(db, list):
                    f["discoverable_by"] = [str(x) for x in db]
                facts.append(f)
        base = [
            dict(fact_id="f.identity.age", category="identity", value=age, unit="years", discoverable_by=["triage", "clinician_encounter"]),
            dict(fact_id="f.identity.sex", category="identity", value=sex, discoverable_by=["triage", "clinician_encounter"]),
            dict(fact_id="f.chief_complaint.condition_group", category="chief_complaint", value=group, discoverable_by=["triage", "clinician_encounter"]),
            dict(fact_id="f.risk.severity_index", category="risk", value=sev, critical=True, discoverable_by=["clinician_encounter"]),
            dict(fact_id="f.risk.true_disposition", category="risk", value=tdisp, critical=True, discoverable_by=["clinician_encounter", "disposition"]),
        ]
        for nm in needs:
            base.append(dict(fact_id=f"f.{'lab' if nm == 'lab' else 'imaging'}.needs_{nm}", category="lab" if nm == "lab" else "imaging",
                             value=True, critical=True, discoverable_by=["clinician_encounter"]))
        have = {f["fact_id"] for f in facts}
        facts = facts + [f for f in base if f["fact_id"] not in have]
        return dict(patient_id=int(patient_id), seed=seed, condition_group=group,
                    condition_template=group if tpl else "generic",
                    diagnosis=diagnosis, severity=sev, acuity=acu, age=age, sex=sex,
                    arrival_mode=E["arrival_mode"][int(g("mode"))], payer=E["payer"][int(g("payer"))],
                    true_disposition=tdisp, needs=needs, facts=facts)

    # ---- known state ----------------------------------------------------------------------
    def known_state(self, b: int, patient_id: int) -> dict:
        from .engine import S_PROV, S_TRI, S_WT, S_TEST, S_WTEST, S_WALK
        truth = self.latent_truth(b, patient_id)
        s = self._slot(b, patient_id)
        E, p = self.enums, self.p
        g = lambda k: p[k][b, s].item()   # noqa: E731
        st = int(g("state"))
        seed = truth["seed"]
        triaged = not (st == S_WT or st == S_TRI) or int(g("mode")) != 0
        seen = g("t_seen") >= 0
        enc_done = seen and not (st == S_PROV and int(g("phase")) == 1)
        known = []
        played = self._played[b].get(int(patient_id))

        def disc(f, kind, cats):
            db = f.get("discoverable_by")
            return (kind in db) if db else (f["category"] in cats)

        if triaged:
            known += [f["fact_id"] for f in truth["facts"] if disc(f, "triage", ("identity", "chief_complaint", "vitals"))]
        if enc_done:
            if played is not None:
                known += [x for x in played.get("information_gained", []) if isinstance(x, str)]
            else:
                q = float(g("enc_q"))
                cand = [f for f in truth["facts"] if disc(f, "clinician_encounter", ("hpi", "pmh", "medications", "allergies", "social", "family", "ros", "exam", "risk"))]
                known += [f["fact_id"] for f in cand if _u(seed, "k:" + f["fact_id"]) < q]
        needs_bits = int(g("needs"))
        orders = [nm for bit, nm in ((1, "xray"), (2, "ct"), (4, "lab")) if needs_bits & bit] if enc_done else []
        ready = []
        if enc_done and float(g("res_left")) <= 0:
            img_pending = (needs_bits & 3) and (st in (S_WTEST, S_TEST) or (st == S_WALK and int(g("next_state")) == S_TEST))
            ready = [o for o in orders if o == "lab" or not img_pending]
            cats = set(["lab"] if "lab" in ready else []) | set(["imaging"] if any(o in ready for o in ("xray", "ct")) else [])
            known += [f["fact_id"] for f in truth["facts"] if f["category"] in cats and not f["fact_id"].startswith(("f.lab.needs_", "f.imaging.needs_"))]
        out, seen_ids = [], set()
        for k in known:
            if k not in seen_ids:
                seen_ids.add(k)
                out.append(k)
        note = ""
        if triaged:
            note = (f"ESI {int(g('acu_q'))}; {truth['condition_group'].replace('_', ' ')}; arrived by "
                    f"{E['arrival_mode'][int(g('mode'))].replace('_', ' ')}; age {truth['age']}")
        return dict(patient_id=int(patient_id), known_fact_ids=out, triage_note=note, orders=orders, results_ready=ready)

    # ---- playable interaction ---------------------------------------------------------------
    def _provider_of(self, b, patient_id):
        sticky = self._viz_staff[b] if b < len(self._viz_staff) else {}
        return sticky.get(int(patient_id))

    def pending_interaction(self, b: int, patient_id: int):
        from .engine import S_PROV, S_WP, S_WALK
        s = self._slot(b, patient_id)
        if s is None:
            return None
        p = self.p
        g = lambda k: p[k][b, s].item()   # noqa: E731
        st = int(g("state"))
        waiting = st == S_WP or (st == S_WALK and int(g("next_state")) == S_WP)
        in_enc = st == S_PROV and int(g("phase")) == 1
        if not (waiting or in_enc):
            return None
        sid = self._provider_of(b, patient_id) if in_enc else None
        return dict(interaction_type="clinician_encounter", patient_id=int(patient_id),
                    status="in_progress" if in_enc else "waiting", held=bool(g("hold")),
                    t_start=int(g("t_seen")) if in_enc else None,
                    sampled_duration_min=round(float(g("enc_dur")), 1) if in_enc else None,
                    participants=[dict(entity_id=int(patient_id), role="patient", played_by="sim"),
                                  dict(entity_id=sid if sid is not None else "unassigned", role="attending", playable=True)],
                    declaration="catalog/interactions.yaml#clinician_encounter", playable=True)

    def hold_for_play(self, b: int, patient_id: int) -> bool:
        """Freeze the sampler for this patient's clinician encounter. Allowed any time before the
        encounter has finished; the patient stays with_provider and the provider stays busy until
        apply_interaction_result is called."""
        from .engine import S_PROV, S_WT, S_TRI, S_WB, S_WP, S_WALK
        s = self._slot(b, patient_id)
        if s is None:
            return False
        p = self.p
        st = int(p["state"][b, s])
        ok = st in (S_WT, S_TRI, S_WB, S_WP) or (st == S_WALK and int(p["next_state"][b, s]) == S_WP) or \
            (st == S_PROV and int(p["phase"][b, s]) == 1)
        if ok:
            p["hold"][b, s] = True
        return bool(ok)

    def release_hold(self, b: int, patient_id: int) -> bool:
        """Give the patient back to the sampler (used when a played session is abandoned)."""
        s = self._slot(b, patient_id)
        if s is None:
            return False
        self.p["hold"][b, s] = False
        if self._deferred[b].pop(int(patient_id), None) is not None:      # a stored early result is discarded with the hold
            self._deferred_n = sum(len(d) for d in self._deferred)
        return True

    def _apply_deferred(self):
        from .engine import S_PROV
        p = self.p
        for b, dd in enumerate(self._deferred):
            for pid in list(dd):
                s = self._slot(b, pid)
                if s is None or int(p["state"][b, s]) == 11:
                    dd.pop(pid)                       # left before being seen (LWBS, death)
                elif int(p["state"][b, s]) == S_PROV and int(p["phase"][b, s]) == 1:
                    res = dd.pop(pid)
                    # the session already happened: the encounter occupies the provider for the played duration from now
                    self.apply_interaction_result(b, res, defer=False)
        self._deferred_n = sum(len(d) for d in self._deferred)

    def cancel_deferred_result(self, b: int, patient_id: int) -> bool:
        """Drop a played result queued with defer=True and give the patient back to the sampler.
        Returns True if a queued result existed."""
        had = int(patient_id) in self._deferred[b]
        self.release_hold(b, patient_id)
        if had and int(patient_id) in self._deferred[b]:      # patient already gone: release_hold found no slot
            self._deferred[b].pop(int(patient_id), None)
            self._deferred_n = sum(len(d) for d in self._deferred)
        return had

    def apply_interaction_result(self, b: int, result: dict, defer: bool = False) -> None:
        """Write a played clinician-encounter result. With defer=True a result for a patient who has not yet
        started the encounter (any pre-provider state) is stored and applied on the tick the encounter starts;
        the patient is held meanwhile. A patient who is past the encounter is rejected with ValueError, a patient
        who has left with KeyError. release_hold() cancels a hold and any stored result; the sampler then resumes."""
        from .engine import S_PROV, F_PLAYED, N_XRAY, N_CT, N_LAB
        if result.get("resolver") != "played":
            raise ValueError("apply_interaction_result expects resolver='played'")
        if result.get("interaction_type") != "clinician_encounter":
            raise ValueError("only clinician_encounter is playable in this simulator")
        pid = int(result["patient_id"])
        s = self._slot(b, pid)
        if s is None:
            raise KeyError(f"patient {pid} is not in hospital {b}")
        p = self.p
        st_now = int(p["state"][b, s])
        if defer and int(p["t_seen"][b, s]) < 0 and st_now != 11:
            # the played session finished before the simulated encounter began: keep the result and
            # write it on the tick the encounter starts (see _apply_deferred)
            self._deferred[b][pid] = dict(result)
            self._deferred_n = sum(len(d) for d in self._deferred)
            p["hold"][b, s] = True
            return
        if not (st_now == S_PROV and int(p["phase"][b, s]) == 1):
            raise ValueError(f"patient {pid} is not in a clinician encounter (state {self.enums['patient_state'][int(p['state'][b, s])]})")
        dur = max(0.0, float(result["duration_min"]))
        q = min(1.0, max(0.0, float(result["quality"])))
        elapsed = max(0, self._tick - 1 - int(p["t_seen"][b, s])) * self.tick_minutes   # simulated minutes already spent in the encounter
        p["enc_dur"][b, s] = dur
        p["timer"][b, s] = max(0.0, dur - elapsed)
        p["enc_q"][b, s] = q
        dec = result.get("decision") or {}
        if isinstance(dec.get("orders"), list):
            bits = 0
            text = " ".join(str(o).lower() for o in dec["orders"])
            if "ct" in text.replace("-", " ").split() or "ct " in text or text.endswith("ct") or "computed tomography" in text:
                bits |= N_CT
            elif any(w in text for w in ("xray", "x-ray", "x ray", "radiograph", "cxr")):
                bits |= N_XRAY
            if any(w in text for w in ("lab", "blood", "cbc", "bmp", "troponin", "lactate", "urinalysis", "panel")):
                bits |= N_LAB
            for ti, bit in enumerate((N_XRAY, N_CT)):
                if (bits & bit) and int(self.eq_units[b, ti] + self.pend_eq_n[b, ti]) == 0:
                    bits &= ~bit
            p["needs"][b, s] = bits
        disp = dec.get("disposition")
        if disp in ("discharge", "admit", "transfer"):
            p["disp"][b, s] = ["discharge", "admit", "transfer"].index(disp)
        p["flags"][b, s] = int(p["flags"][b, s]) | F_PLAYED
        p["hold"][b, s] = False
        self._any_played = True
        rec = dict(result)
        rec.setdefault("t_start", int(p["t_seen"][b, s]))
        rec.setdefault("interaction_id", f"enc-{b}-{pid}")
        self._played[b][pid] = rec
        if self.record:
            self._events[b].append(dict(t=self._tick, kind="interaction_played", entity=pid,
                                        text=f"Clinician encounter for P-{pid:06d} was played (quality {q:.2f}, {dur:.0f} min)"))

    # ---- log ------------------------------------------------------------------------------
    def interaction_log(self, b: int, patient_id=None) -> list:
        """Interaction results (sampled and played) of patients currently in the hospital."""
        from .engine import S_WT, S_TRI, S_PROV, S_TEST, S_WTEST, S_WALK
        p = self.p
        cols = self._patient_cols(b)
        extra = {k: p[k][b].index_select(0, p["active"][b].nonzero().flatten()).tolist()
                 for k in ["tri_dur", "enc_dur", "enc_q", "test_dur", "dis_dur", "tdisp"]}
        out = []
        disp_names = ["discharge", "admit", "transfer"]
        for i, pid in enumerate(cols["pid"]):
            if patient_id is not None and pid != int(patient_id):
                continue
            st = cols["state"][i]
            needs = cols["needs"][i]
            if cols["mode"][i] == 0 and st not in (S_WT, S_TRI) and self.flags["triage"] and self.flags["bays"]:
                out.append(dict(interaction_id=f"tri-{b}-{pid}", interaction_type="triage", patient_id=pid, resolver="sampled",
                                duration_min=round(extra["tri_dur"][i], 1), information_gained=[],
                                decision=dict(kind="acuity_assigned", acuity=cols["acu_q"][i]), quality=1.0))
            if cols["t_seen"][i] >= 0:
                in_enc = st == S_PROV and cols["phase"][i] == 1
                played = self._played[b].get(pid)
                if played is not None:
                    out.append(dict(played))
                elif not in_enc:
                    orders = [nm for bit, nm in ((1, "xray"), (2, "ct"), (4, "lab")) if needs & bit]
                    try:
                        info = [k for k in self.known_state(b, pid)["known_fact_ids"]] if patient_id is not None else []
                    except Exception:
                        info = []
                    out.append(dict(interaction_id=f"enc-{b}-{pid}", interaction_type="clinician_encounter", patient_id=pid,
                                    resolver="sampled", t_start=cols["t_seen"][i], duration_min=round(extra["enc_dur"][i], 1),
                                    information_gained=info, decision=dict(kind="orders", orders=orders, disposition="undecided"),
                                    quality=round(extra["enc_q"][i], 3)))
            past_enc = cols["t_seen"][i] >= 0 and not (st == S_PROV and cols["phase"][i] == 1)
            scanned = past_enc and (needs & 3) and not (st in (S_TEST, S_WTEST) or (st == S_WALK and cols["next_state"][i] == S_TEST))
            if scanned and cols["eq"][i] >= 0:
                out.append(dict(interaction_id=f"img-{b}-{pid}", interaction_type="imaging_test", patient_id=pid, resolver="sampled",
                                duration_min=round(extra["test_dur"][i], 1), information_gained=[],
                                decision=dict(kind="none", detail=["xray", "ct"][cols["eq"][i]]), quality=1.0))
            if cols["disp"][i] >= 0 and (st in (8, 9, 11) or (st == S_WALK and cols["next_state"][i] == 9)):
                out.append(dict(interaction_id=f"dis-{b}-{pid}", interaction_type="disposition", patient_id=pid, resolver="sampled",
                                duration_min=round(extra["dis_dur"][i], 1), information_gained=[],
                                decision=dict(kind="disposition", disposition=disp_names[cols["disp"][i]]),
                                quality=round(extra["enc_q"][i], 3)))
        return out
