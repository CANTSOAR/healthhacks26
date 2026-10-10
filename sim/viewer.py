"""Snapshot / layout / entity detail for one hospital of the batch (plain python, JSON-serialisable).

Nothing here runs in the tick path. Positions are derived from room rectangles in the layout.
"""
from __future__ import annotations

import torch

from .layoutmodel import BAY_CLASSES, C_HALL, slot_xy

ROLE_PREFIX = dict(attending="MD", resident="RES", app="APP", rn="RN", charge_rn="CRN", tech="TECH", registration="REG",
                   pharmacist="PHARM", imaging_tech="IMG", transport="TRN", evs="EVS")
SCAN_TYPES = ["xray", "ct"]


class ViewerMixin:
    # ---- layout ---------------------------------------------------------------------------
    def _extra_equipment(self, b):
        out = []
        lm = self.scn.layout
        for ti, t in enumerate(SCAN_TYPES):
            for k in range(int(self.eq_units[b, ti]) - self.eq_units0[ti]):
                rooms = lm.scan_rooms[t]
                out.append(dict(id=f"{t}-new-{k + 1}", type=t, label=f"{t.upper()} (purchased) {k + 1}",
                                room=lm.rooms[rooms[k % len(rooms)]]["id"] if rooms else lm.rooms[0]["id"],
                                catalog_ref=f"equipment/{t}", provenance="inferred",
                                source="Purchased by the manager (equipment_buy action)"))
        return out

    def layout(self, b: int = 0) -> dict:
        ver = int(self.layout_version[b])
        cache = getattr(self, "_layout_cache", None)
        if cache is None:
            cache = self._layout_cache = {}
        hit = cache.get(b)
        if hit is not None and hit[0] == (ver, self._reset_count):
            return hit[1]
        lay = self.scn.layout.render(ver, int(self.reloc[b]), self.bay_exists[b].tolist(), int(self.ward_cap[b]),
                                     self._extra_equipment(b))
        cache[b] = ((ver, self._reset_count), lay)
        return lay

    # ---- staff roster ---------------------------------------------------------------------
    def _role_sequence(self, n):
        mix = self.cfg["role_mix"]
        roles = list(mix)
        tot = sum(mix.values()) or 1.0
        got = {r: 0 for r in roles}
        seq = []
        for k in range(n):
            r = max(roles, key=lambda r_: mix[r_] / tot * (k + 1) - got[r_])
            got[r] += 1
            seq.append(r)
        return seq

    def _roster(self, b):
        """On-shift staff of hospital b as a list of dicts (id, role, group)."""
        shift = self._shift_idx % 3
        out = []
        n_md = int(self.md_eff[b])
        base = int(self.md_sched[b] - self.md_abs[b])
        seq = self._role_sequence(max(self.max_md, n_md))
        for k in range(n_md):
            role = seq[k]
            num = shift * self.max_md + k + 1
            out.append(dict(id=f"{ROLE_PREFIX[role]}-{num:02d}", role=role, group="provider", called_in=k >= base))
        n_rn = int(self.rn_eff[b])
        for k in range(n_rn):
            out.append(dict(id=f"RN-{shift * self.max_rn + k + 1:02d}", role="rn", group="rn"))
        for k in range(int(self.tri_n[b])):
            out.append(dict(id=f"RN-{3 * self.max_rn + shift * 3 + k + 1:02d}", role="rn", group="triage", k=k))
        for role, n in self.cfg["support"].items():
            for k in range(n):
                out.append(dict(id=f"{ROLE_PREFIX[role]}-{shift * n + k + 1:02d}", role=role, group=role, k=k))
        return out

    def _staff_name(self, s):
        """Stable fictional display name for a roster entry (cosmetic; sim/scenarios/_staff_names.yaml)."""
        nm = getattr(self, "_names", None)
        if nm is None:
            from .config import SCENARIOS, _yaml
            try:
                nm = _yaml(SCENARIOS / "_staff_names.yaml")
            except Exception:
                nm = {}
            self._names = nm
        given, family = nm.get("given") or [], nm.get("family") or []
        if not given or not family:
            return None
        try:
            num = int(str(s["id"]).rsplit("-", 1)[1])
        except Exception:
            num = 0
        roles = self.enums["staff_role"]
        g = s.get("group")
        i = num if g == "provider" else (100 + num if g in ("rn", "triage") else 300 + 40 * roles.index(s["role"]) + num)
        return f"{(nm.get('titles') or {}).get(s['role'], '')}{given[i % len(given)]} {family[i % len(family)]}"

    # ---- snapshot -------------------------------------------------------------------------
    def _patient_cols(self, b):
        p = self.p
        idx = torch.nonzero(p["active"][b]).flatten()
        cols = {k: p[k][b].index_select(0, idx).tolist() for k in
                ["pid", "acu", "acu_q", "cond", "state", "exit", "mode", "age", "payer", "flags", "bay", "eq", "next_state",
                 "t_arr", "t_state", "timer", "walk_total", "phase", "t_seen", "needs", "disp", "hold"]}
        cols["slot"] = idx.tolist()
        return cols

    def _ward_room(self, lay_rooms, pid, ward_cap):
        lm = self.scn.layout
        if not lm.ward_rooms:
            return -1, 0, 1
        k = pid % max(1, ward_cap)
        for i in lm.ward_rooms:
            cap = int(lay_rooms[i]["capacity"])
            if k < cap:
                return i, k, cap
            k -= cap
        i = lm.ward_rooms[-1]
        return i, k, max(1, int(lay_rooms[i]["capacity"]))

    def _place(self, b, cols, lay_rooms):
        """Room index and x,z for every patient in `cols`."""
        from .engine import (S_WT, S_TRI, S_WB, S_WP, S_PROV, S_WTEST, S_TEST, S_WRES, S_BOARD, S_WARD, S_WALK, S_EXIT,
                             X_WARD)
        lm = self.scn.layout
        NB = self.NB
        ward_cap = int(self.ward_cap[b])
        n = len(cols["pid"])
        room, xs, zs = [-1] * n, [0.0] * n, [0.0] * n
        tri_k = 0
        tri_sorted = sorted([i for i in range(n) if cols["state"][i] == S_TRI], key=lambda i: cols["pid"][i])
        tri_of = {i: k for k, i in enumerate(tri_sorted)}

        def at_room(ri, k, cap=None):
            if ri is None or ri < 0:
                return -1, 0.0, 0.0
            r = lay_rooms[ri]
            x, z = slot_xy(r, k, cap)
            return ri, x, z

        def waiting_spot(i):
            pid = cols["pid"][i]
            if cols["mode"][i] == 0:
                return at_room(lm.waiting, pid, max(1, lay_rooms[lm.waiting]["capacity"]))
            return at_room(lm.amb, pid, max(1, lay_rooms[lm.amb]["capacity"]))

        def bay_spot(i):
            bj = cols["bay"][i]
            if bj >= NB:
                return waiting_spot(i)
            bd = lm.bays[bj]
            return at_room(bd["room"], bd["slot"], max(1, lay_rooms[bd["room"]]["capacity"]))

        # scanner rooms: sticky pid -> room, one patient per room while rooms are free
        scan_sticky = self._viz_scan[b] if b < len(self._viz_scan) else {}
        at_scan = [i for i in range(n) if cols["eq"][i] >= 0 and (cols["state"][i] == S_TEST or (
            cols["state"][i] == S_WALK and cols["next_state"][i] in (S_TEST, S_WRES)))]
        here_s = {cols["pid"][i] for i in at_scan}
        for pid in [q for q in scan_sticky if q not in here_s]:
            del scan_sticky[pid]
        for i in sorted(at_scan, key=lambda i: (cols["state"][i] != S_TEST, cols["t_state"][i], cols["pid"][i])):
            pid = cols["pid"][i]
            if pid in scan_sticky:
                continue
            rooms_t = lm.scan_rooms[SCAN_TYPES[cols["eq"][i]]] or lm.scan_rooms["xray"] or lm.scan_rooms["ct"]
            if rooms_t:
                taken = set(scan_sticky.values())
                free_r = [r_ for r_ in rooms_t if r_ not in taken]
                scan_sticky[pid] = free_r[0] if free_r else rooms_t[pid % len(rooms_t)]

        def scan_spot(i):
            ri = scan_sticky.get(cols["pid"][i])
            if ri is None:
                return bay_spot(i)
            return at_room(ri, 0, 1)

        # ward beds: sticky pid -> bed number, so a room never shows more patients than its capacity
        beds = []                                   # bed number -> (room index, slot, room capacity)
        for ri in lm.ward_rooms:
            cap = int(lay_rooms[ri]["capacity"])
            beds += [(ri, k, cap) for k in range(cap)]
        sticky = self._viz_ward[b] if b < len(self._viz_ward) else {}
        wardish = [i for i in range(n) if cols["state"][i] == S_WARD or (cols["state"][i] == S_WALK and cols["next_state"][i] == S_WARD)
                   or (cols["state"][i] == S_EXIT and cols["exit"][i] == X_WARD)]
        here = {cols["pid"][i] for i in wardish}
        for pid in [q for q in sticky if q not in here or sticky[q] >= len(beds)]:
            del sticky[pid]
        used = set(sticky.values())
        free_beds = (k for k in range(len(beds)) if k not in used)
        over = 0
        for i in sorted(wardish, key=lambda i: cols["pid"][i]):
            pid = cols["pid"][i]
            if pid not in sticky:
                k = next(free_beds, None)
                if k is None:                       # census above the staffed beds (after beds were closed)
                    over += 1
                    continue
                sticky[pid] = k

        def ward_spot(i):
            k = sticky.get(cols["pid"][i])
            if k is None:
                if not beds:
                    return -1, 0.0, 0.0
                ri, _, cap = beds[-1]
                return at_room(ri, cols["pid"][i], cap)
            ri, slot, cap = beds[k]
            return at_room(ri, slot, cap)

        for i in range(n):
            st = cols["state"][i]
            if st == S_WT:
                r = waiting_spot(i)
            elif st == S_WB:
                r = waiting_spot(i)
            elif st == S_TRI:
                tr = lm.triage_rooms
                r = at_room(tr[tri_of[i] % len(tr)], 0, 1) if tr else waiting_spot(i)
            elif st in (S_WP, S_PROV, S_WTEST, S_WRES, S_BOARD):
                r = bay_spot(i)
            elif st == S_TEST:
                r = scan_spot(i)
            elif st == S_WARD:
                r = ward_spot(i)
            elif st == S_WALK:
                nx = cols["next_state"][i]
                if nx == S_WP:
                    a, d = waiting_spot(i), bay_spot(i)
                elif nx == S_TEST:
                    a, d = bay_spot(i), scan_spot(i)
                elif nx == S_WRES:
                    a, d = scan_spot(i), bay_spot(i)
                else:
                    a, d = (at_room(lm.waiting, cols["pid"][i]) if cols["bay"][i] >= NB else bay_spot(i)), ward_spot(i)
                tot = cols["walk_total"][i]
                fr = 1.0 if tot <= 1e-6 else min(1.0, max(0.0, 1.0 - cols["timer"][i] / tot))
                r = (d[0], a[1] + (d[1] - a[1]) * fr, a[2] + (d[2] - a[2]) * fr)
            else:   # exited this tick
                if cols["exit"][i] == X_WARD:
                    r = ward_spot(i)
                else:
                    ent = lm.entrance if lm.entrance is not None else lm.waiting
                    r = at_room(ent, 0, 1)
            room[i], xs[i], zs[i] = r[0], round(r[1], 2), round(r[2], 2)
        return room, xs, zs

    def snapshot(self, b: int = 0, consume: bool = True) -> dict:
        """consume=False leaves the event / decision buffers untouched (they are still returned)."""
        from .engine import (S_WT, S_TRI, S_WB, S_WP, S_PROV, S_WTEST, S_TEST, S_WRES, S_BOARD, S_WARD, S_WALK, S_EXIT)
        E = self.enums
        lm = self.scn.layout
        lay = self.layout(b)
        rooms_l = lay["rooms"]
        t, dt = self._tick, self.tick_minutes
        cols = self._patient_cols(b)
        n = len(cols["pid"])
        room, xs, zs = self._place(b, cols, rooms_l)
        # ---- staff
        roster = self._roster(b)
        role_idx = {r: i for i, r in enumerate(E["staff_role"])}
        S_IDLE, S_BUSY, S_WALKING = E["staff_state"].index("idle"), E["staff_state"].index("busy"), E["staff_state"].index("walking")
        stations = lm.by_type.get("nurse_station", []) or ([lm.waiting] if lm.waiting is not None else [0])
        st_staff = dict(id=[], name=[], role=[], state=[], room=[], x=[], z=[], patient=[], fatigue=[])
        pat_staff = [-1] * n
        fat_md, fat_rn = round(float(self.fat_md[b]), 3), round(float(self.fat_rn[b]), 3)
        prov_pat = sorted([i for i in range(n) if cols["state"][i] == S_PROV], key=lambda i: (cols["t_state"][i], cols["pid"][i]))
        providers = [s for s in roster if s["group"] == "provider"]
        sticky = self._viz_staff[b] if b < len(self._viz_staff) else {}
        ids = {s["id"] for s in providers}
        assign, used = {}, set()
        for i in prov_pat:                      # keep earlier pairings
            sid = sticky.get(cols["pid"][i])
            if sid in ids and sid not in used:
                assign[i] = sid
                used.add(sid)
        free_ids = [s["id"] for s in providers if s["id"] not in used]
        for i in prov_pat:
            if i not in assign and free_ids:
                assign[i] = free_ids.pop(0)
        sticky.clear()
        sticky.update({cols["pid"][i]: sid for i, sid in assign.items()})
        prov_of = {sid: i for i, sid in assign.items()}
        in_bay = sorted([i for i in range(n) if cols["bay"][i] < self.NB and cols["state"][i] not in (S_EXIT, S_WALK, S_TEST)],
                        key=lambda i: cols["bay"][i])
        nurses = [s for s in roster if s["group"] == "rn"]
        rn_pats = {s["id"]: [] for s in nurses}
        if nurses:
            per = max(1, -(-len(in_bay) // len(nurses)))
            for j, i in enumerate(in_bay):
                rn_pats[nurses[min(len(nurses) - 1, j // per)]["id"]].append(i)
        tri_pat = sorted([i for i in range(n) if cols["state"][i] == S_TRI], key=lambda i: cols["pid"][i])
        test_pat = [i for i in range(n) if cols["state"][i] == S_TEST]
        walk_pat = [i for i in range(n) if cols["state"][i] == S_WALK and cols["next_state"][i] in (S_TEST, S_WRES, S_WARD)]
        cleaning = [j for j in torch.nonzero(self.bay_clean[b, :self.NB] > 0).flatten().tolist()]
        kcount = {}

        def add(s, state, ri, x, z, pat_i=None, fat=0.0, off=0.6):
            k = len(st_staff["id"])
            st_staff["id"].append(s["id"]), st_staff["name"].append(self._staff_name(s)), st_staff["role"].append(role_idx[s["role"]])
            st_staff["state"].append(state), st_staff["room"].append(ri)
            st_staff["x"].append(round(x + (off if pat_i is not None else 0.0), 2)), st_staff["z"].append(round(z, 2))
            st_staff["patient"].append(cols["pid"][pat_i] if pat_i is not None else -1)
            st_staff["fatigue"].append(fat)
            if pat_i is not None and pat_staff[pat_i] < 0:
                pat_staff[pat_i] = k

        def idle_at(s, rlist, fat=0.0):
            j = kcount.get(s["group"], 0)
            kcount[s["group"]] = j + 1
            ri = rlist[j % len(rlist)]
            r = rooms_l[ri]
            x, z = slot_xy(dict(r, slots=None), j // len(rlist), 6)
            add(s, S_IDLE, ri, x, z, None, fat)

        for s in roster:
            g = s["group"]
            if g == "provider":
                i = prov_of.get(s["id"])
                if i is not None:
                    add(s, S_BUSY, room[i], xs[i], zs[i], i, fat_md)
                else:
                    idle_at(s, stations, fat_md)
            elif g == "rn":
                mine = rn_pats.get(s["id"]) or []
                if mine:
                    i = mine[(t // 3) % len(mine)]
                    add(s, S_BUSY, room[i], xs[i], zs[i], i, fat_rn, off=-0.6)
                else:
                    idle_at(s, stations, fat_rn)
            elif g == "triage":
                tr = lm.triage_rooms
                ri = tr[s["k"] % len(tr)] if tr else lm.waiting
                i = tri_pat[s["k"]] if s["k"] < len(tri_pat) else None
                add(s, S_BUSY if i is not None else S_IDLE, ri, rooms_l[ri]["x"], rooms_l[ri]["z"], i, fat_rn)
            elif g == "imaging_tech" and s["k"] < len(test_pat):
                i = test_pat[s["k"]]
                add(s, S_BUSY, room[i], xs[i], zs[i], i)
            elif g == "transport" and s["k"] < len(walk_pat):
                i = walk_pat[s["k"]]
                add(s, S_WALKING, room[i], xs[i], zs[i], i, off=0.5)
            elif g == "evs" and s["k"] < len(cleaning):
                ri = lm.bay_room[cleaning[s["k"]]]
                add(s, S_BUSY, ri, rooms_l[ri]["x"], rooms_l[ri]["z"])
            else:
                home = dict(registration=[lm.waiting], pharmacist=lm.by_type.get("pharmacy"), imaging_tech=lm.scan_rooms["ct"] or lm.scan_rooms["xray"],
                            evs=lm.by_type.get("support")).get(g) or stations
                idle_at(s, [h for h in home if h is not None] or stations)
        # ---- rooms
        R = len(rooms_l)
        status = [1] * R
        occ = [0] * R
        queue = [0] * R
        for i in range(n):
            if room[i] >= 0 and cols["state"][i] not in (S_EXIT, S_WALK):
                occ[room[i]] += 1
        be, bo, bb, bc = (self.bay_exists[b].tolist(), self.bay_open[b].tolist(), self.bay_busy[b].tolist(), self.bay_clean[b].tolist())
        ST_CLOSED, ST_OPEN, ST_OCC, ST_CLEAN, ST_OOS = range(5)
        multi = {}
        for j, bd in enumerate(lm.bays):
            ri = bd["room"]
            s = ST_CLOSED if not (be[j] and bo[j]) else (ST_OCC if bb[j] else (ST_CLEAN if bc[j] > 0 else ST_OPEN))
            if s == ST_CLOSED and bb[j]:
                s = ST_OCC
            multi.setdefault(ri, []).append(s)
        for ri, ss in multi.items():
            status[ri] = ST_OCC if ST_OCC in ss else (ST_OPEN if ST_OPEN in ss else (ST_CLEAN if ST_CLEAN in ss else ST_CLOSED))
        nq = lambda s_: sum(1 for i in range(n) if cols["state"][i] == s_)   # noqa: E731
        if lm.waiting is not None:
            queue[lm.waiting] = nq(S_WT) + sum(1 for i in range(n) if cols["state"][i] == S_WB and cols["mode"][i] == 0)
        if lm.amb is not None and lm.amb != lm.waiting:
            queue[lm.amb] = sum(1 for i in range(n) if cols["state"][i] == S_WB and cols["mode"][i] != 0)
        tri_n = int(self.tri_n[b])
        for k, ri in enumerate(lm.triage_rooms):
            status[ri] = ST_CLOSED if k >= tri_n else (ST_OCC if occ[ri] else ST_OPEN)
        if lm.triage_rooms:
            queue[lm.triage_rooms[0]] = nq(S_WT)
        down = (self.eq_down[b] > 0).tolist()
        for ti, tname in enumerate(SCAN_TYPES):
            rs = lm.scan_rooms[tname]
            for k, ri in enumerate(rs):
                status[ri] = ST_OOS if (k < len(down[ti]) and down[ti][k]) else (ST_OCC if occ[ri] else ST_OPEN)
            if rs:
                queue[rs[0]] = sum(1 for i in range(n) if cols["state"][i] == S_WTEST and (cols["needs"][i] & (1 << ti)))
        for ri in lm.ward_rooms + [x for x in [lm.waiting, lm.amb] if x is not None]:
            status[ri] = ST_OCC if occ[ri] else ST_OPEN
        for ri, r in enumerate(rooms_l):
            if r.get("physical", True) is False:
                status[ri] = ST_CLOSED
        # ---- equipment
        EQ_IDLE, EQ_USE, EQ_DOWN, EQ_OFF = range(4)
        eq_status = []
        seen = {tname: 0 for tname in SCAN_TYPES}
        in_use = [sum(1 for i in range(n) if cols["state"][i] == S_TEST and cols["eq"][i] == ti) for ti in range(2)]
        avail = self.eq_avail[b].tolist()
        for e in lay["equipment"]:
            if e["type"] in seen:
                ti = SCAN_TYPES.index(e["type"])
                k = seen[e["type"]]
                seen[e["type"]] += 1
                if k < len(down[ti]) and down[ti][k]:
                    eq_status.append(EQ_DOWN)
                    continue
                up_before = sum(1 for kk in range(k) if not down[ti][kk])
                if up_before < in_use[ti]:
                    eq_status.append(EQ_USE)
                elif up_before >= avail[ti]:
                    eq_status.append(EQ_OFF)
                else:
                    eq_status.append(EQ_IDLE)
            else:
                eq_status.append(EQ_IDLE)
        # ---- kpis
        inst = self._instant()
        kp = {k: round(float(inst[k][b]), 4) for k in ["ed_census", "waiting_count", "boarding_count", "bay_occupancy", "ward_occupancy"]}
        for k in ["wait_p95_min", "wait_mean_min", "ed_los_median_min", "lwbs_rate", "margin", "revenue", "cost_total",
                  "md_utilization", "rn_utilization", "arrivals", "first_seen", "lwbs", "deaths", "adverse_events"]:
            kp[k] = round(float(self._last[k][b]), 4)
        kp["staff_on_shift"] = len(roster)
        kp["fatigue_mean"] = round((fat_md + fat_rn) / 2, 4)
        kp["providers_on_shift"] = int(self.md_eff[b])
        kp["nurses_on_shift"] = int(self.rn_eff[b])
        kp["staffed_bays"] = int(inst["staffed"][b])
        kp["physical_bays_open"] = int(inst["phys"][b])
        kp["ward_beds"] = int(self.ward_cap[b])
        kp["invalid_actions"] = int(self.invalid_actions[b])
        kp["settings"] = {h: int(self.settings[h][b]) for h in self.head_names}
        ambulances = []
        if lm.amb is not None:
            ar = rooms_l[lm.amb]
            for i in range(n):
                age_t = t - cols["t_arr"][i]
                if cols["mode"][i] == 1 and age_t <= 3 and cols["state"][i] != S_EXIT:
                    x, z = slot_xy(ar, cols["pid"][i], max(1, ar["capacity"]))
                    ambulances.append(dict(id=f"AMB-{cols['pid'][i] % 100:02d}", x=round(x, 2), z=round(z, 2),
                                           state="unloading" if age_t <= 1 else "leaving"))
        events, decisions = [], []
        if self.record:
            events, decisions = list(self._events[b]), list(self._decisions[b])
            if consume:
                self._events[b], self._decisions[b] = [], []
        hour_min = (t * dt) % 1440
        day = (t * dt) // 1440
        return dict(
            t=t, clock=dict(day=int(day), minute_of_day=int(hour_min), dow=int(day % 7)),
            layout_version=int(self.layout_version[b]),
            patients=dict(id=cols["pid"], acuity=cols["acu_q"], condition=cols["cond"], state=cols["state"], exit=cols["exit"],
                          room=room, x=xs, z=zs, age_min=[(t - a) * dt for a in cols["t_arr"]],
                          state_min=[max(0, (t - a) * dt) for a in cols["t_state"]], arrival_mode=cols["mode"],
                          age_band=cols["age"], payer=cols["payer"], flags=cols["flags"], staff=pat_staff,
                          bay=[lm.bay_room[bj] if bj < self.NB else -1 for bj in cols["bay"]]),
            staff=st_staff, rooms=dict(status=status, occupancy=occ, queue=queue), equipment=dict(status=eq_status),
            ambulances=ambulances, kpis=kp, events=events, decisions=decisions)

    # ---- entity detail --------------------------------------------------------------------
    def _slot(self, b, patient_id):
        p = self.p
        m = torch.nonzero(p["active"][b] & (p["pid"][b] == int(patient_id))).flatten()
        return int(m[0]) if len(m) else None

    LATENT_KEYS = ("true_acuity", "severity", "encounter_quality")

    def patient_detail(self, b: int, patient_id: int, public: bool = False) -> dict:
        """public=True omits latent values (true acuity, severity, sampled encounter quality)."""
        if self._slot(b, patient_id) is None and b < len(self._gone) and int(patient_id) in self._gone[b]:
            d = self._gone_detail(b, int(patient_id))
        else:
            d = self._patient_detail(b, patient_id)
        if public:
            for k in self.LATENT_KEYS:
                d.pop(k, None)
        return d

    def _patient_detail(self, b: int, patient_id: int) -> dict:
        s = self._slot(b, patient_id)
        if s is None:
            raise KeyError(f"patient {patient_id} is not in hospital {b} (never arrived or already left)")
        E, p, t, dt = self.enums, self.p, self._tick, self.tick_minutes
        g = lambda k: p[k][b, s].item()   # noqa: E731
        lm = self.scn.layout
        lay = self.layout(b)
        cols = self._patient_cols(b)
        i = cols["slot"].index(s)
        room, xs, zs = self._place(b, cols, lay["rooms"])
        needs = int(g("needs"))
        bay = int(g("bay"))
        cond = E["condition_group"][int(g("cond"))]
        return dict(
            patient_id=int(patient_id), display_id=f"P-{int(patient_id):06d}", acuity=int(g("acu_q")), true_acuity=int(g("acu")),
            condition_group=cond, state=E["patient_state"][int(g("state"))], exit=E["patient_exit"][int(g("exit"))],
            arrival_mode=E["arrival_mode"][int(g("mode"))], age_band=E["age_band"][int(g("age"))], payer=E["payer"][int(g("payer"))],
            severity=round(float(g("sev")), 3), flags=int(g("flags")),
            flag_names=[nm for bit, nm in ((1, "deteriorated"), (2, "admitted"), (4, "fast_track"), (8, "played")) if int(g("flags")) & bit],
            room=lay["rooms"][room[i]]["id"] if room[i] >= 0 else None, room_index=room[i], x=xs[i], z=zs[i],
            bay=lay["rooms"][lm.bay_room[bay]]["id"] if bay < self.NB else None,
            bay_class=BAY_CLASSES[lm.bay_cls[bay]] if bay < self.NB else None,
            arrival_t=int(g("t_arr")), age_min=int((t - g("t_arr")) * dt), state_min=int((t - g("t_state")) * dt),
            first_seen_t=int(g("t_seen")) if g("t_seen") >= 0 else None,
            door_to_provider_min=int((g("t_seen") - g("t_arr")) * dt) if g("t_seen") >= 0 else None,
            remaining_min=round(max(0.0, float(g("timer"))), 1) if int(g("state")) in (1, 4, 6, 9, 10) else None,
            orders=[nm for bit, nm in ((1, "xray"), (2, "ct"), (4, "lab")) if needs & bit] if g("t_seen") >= 0 else [],
            disposition=(["discharge", "admit", "transfer"][int(g("disp"))] if g("disp") >= 0 else "undecided"),
            in_hospital=True, held_for_play=bool(g("hold")), encounter_quality=round(float(g("enc_q")), 3) if g("t_seen") >= 0 else None,
            interactions=self.interaction_log(b, patient_id),
            catalog_refs=[f"patient/esi{int(g('acu_q'))}", f"conditions/{cond}"],
            synthetic=True)

    # ---- patients who have left: last-known record (kept only for small batches) ---------
    RAW_KEYS = ("acu", "acu_q", "cond", "exit", "mode", "age", "payer", "sev", "flags", "t_arr", "t_state", "t_seen", "needs",
                "disp", "eq", "enc_dur", "enc_q", "tri_dur", "test_dur", "dis_dur", "t_board", "tdisp")

    def _capture_exits(self):
        p = self.p
        m = p["active"] & (p["state"] == 11)
        if not bool(m.any()):
            return
        cap = int(self.scn.engine.get("exited_history", 5000))
        for b, s in torch.nonzero(m).tolist():
            raw = {k: p[k][b, s].item() for k in self.RAW_KEYS}
            g = self._gone[b]
            g[int(p["pid"][b, s])] = raw
            if len(g) > cap:
                g.pop(next(iter(g)))

    def _gone_detail(self, b: int, pid: int) -> dict:
        E, dt = self.enums, self.tick_minutes
        r = self._gone[b][pid]
        seen = r["t_seen"] >= 0
        needs = int(r["needs"])
        cond = E["condition_group"][int(r["cond"])]
        ex = E["patient_exit"][int(r["exit"])]
        orders = [nm for bit, nm in ((1, "xray"), (2, "ct"), (4, "lab")) if needs & bit] if seen else []
        log = []
        if r["mode"] == 0 and seen and self.flags["triage"] and self.flags["bays"]:
            log.append(dict(interaction_id=f"tri-{b}-{pid}", interaction_type="triage", patient_id=pid, resolver="sampled",
                            duration_min=round(r["tri_dur"], 1), information_gained=[],
                            decision=dict(kind="acuity_assigned", acuity=int(r["acu_q"])), quality=1.0))
        if seen:
            played = self._played[b].get(pid)
            log.append(dict(played) if played is not None else dict(
                interaction_id=f"enc-{b}-{pid}", interaction_type="clinician_encounter", patient_id=pid, resolver="sampled",
                t_start=int(r["t_seen"]), duration_min=round(r["enc_dur"], 1), information_gained=[],
                decision=dict(kind="orders", orders=orders, disposition="undecided"), quality=round(r["enc_q"], 3)))
            if (needs & 3) and r["eq"] >= 0:
                log.append(dict(interaction_id=f"img-{b}-{pid}", interaction_type="imaging_test", patient_id=pid, resolver="sampled",
                                duration_min=round(r["test_dur"], 1), information_gained=[],
                                decision=dict(kind="none", detail=["xray", "ct"][int(r["eq"])]), quality=1.0))
            if r["disp"] >= 0 and ex in ("discharged_ed", "discharged_ward", "transferred"):
                log.append(dict(interaction_id=f"dis-{b}-{pid}", interaction_type="disposition", patient_id=pid, resolver="sampled",
                                duration_min=round(r["dis_dur"], 1), information_gained=[],
                                decision=dict(kind="disposition", disposition=["discharge", "admit", "transfer"][int(r["disp"])]),
                                quality=round(r["enc_q"], 3)))
        fl = int(r["flags"])
        return dict(
            patient_id=pid, display_id=f"P-{pid:06d}", acuity=int(r["acu_q"]), true_acuity=int(r["acu"]), condition_group=cond,
            state="exited", exit=ex, in_hospital=False, arrival_mode=E["arrival_mode"][int(r["mode"])],
            age_band=E["age_band"][int(r["age"])], payer=E["payer"][int(r["payer"])], severity=round(float(r["sev"]), 3), flags=fl,
            flag_names=[nm for bit, nm in ((1, "deteriorated"), (2, "admitted"), (4, "fast_track"), (8, "played")) if fl & bit],
            room=None, room_index=-1, x=None, z=None, bay=None, bay_class=None,
            arrival_t=int(r["t_arr"]), exit_t=int(r["t_state"]), total_min=int((r["t_state"] - r["t_arr"]) * dt),
            age_min=int((self._tick - r["t_arr"]) * dt), state_min=int((self._tick - r["t_state"]) * dt),
            first_seen_t=int(r["t_seen"]) if seen else None,
            door_to_provider_min=int((r["t_seen"] - r["t_arr"]) * dt) if seen else None, remaining_min=None, orders=orders,
            disposition=(["discharge", "admit", "transfer"][int(r["disp"])] if r["disp"] >= 0 else "undecided"),
            held_for_play=False, encounter_quality=round(float(r["enc_q"]), 3) if seen else None, interactions=log,
            catalog_refs=[f"patient/esi{int(r['acu_q'])}", f"conditions/{cond}"], synthetic=True)

    def staff_detail(self, b: int, staff_id: str) -> dict:
        snap = self.snapshot(b, consume=False)
        st = snap["staff"]
        if staff_id not in st["id"]:
            raise KeyError(f"staff {staff_id} is not on shift in hospital {b}")
        k = st["id"].index(staff_id)
        E = self.enums
        role = E["staff_role"][st["role"][k]]
        lay = self.layout(b)
        c = self.cfg
        pats = [pid for pid, sidx in zip(snap["patients"]["id"], snap["patients"]["staff"]) if sidx == k]
        return dict(staff_id=staff_id, name=st["name"][k], role=role, state=E["staff_state"][st["state"][k]],
                    room=lay["rooms"][st["room"][k]]["id"] if st["room"][k] >= 0 else None, x=st["x"][k], z=st["z"][k],
                    patient=st["patient"][k] if st["patient"][k] >= 0 else None, patients=pats,
                    fatigue=st["fatigue"][k], shift=["day", "evening", "night"][self._shift_idx % 3],
                    wage_per_hour=c["wage"].get(role), productivity=c["productivity"].get(role),
                    catalog_refs=[f"staff/{role}"], fictional=True)
