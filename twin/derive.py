"""Tracked extracts -> hospital attributes, shared-catalog overrides and layout counts.

Every value is either read from an extract (tag `measured`, with dataset, release, CMS-number filter and field names in
the citation), a published benchmark (`literature`), or produced by a stated rule (`assumed`, with the rule in the
citation). Nothing is filled in silently: when a source is missing the attribute is either left out and listed in the
report or carried as `assumed` with the reason.
"""
from __future__ import annotations

import datetime as dt
import math

import yaml

from .sources._common import REPO, norm_ccn, read_extract

SOURCES = ["hospital_general", "care_compare", "hcris", "pos", "hhs_capacity", "cms_rates", "roster", "quality", "bls_oews", "fluview"]
VISITS_PER_SPACE = 1100          # annual ED visits per treatment space (see the citation text of ed_treatment_spaces)
WARD_UNIT_BEDS = 24
W0 = {"triage": 1.0417, "treatment_bay": 2.5, "resus_bay": 6.6667, "fast_track": 1.4583, "peds_ed": 2.5, "results_waiting": 0.4167, "hallway_overflow": 0.8333}
ESI_CODE = {1: "99291", 2: "99285", 3: "99284", 4: "99283", 5: "99282"}
RULE = "Derived by rule (twin/derive.py), not a public figure for this hospital: "


def A(value, unit, source, citation, **kw):
    """One catalog attribute node."""
    assert source in ("measured", "literature", "assumed"), source
    node = {"value": value, "unit": unit, "source": source, "citation": citation}
    for k in ("url", "file", "range", "note", "index", "validation_only"):
        if kw.get(k) is not None:
            node[k] = kw[k]
    return node


def _days(a: str, b: str) -> int:
    f = lambda s: dt.datetime.strptime(s, "%m/%d/%Y").date()  # noqa: E731
    return (f(b) - f(a)).days + 1


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _label(s):
    """HCRIS alpha labels carry the 5-digit cost-centre code in front ('03100INTENSIVE CARE UNIT')."""
    return None if s is None else (s[5:].strip() if s[:5].isdigit() else s.strip())


def load_shared() -> dict:
    return {f: yaml.safe_load((REPO / "catalog" / f"{f}.yaml").read_text()) for f in ["patient", "staff", "space", "equipment", "event"]}


def shared_node(cat: dict, path: str):
    f, variant, key = path.split(".")
    d = cat[f]
    return (d.get("shared") or {}).get(key) if variant == "shared" else (((d.get("variants") or {}).get(variant) or {}).get("attributes") or {}).get(key)


class Twin:
    """Everything derived for one hospital."""

    def __init__(self, ccn, hospital_id: str, label: str | None = None, expect: list[str] | None = None):
        self.ccn = norm_ccn(ccn)
        self.id = hospital_id
        self.expect = [t for t in (expect or []) if t]
        self.E = {s: read_extract(self.ccn, s) for s in SOURCES}
        self.fetch_log = read_extract(self.ccn, "_fetch_log") or {"sources": {}}
        self.F = lambda s: f"data/processed/hospitals/{self.ccn}/{s}.json"   # noqa: E731
        self.attrs: dict = {}
        self.overrides: dict = {}
        self.missing: list[dict] = []        # things that could not be sourced
        self.disagreements: list[dict] = []
        self.notes: list[str] = []
        self.shared = load_shared()
        pf = REPO / "twin" / "published" / f"{self.ccn}.yaml"
        self.published = (yaml.safe_load(pf.read_text()) or {}).get("attributes", {}) if pf.exists() else {}
        gi = self.E["hospital_general"]
        if not gi:
            raise SystemExit(f"no hospital_general extract for CCN {self.ccn}: run `python -m twin.fetch --ccn {self.ccn}` first")
        self.fac = gi["facility"]
        self.name = self.fac["Facility Name"].title()
        self.label = label or f"{self.name} (model)"
        self.build()

    # ------------------------------------------------------------------------------------------
    def miss(self, what, why, consequence):
        self.missing.append({"what": what, "why": why, "consequence": consequence})

    def src_unavailable(self, name):
        s = (self.fetch_log.get("sources") or {}).get(name) or {}
        return s.get("error") or "extract not present (source not fetched)"

    # ------------------------------------------------------------------------------------------
    def build(self):
        self.identity()
        self.care_compare()
        self.cost_report()
        self.provider_of_services()
        self.hhs()
        self.roster()
        self.rates_context()
        self.quality()
        self.ed_and_ward_sizing()
        self.model_parameters()
        self.override_arrivals()
        self.override_revenue()
        self.override_space_costs()
        self.override_wages()
        self.override_staffing()
        self.override_flu()

    # ---- identity ---------------------------------------------------------------------------
    def identity(self):
        g, f = self.E["hospital_general"], self.fac
        src = g["source"]
        cite = (f"CMS Hospital General Information (Provider Data Catalog {src['dataset_id']}, release {src['release']}), row with Facility ID == '{self.ccn}': "
                f"{f['Facility Name']}, {f.get('Address')}, {f.get('City/Town')}, {f.get('State')} {f.get('ZIP Code')}")
        kw = dict(url=src["landing"], file=self.F("hospital_general"))
        a = self.attrs
        chk = ""
        if self.expect:
            ok = all(t.lower() in (f["Facility Name"] + " " + str(f.get("City/Town"))).lower() for t in self.expect)
            if not ok:
                raise SystemExit(f"CCN {self.ccn} is '{f['Facility Name']}', {f.get('City/Town')} {f.get('State')} - does not match the expected {self.expect}; wrong CMS number?")
            chk = f"; build-time identity check passed: name and city contain {self.expect}"
        a["cms_certification_number"] = A(self.ccn, "identifier", "measured", cite + chk, **kw)
        a["facility_name_cms"] = A(f["Facility Name"], "name", "measured", cite + "; field 'Facility Name'", **kw)
        a["facility_address_cms"] = A(f"{f.get('Address')}, {f.get('City/Town')}, {f.get('State')} {f.get('ZIP Code')}", "address", "measured",
                                      cite + "; fields Address, City/Town, State, ZIP Code", **kw)
        for key, field, unit in [("hospital_type_cms", "Hospital Type", "category"), ("hospital_ownership_cms", "Hospital Ownership", "category"),
                                 ("emergency_services_cms", "Emergency Services", "yes/no")]:
            if f.get(field):
                a[key] = A(f[field], unit, "measured", cite + f"; field '{field}'", **kw)
        r = _num(f.get("Hospital overall rating"))
        if r is not None:
            a["cms_overall_star_rating"] = A(int(r), "stars (1-5)", "measured", cite + "; field 'Hospital overall rating'", **kw)
        else:
            self.miss("cms_overall_star_rating", f"CMS publishes '{f.get('Hospital overall rating')}' for this hospital", "attribute left out")

    # ---- Care Compare -----------------------------------------------------------------------
    def care_compare(self):
        c = self.E["care_compare"]
        self.visits = self.visit_days = None
        if not c:
            self.miss("Care Compare ED measures (OP-18b, OP-18c, OP-22, EDV)", self.src_unavailable("care_compare"),
                      "no validation targets; ED volume falls back to the HHS weekly series if present")
            return
        src = c["source"]
        m = {r["Measure ID"]: r for r in c["measures"]}
        f = c["facility_in_file"]
        base = (f"CMS Care Compare 'Timely and Effective Care - Hospital' (Provider Data Catalog {src['dataset_id']}, release {src['release']}), Facility ID (CCN) {self.ccn} "
                f"{f['Facility Name']}, {f['Address']}, {f['City/Town']} {f['State']}")
        kw = dict(url=src["landing"], file=self.F("care_compare"))
        pk = c["peer_group_key"]
        peers = {(r["group"], r["measure"]): r for r in c["peer_groups"]}
        edv = c.get("edv_category")
        pname = f"the same '{edv}' ED-volume category" if edv else "all hospitals"
        a = self.attrs

        def score(mid):
            r = m.get(mid)
            return (r, _num(r["Score"])) if r else (None, None)

        r, v = score("OP_18b")
        if v is not None:
            p = peers.get((pk, "OP_18b"))
            a["validation_median_ed_time_min"] = A(
                int(v), "minutes", "measured", f"{base}; measure OP_18b score, sample {r['Sample']} sampled visits, period {r['Start Date']}-{r['End Date']}",
                range=[round(p["p10"], 1), round(p["p90"], 1)] if p else None, validation_only=True,
                note="Median minutes from ED arrival to ED departure for DISCHARGED patients only (excludes admitted, transferred and psychiatric patients). "
                     + (f"range = 10th-90th percentile of OP_18b across the {p['n_hospitals']} hospitals in {pname} (median {p['median']:.0f}). " if p else "")
                     + "Compare with the simulator's median length of visit of discharged patients.", **kw)
        else:
            self.miss("validation_median_ed_time_min (OP-18b)", f"CMS score is '{(r or {}).get('Score')}' (footnote {(r or {}).get('Footnote')})", "no ED-time validation target")
        r, v = score("OP_18c")
        if v is not None:
            p = peers.get((pk, "OP_18c"))
            a["validation_median_ed_time_psych_min"] = A(
                int(v), "minutes", "measured", f"{base}; measure OP_18c score, sample {r['Sample']} sampled visits, period {r['Start Date']}-{r['End Date']}",
                range=[round(p["p10"], 1), round(p["p90"], 1)] if p else None, validation_only=True,
                note=f"Psychiatric / mental-health patients, discharged. Only {r['Sample']} sampled visits - a weak target. The simulator has no separate psychiatric stream.", **kw)
        r, v = score("OP_22")
        if v is not None:
            p = peers.get((pk, "OP_22"))
            n = _num(r["Sample"])
            a["validation_lwbs_rate"] = A(
                round(v / 100, 4), "fraction", "measured",
                f"{base}; measure OP_22 score {r['Score']} percent, denominator {r['Sample']} ED visits, period {r['Start Date']}-{r['End Date']}",
                range=[p["p10"] / 100, p["p90"] / 100] if p else None, validation_only=True,
                note=f"CMS publishes OP_22 as a whole-number percent, so {v / 100:.2f} means between {max(0, v - .5):.1f}% and {v + .5:.1f}%. "
                     + (f"range = 10th-90th percentile across {p['n_hospitals']} hospitals in {pname} (median {p['median']:.0f}%)." if p else ""), **kw)
            if n:
                self.visits, self.visit_days = int(n), _days(r["Start Date"], r["End Date"])
                self.visit_cite = f"{base}; denominator ('Sample') of measure OP_22 = total ED visits reported for {r['Start Date']}-{r['End Date']}"
                self.visit_kw = kw
                a["ed_visits_per_year_cms"] = A(
                    int(n), "visits/year", "measured", self.visit_cite,
                    note=f"{int(n)} visits / {self.visit_days} days = {n / self.visit_days:.0f} per day. All ED visits reported under this CMS number; a certification number can "
                         "cover more than one campus, in which case this is their sum. This is the figure the model's arrival rate uses.", **kw)
        else:
            self.miss("validation_lwbs_rate (OP-22)", f"CMS score is '{(r or {}).get('Score')}'", "no LWBS validation target and no CMS ED-visit count")
        if edv:
            r = m["EDV"]
            a["ed_volume_category_cms"] = A(edv, "category", "measured", f"{base}; measure EDV, period {r['Start Date']}-{r['End Date']}",
                                            note="CMS EDV categories: low <20,000; medium 20,000-39,999; high 40,000-59,999; very high >=60,000 visits/year", **kw)
        for mid, key, what in [("SEP_1", "validation_sepsis_bundle_compliance", "severe sepsis and septic shock management bundle (SEP-1), percent of sampled patients who received it"),
                               ("OP_23", "validation_head_ct_within_45min_stroke", "head CT or MRI results for stroke patients within 45 minutes of ED arrival (OP-23)")]:
            r, v = score(mid)
            if v is not None:
                a[key] = A(round(v / 100, 3), "fraction", "measured", f"{base}; measure {mid} score {r['Score']} percent, sample {r['Sample']}, period {r['Start Date']}-{r['End Date']}"
                           + (f", footnote {r['Footnote']}" if r.get("Footnote") else ""), validation_only=True,
                           note=f"Context only - {what}. Not reproduced by the simulator.", **kw)

    # ---- cost report ------------------------------------------------------------------------
    def cost_report(self):
        h = self.E["hcris"]
        self.h = None
        if not h:
            self.miss("HCRIS cost report (beds, days, discharges, occupancy, ED cost and salaries, routine / ICU cost per day, revenue, FTE)",
                      self.src_unavailable("hcris"), "bed counts, occupancy and all cost-derived fixed costs are unavailable; shared-catalog fixed costs (another hospital's) stay in force")
            return
        rep = h["report"]
        y = rep["hcris_file_year"]
        HC = (f"CMS HCRIS hospital cost report (form CMS-2552-10), FY{y} file, report {rep['rpt_rec_num']} for CCN {self.ccn}, "
              f"fiscal year {rep['fy_begin']}-{rep['fy_end']} (report status code {rep['report_status_code']})")
        kw = dict(url=h["source"]["url"], file=self.F("hcris"))
        b, c = h["beds_days_discharges_wsS3_part1"], h["cost_centres"]
        tot = b.get("total_hospital") or {}
        a = self.attrs
        self.h = dict(HC=HC, kw=kw, hours=rep["fy_days"] * 24, b=b, c=c)
        pos = (self.E["pos"] or {}).get("row") or {}
        if tot.get("beds"):
            fac = (b.get("total_facility") or {}).get("beds")
            a["licensed_beds"] = A(int(tot["beds"]), "beds", "measured", f"{HC}; Worksheet S-3 Part I line 14 column 2 (total hospital beds available)",
                                   note="Beds available for use as reported on the cost report, not the state licence."
                                        + (f" Including sub-provider units (psychiatric, rehabilitation) the facility total on line 27 is {int(fac)}." if fac and fac != tot["beds"] else "")
                                        + (f" The Provider of Services file lists {pos['BED_CNT']} certified beds." if pos.get("BED_CNT") else ""), **kw)
        icu_lines = [(k, n) for k, n in [("intensive_care_unit", 8), ("coronary_care_unit", 9), ("burn_icu", 10), ("surgical_icu", 11)] if (b.get(k) or {}).get("beds")]
        self.h["icu_beds"] = None
        if icu_lines:
            n = int(sum(b[k]["beds"] for k, _ in icu_lines))
            self.h["icu_beds"] = n
            self.h["icu_lines"] = icu_lines
            only8 = len(icu_lines) == 1 and not any(_label(s["label_in_report"]) and "NEONATAL" in _label(s["label_in_report"]).upper() for s in h["special_care_units"])
            a["icu_beds"] = A(n, "beds", "measured", f"{HC}; Worksheet S-3 Part I column 2, " + " + ".join(f"line {ln} {k.replace('_', ' ')} ({int(b[k]['beds'])})" for k, ln in icu_lines),
                              note="Critical-care beds on the cost report's intensive-care lines 8-11. "
                                   + ("The report has a single intensive-care line and no separate neonatal or pediatric line, so this figure may include neonatal and pediatric intensive care."
                                      if only8 else "Neonatal and pediatric intensive care are reported on line 12 and its subscripts (separate attributes when labelled)."), **kw)
        for s in h["special_care_units"]:
            lab = (_label(s["label_in_report"]) or "").upper()
            if s["s3_line"].startswith("012") and s.get("beds"):
                key = "nicu_beds" if "NEONATAL" in lab else "picu_beds" if "PEDIATRIC" in lab else None
                if key and key not in a:
                    a[key] = A(int(s["beds"]), "beds", "measured", f"{HC}; Worksheet S-3 Part I line {int(s['s3_line'][:3])}{'.' + s['s3_line'][3:] if s['s3_line'][3:] != '00' else ''} column 2 "
                               f"(other special care; labelled '{_label(s['label_in_report'])}' on Worksheet A line {int(s['worksheet_a_line'][:3])}"
                               f"{'.' + s['worksheet_a_line'][3:] if s['worksheet_a_line'][3:] != '00' else ''})", **kw)
        ap = b.get("adults_and_pediatrics") or {}
        if ap.get("beds"):
            a["routine_beds"] = A(int(ap["beds"]), "beds", "measured", f"{HC}; Worksheet S-3 Part I line 1 column 2 (adults & pediatrics routine beds)", **kw)
        if tot.get("discharges_total"):
            a["inpatient_discharges_per_year"] = A(int(tot["discharges_total"]), "discharges/year", "measured", f"{HC}; Worksheet S-3 Part I line 14 column 15", **kw)
        if tot.get("inpatient_days_total"):
            a["inpatient_days_per_year"] = A(int(tot["inpatient_days_total"]), "patient-days/year", "measured", f"{HC}; Worksheet S-3 Part I line 14 column 8", **kw)
        if tot.get("discharges_total") and tot.get("inpatient_days_total"):
            a["inpatient_alos_days"] = A(round(tot["inpatient_days_total"] / tot["discharges_total"], 2), "days", "measured",
                                         f"{HC}; Worksheet S-3 Part I line 14: total inpatient days {int(tot['inpatient_days_total'])} / total discharges {int(tot['discharges_total'])}",
                                         note="All inpatients of this hospital (not only ED admissions). patient.shared.inpatient_los_days uses the national NHAMCS stay length of ED admissions.", **kw)
        if tot.get("bed_days_available") and tot.get("inpatient_days_total"):
            occ = tot["inpatient_days_total"] / tot["bed_days_available"]
            note = "Annual average occupancy of available beds; a calibration anchor for boarding."
            if occ > 1:
                note = (f"AS REPORTED, and above 1: the cost report lists more inpatient days than bed days available ({int(tot['inpatient_days_total'])} vs {int(tot['bed_days_available'])}), "
                        "so its 'beds available' understates the beds actually in use. Read it as 'full'; inpatient_occupancy_hhs (staffed beds, weekly reports) is the usable figure for calibration.")
            a["inpatient_occupancy"] = A(round(occ, 3), "fraction", "measured",
                                         f"{HC}; Worksheet S-3 Part I line 14: inpatient days {int(tot['inpatient_days_total'])} / bed days available {int(tot['bed_days_available'])}", note=note, **kw)
        # emergency cost centre: line 91 and its subscripts
        ed = [v for k, v in sorted(c.items()) if k.startswith("091")]
        self.h["ed"] = None
        if ed and any(v.get("direct_expense_wsA_col7") for v in ed):
            sm = lambda f: sum(v.get(f) or 0.0 for v in ed)  # noqa: E731
            lines = " + ".join(f"line {int(v['cms_line'][:3])}{'.' + v['cms_line'][3:] if v['cms_line'][3:] != '00' else ''} '{_label(v['label_in_report'])}'" for v in ed)
            direct, sal, after = sm("direct_expense_wsA_col7"), sm("salaries_wsA_col1"), sm("cost_after_overhead_wsB1_col26")
            charges = sm("inpatient_charges_wsC1_col6") + sm("outpatient_charges_wsC1_col7")
            self.h["ed"] = dict(direct=direct, salaries=sal, after=after, lines=lines)
            a["ed_direct_cost_per_year"] = A(int(direct), "usd/year", "measured", f"{HC}; Worksheet A {lines}, column 7 (net expenses for allocation); of which salaries (column 1) {int(sal)}", **kw)
            a["ed_salaries_per_year"] = A(int(sal), "usd/year", "measured", f"{HC}; Worksheet A {lines}, column 1 (salaries)",
                                          note="Salaries of staff charged to the emergency cost centre (nurses, technicians, clerks and any employed providers). Physicians who bill "
                                               "professional fees through a separate practice plan are not in it. A calibration target for the modelled ED labour cost.", **kw)
            if after:
                a["ed_cost_after_overhead_per_year"] = A(int(after), "usd/year", "measured", f"{HC}; Worksheet B Part I {lines}, column 26, cost after step-down allocation of general service (overhead) cost centres",
                                                         note="Excludes ancillary departments used by ED patients (laboratory, imaging, pharmacy) and physician professional fees.", **kw)
                if self.visits:
                    a["ed_cost_per_visit"] = A(round(after / self.visits, 0), "usd/visit", "measured",
                                               f"{HC}; Worksheet B Part I {lines} column 26 ({int(after)}) / {self.visits} ED visits (CMS Care Compare OP-22 denominator)",
                                               note=f"Direct cost only: {direct / self.visits:.0f} usd/visit. ED cost centre only, no ancillaries.", **kw)
            if charges:
                ccr = ed[0].get("cost_to_charge_wsC1_col9")
                a["ed_gross_charges_per_year"] = A(int(charges), "usd/year", "measured", f"{HC}; Worksheet C Part I {lines}, columns 6+7 (inpatient + outpatient charges)"
                                                   + (f"; cost-to-charge ratio column 9 = {ccr}" if ccr else ""), note="List charges, not payments.", **kw)
        else:
            self.miss("ed_direct_cost_per_year / ed_salaries_per_year", "the cost report has no Worksheet A line 91 (Emergency) expense", "ED cost targets and ED space fixed costs unavailable")
        r = c.get("03000")
        if r and r.get("cost_after_overhead_wsB1_col26") and ap.get("inpatient_days_total"):
            a["routine_cost_per_patient_day"] = A(round(r["cost_after_overhead_wsB1_col26"] / ap["inpatient_days_total"], 0), "usd/patient-day", "measured",
                                                  f"{HC}; Worksheet B Part I line 30 column 26 ({int(r['cost_after_overhead_wsB1_col26'])}) / Worksheet S-3 Part I line 1 column 8 "
                                                  f"({int(ap['inpatient_days_total'])} adults & pediatrics days)", note="Routine (room, board, nursing) cost only; no ancillaries.", **kw)
        if icu_lines:
            a_line = {8: "03100", 9: "03200", 10: "03300", 11: "03400"}
            cost = sum((c.get(a_line[ln]) or {}).get("cost_after_overhead_wsB1_col26") or 0.0 for _, ln in icu_lines)
            days = sum(b[k].get("inpatient_days_total") or 0.0 for k, _ in icu_lines)
            self.h["icu_cost"] = cost
            if cost and days:
                a["icu_cost_per_patient_day"] = A(round(cost / days, 0), "usd/patient-day", "measured",
                                                  f"{HC}; Worksheet B Part I lines {'+'.join(str(ln + 23) for _, ln in icu_lines)} column 26 ({int(cost)}) / Worksheet S-3 Part I lines "
                                                  f"{'+'.join(str(ln) for _, ln in icu_lines)} column 8 ({int(days)} days)", **kw)
        if h.get("net_patient_revenue_wsG3_line3"):
            a["net_patient_revenue_per_year"] = A(int(h["net_patient_revenue_wsG3_line3"]), "usd/year", "measured",
                                                  f"{HC}; Worksheet G-3 line 3; total operating expense (line 4) {int(h.get('total_operating_expense_wsG3_line4') or 0)}", **kw)
        if tot.get("employees_on_payroll_fte"):
            a["fte_employees"] = A(round(tot["employees_on_payroll_fte"], 2), "FTE", "measured", f"{HC}; Worksheet S-3 Part I line 14 column 10 (employees on payroll, hospital)",
                                   note="Hospital-wide, all departments and occupations. The cost report has no FTE by department or by occupation.", **kw)
        if tot.get("interns_residents_fte"):
            a["residents_fte"] = A(round(tot["interns_residents_fte"], 2), "FTE", "measured", f"{HC}; Worksheet S-3 Part I line 14 column 9 (interns and residents, hospital)",
                                   note="All training programmes of the hospital, not emergency medicine alone. Residents are NOT in the clinician roster (they do not bill Medicare); "
                                        "this is the only public count of them.", **kw)
        else:
            self.miss("residents_fte", "Worksheet S-3 Part I line 14 column 9 is empty (no approved teaching programme reported)", "attribute left out")

    # ---- provider of services ---------------------------------------------------------------
    def provider_of_services(self):
        p = self.E["pos"]
        self.or_rooms = None
        if not p:
            self.miss("Provider of Services file (operating rooms, cath labs, RN FTE, certified beds)", self.src_unavailable("pos"), "attributes left out")
            return
        row, src = p["row"], p["source"]
        PC = f"CMS Provider of Services file (QIES, hospital & other facilities), {src['release']}, PRVDR_NUM {self.ccn}"
        kw = dict(url=src["landing"], file=self.F("pos"))
        a = self.attrs
        zero = []
        for key, field, unit, note in [
                ("operating_rooms", "OPRTG_ROOM_CNT", "rooms", None),
                ("cath_lab_rooms", "CRDC_CTHRTZTN_PRCDR_ROOMS_CNT", "rooms", None),
                ("certified_beds_pos", "CRTFD_BED_CNT", "beds", "Medicare-certified beds at the last survey; differs from the cost report's beds available."),
                ("rn_fte", "RN_CNT", "FTE", "Registered nurses, hospital-wide (all units), as recorded at the last certification survey - not the ED's nurses. Nurses are not in the clinician roster."),
                ("lpn_fte", "LPN_LVN_CNT", "FTE", "Licensed practical / vocational nurses, hospital-wide, at the last survey.")]:
            v = _num(row.get(field))
            if v:
                a[key] = A(int(v) if float(v).is_integer() and unit != "FTE" else round(v, 2), unit, "measured", f"{PC}; {field}", note=note, **kw)
            else:
                zero.append(f"{field}={row.get(field)!r}")
        if zero:
            self.miss("Provider of Services counts: " + ", ".join(zero), "the file carries zero or blank for this hospital, which is a non-report, not a count of zero",
                      "attributes left out (" + ", ".join(k for k, f in [("operating_rooms", "OPRTG_ROOM_CNT"), ("cath_lab_rooms", "CRDC_CTHRTZTN_PRCDR_ROOMS_CNT"),
                                                                              ("certified_beds_pos", "CRTFD_BED_CNT"), ("rn_fte", "RN_CNT"), ("lpn_fte", "LPN_LVN_CNT")]
                                                         if any(z.startswith(f + "=") for z in zero)) + ")")
        self.or_rooms = int(_num(row.get("OPRTG_ROOM_CNT")) or 0) or None
        cb, lb = _num(row.get("CRTFD_BED_CNT")), (self.attrs.get("licensed_beds") or {}).get("value")
        if cb and lb and abs(cb - lb) / lb > 0.05:
            self.disagreements.append({"what": "Hospital beds", "figures": f"cost report beds available {lb} (licensed_beds); Provider of Services certified beds {int(cb)} (certified_beds_pos)",
                                       "model_uses": "neither directly - the modelled inpatient pool is sized from ED admissions (ward_pool_beds)"})

    # ---- HHS weekly capacity ----------------------------------------------------------------
    def hhs(self):
        e = self.E["hhs_capacity"]
        self.hhs_month = None
        if not e:
            self.miss("HHS weekly facility series (ED visits per week, staffed beds, occupancy)", self.src_unavailable("hhs_capacity"),
                      "no hospital-specific weekly ED volume, seasonality or occupancy series; the national assumed month profile stays in force")
            return
        s, src = e["summary"], e["source"]
        win = s["window"]
        base = (f"HHS 'COVID-19 Reported Patient Impact and Hospital Capacity by Facility' (healthdata.gov {src['dataset_id']}), hospital_pk {self.ccn} "
                f"{e['facility_in_file'].get('hospital_name')}")
        kw = dict(url=src["landing"], file=self.F("hhs_capacity"))
        a = self.attrs
        vint = "Vintage: hospital reporting to HHS stopped being mandatory after 2024-04-30, so this is the latest public weekly series, not the current year."
        ed, ew = s.get("ed_visits_per_week"), s.get("ed_visits_window")
        if ed and ed["n_weeks"] >= 26:
            ec = f"{base}; field previous_day_total_ed_visits_7_day_sum, {ed['n_weeks']} weeks {ew['first_week']} to {ew['last_week']}"
            stale = ew["last_week"] != win["last_week"]
            en = vint + (f" The hospital stopped reporting this optional field after the week of {ew['last_week']}; the window is the last 52 weeks that have a value." if stale else "")
            if s["ed_visits_weeks_excluded"]:
                en += f" {len(s['ed_visits_weeks_excluded'])} week(s) excluded as partial reports (outside 0.5-1.5 x the median)."
            a["ed_visits_per_week_mean"] = A(round(ed["mean"], 1), "visits/week", "measured", ec + "; mean", range=[ed["p10"], ed["p90"]],
                                             note=en + f" range = 10th-90th percentile of the weekly values. Annualised: {s['ed_visits_annualised']} visits.", **kw)
            a["ed_visits_per_week_min"] = A(ed["min"], "visits/week", "measured", ec + "; lowest week", note=vint, **kw)
            a["ed_visits_per_week_max"] = A(ed["max"], "visits/week", "measured", ec + "; highest week", note=vint, **kw)
            a["ed_visits_per_week_cv"] = A(ed["cv"], "coefficient of variation", "measured", ec + "; standard deviation / mean of the weekly totals",
                                           note="Week-to-week variability of ED volume; a check on the simulated arrival process (Poisson noise alone gives about "
                                                f"{1 / math.sqrt(ed['mean']):.3f} at this volume; the rest is seasonality and real variation). " + vint, **kw)
            a["ed_visits_per_year_hhs"] = A(int(s["ed_visits_annualised"]), "visits/year", "measured", ec + "; weekly mean x 365.25 / 7",
                                            note="Second public figure for ED volume; the model uses ed_visits_per_year_cms (see the note on patient.shared.arrivals_per_day). " + en, **kw)
            mp = s.get("ed_visits_month_profile")
            if mp:
                self.hhs_month = dict(profile=mp["profile_jan0"], weeks=mp["weeks_per_month"], cite=ec, note=en, kw=kw)
                a["ed_visits_month_profile_hhs"] = A(mp["profile_jan0"], "multiplier (mean 1)", "measured", ec + "; mean weekly visits by calendar month / mean of the 12 monthly means",
                                                     index="month (January first)", note=f"One year of data ({mp['weeks_per_month']} weeks per month). " + en, **kw)
            if self.visits:
                ratio = s["ed_visits_annualised"] / self.visits
                if abs(ratio - 1) > 0.10:
                    self.disagreements.append({
                        "what": "Annual ED visits",
                        "figures": f"CMS Care Compare OP-22 denominator {self.visits} (ed_visits_per_year_cms); HHS weekly series annualised {s['ed_visits_annualised']} "
                                   f"(ed_visits_per_year_hhs, weeks {ew['first_week']} to {ew['last_week']}), a ratio of {ratio:.2f}",
                        "model_uses": "the CMS OP-22 denominator (most recent full calendar year, the definition behind the LWBS rate the model is validated against). The two series "
                                      "define an 'ED visit' differently and cover different periods; why they differ this much for this hospital is not established. The HHS series "
                                      "is used only for the shape over the year and week-to-week variability, never for the level."})
        else:
            self.miss("ed_visits_per_week_* (HHS)", "fewer than 26 weeks of the optional ED-visit field were ever reported by this hospital", "no weekly ED series; national assumed month profile stays in force")
        occ = s.get("inpatient_occupancy")
        cw = f"{win['weeks']} weeks {win['first_week']} to {win['last_week']}"
        if occ:
            a["inpatient_occupancy_hhs"] = A(round(occ["mean"], 3), "fraction", "measured", f"{base}; inpatient_beds_used_7_day_avg / inpatient_beds_7_day_avg, mean of {cw}",
                                             range=[occ["min"], occ["max"]], note="Staffed inpatient beds occupied, weekly; range = lowest to highest week. " + vint, **kw)
            a["staffed_inpatient_beds_hhs"] = A(round(s["inpatient_beds"]["mean"], 1), "beds", "measured", f"{base}; inpatient_beds_7_day_avg, mean of {cw}",
                                                note="Staffed inpatient beds as reported weekly to HHS (adult and pediatric); a different definition from the cost report's beds available. " + vint, **kw)
            hc = (self.attrs.get("inpatient_occupancy") or {}).get("value")
            if hc and abs(hc - occ["mean"]) > 0.05:
                self.disagreements.append({"what": "Inpatient occupancy",
                                           "figures": f"cost report {hc} (inpatient_occupancy, days / bed days available, fiscal year); HHS weekly {occ['mean']:.3f} "
                                                      f"(inpatient_occupancy_hhs, staffed beds used / staffed beds, {win['first_week']} to {win['last_week']})",
                                           "model_uses": "neither as an input (the ward pool starts at ward_initial_occupancy, a model parameter); both are validation targets. "
                                                         + ("The cost-report figure is above 1 and cannot be a target; use the HHS figure." if hc > 1 else "They differ in bed definition and year.")})
        io = s.get("adult_icu_occupancy")
        if io and s.get("adult_icu_beds"):
            a["staffed_adult_icu_beds_hhs"] = A(round(s["adult_icu_beds"]["mean"], 1), "beds", "measured", f"{base}; total_staffed_adult_icu_beds_7_day_avg, mean of {cw}", note=vint, **kw)
            a["adult_icu_occupancy_hhs"] = A(round(io["mean"], 3), "fraction", "measured",
                                             f"{base}; staffed_adult_icu_bed_occupancy_7_day_avg / total_staffed_adult_icu_beds_7_day_avg, mean of {cw}", range=[io["min"], io["max"]], note=vint, **kw)

    # ---- roster -----------------------------------------------------------------------------
    def roster(self):
        r = self.E["roster"]
        if not r:
            self.miss("Clinician roster (affiliated clinicians by specialty, ED provider pool)", self.src_unavailable("roster"), "roster attributes left out")
            return
        comp = r["source"]["components"]
        fa, nd = comp["facility_affiliation"], comp["national_downloadable_file"]
        base = (f"CMS Doctors and Clinicians 'Facility Affiliation Data' (Provider Data Catalog {fa['dataset_id']}, release {fa['release']}), rows with "
                f"'Facility Affiliations Certification Number' == '{self.ccn}', joined on NPI to the 'National Downloadable File' ({nd['dataset_id']}, release {nd['release']})")
        kw = dict(url=fa["landing"], file=self.F("roster"))
        n, a = r["counts"], self.attrs
        cover = ("Medicare-enrolled clinicians that CMS affiliates with this hospital. Not covered: residents and fellows (see residents_fte), nurses (see rn_fte), clinicians "
                 "not enrolled in Medicare. Affiliation is not hours: ")
        a["clinicians_affiliated_total"] = A(n["clinicians_affiliated_total"], "clinicians", "measured", base + "; distinct NPIs",
                                             note=cover + f"{n['affiliated_with_other_hospitals_too']} of them are affiliated with at least one other hospital too.", **kw)
        a["physicians_affiliated"] = A(n["physicians_total"], "clinicians", "measured", base + "; distinct NPIs whose pri_spec is a physician specialty",
                                       note="Excludes nurse practitioners, physician assistants, nurse anaesthetists, therapists, psychologists and other non-physician specialties "
                                            "(list in the extract's `definitions`).", **kw)
        a["apps_affiliated"] = A(n["apps_total"], "clinicians", "measured", base + f"; pri_spec NURSE PRACTITIONER ({n['nurse_practitioners']}) or PHYSICIAN ASSISTANT ({n['physician_assistants']})",
                                 note="All departments of the hospital, not the ED.", **kw)
        a["em_physicians"] = A(n["em_physicians"], "clinicians", "measured", base + "; pri_spec == 'EMERGENCY MEDICINE'",
                               note=f"Attending-level emergency physicians affiliated with the hospital - the pool the ED's attending shifts are drawn from, not the number on shift. "
                                    f"{n['em_physicians_only_this_hospital']} are affiliated with this hospital only; the others also work elsewhere. "
                                    f"{n['em_physicians_secondary_specialty']} more list emergency medicine as a secondary specialty"
                                    + (f" and {n['em_physicians_nppes_taxonomy_only']} more carry an emergency-medicine NPPES taxonomy code only" if n.get("em_physicians_nppes_taxonomy_only") is not None else "")
                                    + " (not counted here). Emergency-medicine residents are not included.", **kw)
        if n.get("em_apps") is not None:
            mu = comp["medicare_by_provider_and_service"]
            a["em_apps"] = A(n["em_apps"], "clinicians", "measured",
                             base + f"; pri_spec NURSE PRACTITIONER or PHYSICIAN ASSISTANT AND at least 11 emergency-department visit services (HCPCS 99281-99285, place of service facility) "
                                    f"billed under the clinician's own NPI in {mu['dataset']} ({n['em_apps_nurse_practitioners']} nurse practitioners, {n['em_apps_physician_assistants']} physician assistants)",
                             note="A LOWER BOUND on the ED's advanced practice providers: CMS gives no ED specialty for them, so they are found through their own Medicare billing. "
                                  "Visits billed under a supervising physician, non-Medicare visits and suppressed rows (10 or fewer beneficiaries) are invisible. "
                                  + (f"NPPES taxonomy codes add {n['apps_with_emergency_nppes_taxonomy']} (the taxonomy has no emergency code for nurse practitioners or physician assistants)."
                                     if n.get("apps_with_emergency_nppes_taxonomy") is not None else "NPPES was not available."), **kw)
        else:
            self.miss("em_apps", r["source"]["unavailable"].get("medicare_by_provider_and_service", "Medicare by-provider-and-service file unavailable"),
                      "emergency-medicine NPs/PAs cannot be told apart from other NPs/PAs; attribute left out")
        for key in ["hospitalists", "radiologists", "critical_care_physicians", "anesthesiologists"]:
            a[key + "_affiliated"] = A(n[key], "clinicians", "measured", base + f"; pri_spec in the '{key}' group (see the extract's by_specialty table)", **kw)

    # ---- payment context --------------------------------------------------------------------
    def rates_context(self):
        r = self.E["cms_rates"]
        if not r:
            return
        row = r["impact_file_row"]
        base = f"CMS IPPS FY 2027 final rule + correction notice, Impact File row with Provider Number == '{self.ccn}' ({row.get('Name')})"
        kw = dict(url=r["source"]["landing"], file=self.F("cms_rates"))
        a = self.attrs
        a["ipps_wage_index"] = A(row["FY 2027 Wage Index"], "index", "measured", base + "; 'FY 2027 Wage Index'"
                                 + f"; geographic labour market area {row.get('Geographic Labor Market Area')}, payment area {row.get('Payment Labor Market Area')}, reclassification '{row.get('RECLASS')}'", **kw)
        a["medicare_case_mix_index"] = A(row["TACMIV44"], "index", "measured", base + "; TACMIV44 (transfer-adjusted case-mix index, MS-DRG version 44)",
                                         note=f"Medicare discharges only ({row.get('Bills')} bills).", **kw)
        if row.get("Resident to Bed Ratio") is not None:
            a["resident_to_bed_ratio"] = A(row["Resident to Bed Ratio"], "ratio", "measured", base + "; 'Resident to Bed Ratio'", **kw)
        if row.get("Medicare Percentage") is not None:
            a["medicare_share_of_inpatient_days"] = A(row["Medicare Percentage"], "fraction", "measured", base + "; 'Medicare Percentage'",
                                                      note="Inpatient days, not ED visits. The ED payer mix in the model is national (patient.shared.payer_mix).", **kw)
        if row.get("Medicaid Percentage") is not None:
            a["medicaid_share_of_inpatient_days"] = A(row["Medicaid Percentage"], "fraction", "measured", base + "; 'Medicaid Percentage'", **kw)

    def quality(self):
        q = self.E["quality"]
        if not q or not q.get("hcahps"):
            return
        src = q["source"]["hcahps"]
        for r in q["hcahps"]:
            if r.get("HCAHPS Measure ID") == "H_STAR_RATING" and _num(r.get("Patient Survey Star Rating")):
                self.attrs["hcahps_summary_star_rating"] = A(
                    int(_num(r["Patient Survey Star Rating"])), "stars (1-5)", "measured",
                    f"CMS 'Patient survey (HCAHPS) - Hospital' (Provider Data Catalog {src['dataset_id']}, release {src['release']}), Facility ID == '{self.ccn}', measure H_STAR_RATING; "
                    f"{r.get('Number of Completed Surveys')} completed surveys, period {r.get('Start Date')}-{r.get('End Date')}",
                    url=src["landing"], file=self.F("quality"), note="Inpatient survey - context only, not an ED measure and not a simulator input.")

    # ---- sizes that are not public: stated rules ---------------------------------------------
    def ed_and_ward_sizing(self):
        a = self.attrs
        visits = self.visits or (a.get("ed_visits_per_year_hhs") or {}).get("value")
        if not visits:
            raise SystemExit(f"CCN {self.ccn}: no public ED visit count (Care Compare OP-22 denominator and HHS weekly series both missing) - cannot size the twin")
        self.visits_used = int(visits)
        self.arrivals_per_day = (self.visits / self.visit_days) if self.visits else visits / 365.25
        vsrc = "the CMS OP-22 denominator" if self.visits else "the HHS weekly series, annualised"
        pub = self.published
        n = int(pub["ed_treatment_spaces"]["value"]) if "ed_treatment_spaces" in pub else max(8, round(visits / VISITS_PER_SPACE))
        resus = int(pub["resus_bays"]["value"]) if "resus_bays" in pub else min(8, max(2, round(0.06 * n)))
        fast = min(12, max(2, round(0.10 * n)))
        peds = 0
        main = n - resus - fast - peds
        triage = min(4, max(1, math.ceil(visits / 30000)))
        scan = max(1, round(visits / 40000))
        amb = min(12, max(2, round(visits / 10000)))
        bench = (f"{RULE}treatment spaces = annual ED visits ({self.visits_used}, {vsrc}) / {VISITS_PER_SPACE} visits per space per year. {VISITS_PER_SPACE} is anchored on the two "
                 "hospitals for which a published count was found: Mayo Clinic Rochester (75 rooms, about 84,800 visits: 1,130 per room) and RWJUH New Brunswick ('more than 100' spaces, "
                 "81,000-95,000 visits: 810-950 per space). ED planning guides quote a wider span, roughly 1,100-2,000, not checked against a primary source in this build. "
                 "This hospital's real number of treatment spaces was searched for and not found")
        a["ed_visits_per_year"] = A(self.visits_used, "visits/year", "measured",
                                    self.visit_cite if self.visits else a["ed_visits_per_year_hhs"]["citation"], note="calibration anchor (same figure as ed_visits_per_year_cms)"
                                    if self.visits else "calibration anchor (HHS weekly series; no CMS count)", **(self.visit_kw if self.visits else {}))
        a["ed_treatment_spaces"] = pub.get("ed_treatment_spaces") or A(
            n, "spaces", "assumed", bench, range=[max(8, round(visits / 1500)), round(visits / 800)],
            note="NOT PUBLIC. range = the same rule at 1,500 and 800 visits per space. A candidate for calibration against the LWBS rate and ED time.")
        a["resus_bays"] = pub.get("resus_bays") or A(resus, "bays", "assumed", f"{RULE}6 percent of treatment spaces (the share in the RWJUH model), at least 2, at most 8")
        a["fast_track_spaces"] = A(fast, "spaces", "assumed", f"{RULE}10 percent of treatment spaces (the share in the RWJUH model), at least 2, at most 12; whether the hospital runs a fast track is not in any public dataset")
        a["peds_ed_spaces"] = A(peds, "spaces", "assumed", f"{RULE}0 - no public dataset says whether the hospital has a separate pediatric ED or how large it is; children are seen in the main ED in the model")
        a["adult_main_bays"] = A(main, "bays", "assumed", f"{RULE}treatment spaces minus resuscitation, fast-track and pediatric spaces ({n} - {resus} - {fast} - {peds})")
        ho = [0, max(2, round(0.08 * n)), max(4, round(0.16 * n))]
        a["hallway_overflow_spaces"] = A(ho, "spaces", "assumed", f"{RULE}overflow_bays action levels = 0, 8 and 16 percent of treatment spaces (as in the RWJUH model)", index="level")
        a["triage_rooms"] = A(triage, "rooms", "assumed", f"{RULE}one triage room per 30,000 annual visits, rounded up, between 1 and 4")
        a["ambulance_bay_slots"] = A(amb, "ambulances", "assumed", f"{RULE}one slot per 10,000 annual visits, between 2 and 12 (drawing only; not simulated)")
        a["ct_scanners_ed"] = A(scan, "units", "assumed", f"{RULE}one ED CT scanner per 40,000 annual visits, at least 1 (the RWJUH model has 2 for about 81,000); the hospital's scanner count is not public")
        a["xray_rooms_ed"] = A(scan, "units", "assumed", f"{RULE}one ED X-ray room per 40,000 annual visits, at least 1; not public")
        a["ultrasound_units"] = A(scan, "units", "assumed", f"{RULE}one per 40,000 annual visits, at least 1 (drawing only; not simulated)")
        a["mri_units"] = A(1, "units", "assumed", f"{RULE}1 in main radiology (drawing only; not simulated)")
        a["bays_delta_step"] = A(4, "bays", "assumed", "Simulator model parameter: structural action step (same as the RWJUH model)")
        a["ward_beds_delta_step"] = A(8, "beds", "assumed", "Simulator model parameter: structural action step (same as the RWJUH model)")
        a["min_main_bays"] = A(max(4, round(0.12 * main)), "bays", "assumed", "Simulator model parameter: bays_delta cannot take the main ED below this; 12 percent of main bays (8 of 68 in the RWJUH model)")

        # ---- inpatient pool visible to the ED, sized the way the RWJUH model's pool is (sim/BASELINE.md, calibration record)
        P = self.shared["patient"]
        mix = P["shared"]["acuity_mix"]["value"]
        padm = [P["variants"][f"esi{i}"]["attributes"]["p_admit"]["value"] for i in range(1, 6)]
        share = sum(m * p for m, p in zip(mix, padm))
        los = P["shared"]["inpatient_los_days"]["value"]
        adm = self.arrivals_per_day * share
        need = adm * los
        ref_ratio = 0.926      # beds in use / pool beds in the RWJUH model: 222 x 0.1325 x 5.29 = 155.6 against its 168-bed pool
        total = max(16, int(round(need / ref_ratio / 8.0)) * 8)
        icu_b = sd_b = max(4, int(round(total / 7 / 8.0)) * 8) if total >= 56 else max(2, round(total / 7))
        ward_b = total - icu_b - sd_b
        nu = max(1, math.ceil(ward_b / WARD_UNIT_BEDS))
        ward_units = [ward_b // nu + (1 if i < ward_b % nu else 0) for i in range(nu)]
        self.pool = dict(ward_units=ward_units, icu=icu_b, stepdown=sd_b, total=total, admissions_per_day=adm, need=need)
        how = (f"{RULE}ED admissions per day = arrivals {self.arrivals_per_day:.1f} x admitted share {share:.4f} (national NHAMCS acuity mix x admission probability by acuity, "
               f"catalog/patient.yaml) = {adm:.1f}; x {los} days national stay length of ED admissions = {need:.0f} beds in use; / {ref_ratio} (the ratio of beds in use to pool beds in "
               f"the RWJUH model: 155.6 against its 168-bed pool, sim/BASELINE.md calibration record) = {need / ref_ratio:.0f}, rounded to a multiple of 8 = {total}")
        lb = (a.get("licensed_beds") or {}).get("value")
        pn = ("The modelled pool is the part of the hospital that ED admissions turn over in, not the hospital's bed count" + (f" ({lb} beds available on the cost report)" if lb else "")
              + ". The hospital's real ED admission rate and length of stay of ED admissions are not public; both are national values here.")
        a["ward_pool_beds"] = A(self.pool["total"], "beds", "assumed", how, note=pn)
        a["ward_beds_for_ed_admissions"] = A(sum(self.pool["ward_units"]), "beds", "assumed", f"{RULE}general ward part of the modelled pool: ward_pool_beds minus ICU and step-down "
                                             f"({self.pool['total']} - {icu_b} - {sd_b})")
        a["ward_pool_icu_beds"] = A(icu_b, "beds", "assumed", f"{RULE}one seventh of the pool rounded to a multiple of 8, as in the RWJUH model (24 of 168)")
        a["ward_pool_stepdown_beds"] = A(sd_b, "beds", "assumed", f"{RULE}one seventh of the pool rounded to a multiple of 8, as in the RWJUH model (24 of 168)")
        a["min_ward_beds"] = A(max(8, round(0.1 * self.pool["total"] / 8) * 8), "beds", "assumed", "Simulator model parameter: ward_beds_delta cannot take the pool below this; about 10 percent of the pool (16 of 168 in the RWJUH model)")
        if lb and self.pool["total"] > 0.6 * lb:
            self.notes.append(f"The modelled ward pool ({self.pool['total']} beds) is more than 60 percent of the hospital's beds available ({lb}); the national admission rate or stay length may overstate this hospital's ED admissions.")
        self.counts = dict(adult_main_bays=main, resus_bays=resus, fast_track_spaces=fast, peds_ed_spaces=peds, triage_rooms=triage, ct=scan, xray=scan, ultrasound=scan, mri=1,
                           ambulance_slots=amb, ward_units=self.pool["ward_units"], icu_beds=icu_b, stepdown_beds=sd_b,
                           or_rooms=self.or_rooms or 12, recovery_beds=round(1.5 * (self.or_rooms or 12)))
        self.n_spaces = n
        for k, v in pub.items():
            if k not in a:
                a[k] = v

    def model_parameters(self):
        a = self.attrs
        a["ward_pool_los_factor"] = A(0.85, "x inpatient LOS", "assumed",
                                      "Simulator model parameter: share of an ED admission's inpatient stay that is spent in the modelled ward pool. 0.85 is the value calibrated "
                                      "for the RWJUH model; with the pool sized by the same rule it puts long-run pool occupancy near 0.83-0.85. A calibration knob - fit it to "
                                      "inpatient_occupancy_hhs / inpatient_occupancy")
        a["ward_initial_occupancy"] = A(0.85, "fraction", "assumed", "Simulator model parameter: share of the ward pool occupied at episode start (warm start); same as the RWJUH model")
        a["ward_pool_room_types"] = A(["ward_unit", "icu_bed", "stepdown_bed"], "room types", "assumed", "Simulator model parameter: layout room types whose capacity forms the inpatient pool available to ED admissions")
        a["ed_bay_room_types"] = A({"resus_bay": "resus", "treatment_bay": "main", "fast_track": "fast", "peds_ed": "peds"}, "map", "assumed",
                                   "Simulator model parameter: layout room types that are ED treatment spaces and the stream each serves")

    # ---- overrides of hospital-specific values that live in the shared catalog files ---------
    def override_arrivals(self):
        o = self.overrides
        hh = (self.attrs.get("ed_visits_per_year_hhs") or {}).get("value")
        if self.visits:
            v = round(self.visits / self.visit_days)
            rng = sorted([v, round(hh / 365.25)]) if hh else None
            o["patient.shared.arrivals_per_day"] = A(
                v, "patients/day", "measured", self.visit_cite.replace("; denominator ('Sample') of measure OP_22 = total ED visits reported for", "; OP_22 denominator, total ED visits in")
                + f": {self.visits} / {self.visit_days} days", range=rng,
                note="All ED visits reported under the CMS number (every campus and every age it covers)."
                     + (f" Other end of the range = the HHS weekly series annualised ({hh}) / 365.25; see the disagreement note in the data report." if hh else "")
                     + " Hourly and weekday variation are national (NHAMCS) profiles.", **self.visit_kw)
        else:
            src = self.attrs["ed_visits_per_year_hhs"]
            o["patient.shared.arrivals_per_day"] = A(round(hh / 365.25), "patients/day", "measured", src["citation"] + " / 365.25", url=src.get("url"), file=src.get("file"),
                                                     note="No CMS OP-22 denominator for this hospital; HHS weekly series used instead. " + src.get("note", ""))
        if self.hhs_month:
            m = self.hhs_month
            o["patient.shared.arrival_month_profile"] = A(
                m["profile"], "multiplier (mean 1)", "measured", m["cite"] + "; mean weekly visits by calendar month / mean of the 12 monthly means",
                index="month (January first)", note=f"This hospital's own seasonal shape, from ONE year of weekly reports ({m['weeks']} weeks per month), so it carries that year's noise. "
                                                  "Replaces the assumed national winter-peaked profile in catalog/patient.yaml. " + m["note"], **m["kw"])
        else:
            self.miss("patient.shared.arrival_month_profile (hospital-specific seasonality)", "no usable HHS weekly ED series", "the assumed national month profile in catalog/patient.yaml stays in force")

    def override_revenue(self):
        r = self.E["cms_rates"]
        if not r:
            why = self.src_unavailable("cms_rates")
            self.miss("Medicare payment rates for this hospital (inpatient revenue per stay, ED visit and imaging payment)", why,
                      "patient.shared.inpatient_revenue, patient.esi*.revenue_ed_visit and equipment.*.revenue_per_use keep the shared-catalog values, which are wage-adjusted for CCN 310038 (RWJUH) - "
                      "treat revenue as assumed for this hospital")
            for i in range(1, 6):
                n = shared_node(self.shared, f"patient.esi{i}.revenue_ed_visit")
                self.overrides[f"patient.esi{i}.revenue_ed_visit"] = A(n["value"], n["unit"], "assumed", f"No IPPS/OPPS wage adjustment available for CCN {self.ccn} ({why}); value carried over from the RWJUH (CCN 310038) wage-adjusted rate")
            n = shared_node(self.shared, "patient.shared.inpatient_revenue")
            self.overrides["patient.shared.inpatient_revenue"] = A(n["value"], n["unit"], "assumed", f"No IPPS Impact File row for CCN {self.ccn} ({why}); value carried over from RWJUH (CCN 310038)")
            return
        c, row, o = r["computed"], r["impact_file_row"], self.overrides
        t1 = r["table_1a_full_update_wage_index_gt_1"]
        F = self.F("cms_rates")
        hsp = row.get("HSP Rate")
        npr, disc = (self.attrs.get("net_patient_revenue_per_year") or {}).get("value"), (self.attrs.get("inpatient_discharges_per_year") or {}).get("value")
        h = self.E["hcris"] or {}
        ipshare = (h.get("inpatient_revenue_wsG2_line28_col1") or 0) / h["total_revenue_wsG2_line28_col3"] if h.get("total_revenue_wsG2_line28_col3") else None
        cross = (f" Cross-check: the cost report gives net patient revenue {npr:,} usd x inpatient share of gross revenue {ipshare:.3f} (Worksheet G-2 line 28) / {disc:,} discharges = about "
                 f"{npr * ipshare / disc:,.0f} usd per discharge, all payers." if npr and disc and ipshare else "")
        o["patient.shared.inpatient_revenue"] = A(
            round(c["payment_at_hospital_cmi"]), "usd/stay", "measured",
            f"CMS IPPS FY 2027 final rule + correction notice: Tables 1A/1D standardized amounts (labor {t1['labor_related']}, nonlabor {t1['nonlabor_related']}, capital {r['table_1d_capital_rate']}) "
            f"and Impact File row for CCN {self.ccn} (wage index {row['FY 2027 Wage Index']}, teaching factor {row.get('TCHOP', 0)}, DSH factor {row.get('DSHOPP', 0)}, capital GAF {row['GAF']}, "
            f"transfer-adjusted case-mix index {c['case_mix_index_TACMIV44']}, uncompensated-care amount per claim {c['uncompensated_care_per_claim']}); {c['formula']}",
            url=r["source"]["landing"], file=F, range=[round(c["payment_at_weight_1"]), round(c["payment_at_hospital_cmi"])],
            note=f"Medicare fee-for-service basis (other payers through payer_revenue_multiplier). BASE-RATE ASSUMPTION: the stay is paid at this hospital's average Medicare case-mix index "
                 f"({c['case_mix_index_TACMIV44']}, all Medicare discharges); medical admissions through the ED are on average lighter, so this is an upper estimate - lower end of range = a DRG weight of 1.0. "
                 f"Payment per unit of DRG weight = {round(c['operating_per_unit_weight'] + c['capital_per_unit_weight'])} usd."
                 + (f" The Impact File lists a hospital-specific rate ({hsp}; provider type {row.get('Provider Type')}): such hospitals are paid the higher of the federal and the hospital-specific "
                    "rate, and only the federal rate is modelled here." if hsp else "") + cross)
        op = {x["hcpcs"]: x for x in r["opps_codes"]}
        adj = c["opps_wage_adjustment"]
        OD = (f"CMS OPPS Addendum B, July 2026 update (national unadjusted payment rate by HCPCS code), wage-adjusted for CCN {self.ccn} as rate x (0.6 x wage index "
              f"{row['FY 2027 Wage Index']} + 0.4) = x{adj}")
        OU = r["source"]["opps_landing"]
        for i, code in ESI_CODE.items():
            x = op[code]
            o[f"patient.esi{i}.revenue_ed_visit"] = A(
                float(x["payment_rate_wage_adjusted"]), "usd/visit", "measured", f"{OD}; HCPCS {code} (APC {x['apc']}), national rate {x['payment_rate_national_unadjusted']}", url=OU, file=F,
                note=f"MAPPING ASSUMPTION: triage level {i} is billed as visit code {code} (level 1 -> critical care first hour, levels 2-5 -> ED visit levels 5-2). In practice the billed level follows "
                     "documented resources, not the triage level. Hospital facility payment on the Medicare basis only: no physician professional fee.")
        pick = {"xray": "71046", "ultrasound": "76700", "mri": "70551"}
        for eq in ["ct", "xray", "ultrasound", "mri"]:
            g = [x for x in r["opps_codes"] if x["group"] == eq and x["payment_rate_wage_adjusted"] == x["payment_rate_wage_adjusted"]]
            vals = [x["payment_rate_wage_adjusted"] for x in g]
            if eq == "ct":
                val = round(sum(vals) / len(vals), 2)
                how = f"unweighted mean over {len(g)} common ED CT codes ({', '.join(x['hcpcs'] for x in g)}; APCs {', '.join(sorted({str(x['apc']) for x in g}))})"
                note = "Unweighted across codes (no ED volume by code is public); range = cheapest to dearest of those codes. "
            else:
                x = op[pick[eq]]
                val = float(x["payment_rate_wage_adjusted"])
                how = f"HCPCS {pick[eq]} (APC {x['apc']}), national rate {x['payment_rate_national_unadjusted']}"
                note = "One representative code; range = the other fetched codes of this modality. "
            si = sorted({x["status_indicator"] for x in g})
            o[f"equipment.{eq}.revenue_per_use"] = A(val, "usd", "measured", f"{OD}; {how}", url=OU, file=F, range=[min(vals), max(vals)],
                                                     note=note + f"Status indicators {si}: packaged or composite when billed with an ED visit, so this is the stand-alone rate and an upper bound "
                                                                 "on the marginal Medicare payment during an ED visit. Facility payment only, no radiologist fee.")

    def override_space_costs(self):
        o, h = self.overrides, self.h
        if not h:
            for s in ["ward_unit", "icu_bed", "triage", "treatment_bay", "resus_bay", "fast_track", "peds_ed", "results_waiting", "hallway_overflow", "stepdown_bed"]:
                n = shared_node(self.shared, f"space.{s}.fixed_cost_per_hour")
                o[f"space.{s}.fixed_cost_per_hour"] = A(n["value"], n["unit"], "assumed", f"No cost report for CCN {self.ccn} ({self.src_unavailable('hcris')}); value carried over from the RWJUH (CCN 310038) cost report")
            return
        HC, kw, HOURS, b, c = h["HC"], h["kw"], h["hours"], h["b"], h["c"]
        cap = self.shared["space"]["variants"]["ward_unit"]["attributes"]["capacity"]["value"]
        r, ap = c.get("03000") or {}, b.get("adults_and_pediatrics") or {}
        ward_bed = icu_bed = None
        if r.get("cost_after_overhead_wsB1_col26") and ap.get("beds"):
            ward_bed = r["cost_after_overhead_wsB1_col26"] / ap["beds"] / HOURS
            o["space.ward_unit.fixed_cost_per_hour"] = A(
                round(ward_bed * cap, 1), "usd/hour", "measured",
                f"{HC}; Worksheet B Part I line 30 (adults & pediatrics) column 26 = {int(r['cost_after_overhead_wsB1_col26'])} usd / {int(ap['beds'])} beds / {HOURS} hours = "
                f"{ward_bed:.1f} usd per bed-hour, times the unit capacity of {cap} beds",
                note="Fully allocated routine cost INCLUDING ward nursing salaries and overhead (ward staff are not modelled separately); excludes ancillaries.", **kw)
        if h.get("icu_beds") and h.get("icu_cost"):
            icu_bed = h["icu_cost"] / h["icu_beds"] / HOURS
            o["space.icu_bed.fixed_cost_per_hour"] = A(
                round(icu_bed, 1), "usd/hour", "measured",
                f"{HC}; Worksheet B Part I lines {'+'.join(str(ln + 23) for _, ln in h['icu_lines'])} column 26 = {int(h['icu_cost'])} usd / {h['icu_beds']} ICU beds (Worksheet S-3 Part I) / {HOURS} hours",
                note="Fully allocated cost including ICU nursing salaries and overhead; excludes ancillaries.", **kw)
        if ward_bed and icu_bed:
            o["space.stepdown_bed.fixed_cost_per_hour"] = A(round((ward_bed * icu_bed) ** 0.5, 1), "usd/hour", "assumed",
                                                            f"Assumed: geometric mean of the measured ward cost per bed-hour ({ward_bed:.1f}) and ICU cost per bed-hour ({icu_bed:.1f}); the cost report has no step-down cost centre")
        orc = (c.get("05000") or {}).get("cost_after_overhead_wsB1_col26")
        if orc and self.or_rooms:
            o["space.operating_room.fixed_cost_per_hour"] = A(
                round(orc / self.or_rooms / HOURS, 1), "usd/hour", "measured",
                f"{HC}; Worksheet B Part I line 50 (operating room) column 26 = {int(orc)} usd / {self.or_rooms} operating rooms (CMS Provider of Services file OPRTG_ROOM_CNT) / {HOURS} hours",
                note="Averaged over all hours of the year including unstaffed nights; includes OR staff salaries. Not used by the ED simulation.", **kw)
        ed = h.get("ed")
        if ed and ed["after"]:
            a = self.attrs
            counts = {"triage": a["triage_rooms"]["value"], "treatment_bay": a["adult_main_bays"]["value"], "resus_bay": a["resus_bays"]["value"],
                      "fast_track": a["fast_track_spaces"]["value"], "peds_ed": a["peds_ed_spaces"]["value"], "results_waiting": 1}
            pool = ed["after"] - ed["direct"]
            k = pool / HOURS / sum(counts[s] * W0[s] for s in counts)
            for s, w in W0.items():
                o[f"space.{s}.fixed_cost_per_hour"] = A(
                    round(w * k, 1), "usd/hour", "assumed",
                    f"Calibrated, split assumed: overhead allocated to the Emergency cost centre = Worksheet B Part I column 26 minus Worksheet A column 7 ({ed['lines']}) = "
                    f"{int(pool)} usd/year ({HC}), spread over the modelled ED spaces {counts} for {HOURS} hours using relative weights per space type (this type {w}); scale factor {k:.2f}",
                    note="The annual total is measured; how it divides between space types is assumed, and the number of spaces is itself a rule, hence 'assumed'. Overhead includes "
                         "employee-benefit, administration, plant and housekeeping allocations. ED staff salaries are NOT included (staff are costed by wage).", **kw)

    def override_wages(self):
        w, o = self.E["bls_oews"], self.overrides
        roles = ["attending", "app", "rn", "charge_rn", "tech", "registration", "pharmacist", "imaging_tech", "transport", "evs"]
        if not w:
            why = self.src_unavailable("bls_oews")
            self.miss("BLS OEWS wages for the hospital's metropolitan area", why, "staff.*.wage_per_hour carried over from New Jersey statewide wages and tagged assumed")
            for role in roles:
                n = shared_node(self.shared, f"staff.{role}.wage_per_hour")
                o[f"staff.{role}.wage_per_hour"] = A(n["value"], "usd/hour", "assumed", f"BLS OEWS wages for this hospital's area were not available ({why}); New Jersey statewide value carried over")
            return
        geo, src = w["geography"], w["source"]
        names = {"metro": f"{geo.get('cbsa_title')} metropolitan statistical area (CBSA {geo.get('cbsa')}, BLS area {w['areas'].get('metro')})",
                 "state": f"{w['state']} statewide (BLS area {w['areas'].get('state')})"}
        tab = {(r["area"], r["soc"]): r for r in w["table"]}
        stat = {"hourly_mean": "hourly mean", "hourly_median": "hourly MEDIAN", "hourly_p75": "hourly 75th percentile"}
        why_role = {"attending": "Median, not mean: the occupation's wage distribution is bimodal in many areas (trainees coded in the same occupation). Base wage only; benefits through staff.shared.benefits_load.",
                    "app": "All specialties, not ED-specific.", "rn": "All settings, not ED-specific.",
                    "charge_rn": "There is no charge-nurse occupation code; the RN 75th percentile is a proxy for a senior nurse (a mapping assumption).",
                    "tech": "There is no ED-technician occupation code; hospitals fill the role with EMT-certified or nursing-assistant staff.",
                    "imaging_tech": "CT/MRI technologists (SOC 29-2035) earn more; not fetched.", "evs": "All industries."}
        for role in roles:
            rw = w["role_wages"].get(role) or {}
            if rw.get("value") is None:
                n = shared_node(self.shared, f"staff.{role}.wage_per_hour")
                self.miss(f"staff.{role}.wage_per_hour", rw.get("note", "no BLS estimate"), "New Jersey statewide value carried over, tagged assumed")
                o[f"staff.{role}.wage_per_hour"] = A(n["value"], "usd/hour", "assumed", f"BLS publishes no estimate for this occupation in {names.get('metro')} or {names.get('state')}; New Jersey statewide value carried over")
                continue
            comp = rw["components"]
            how = (f"SOC {comp[0]['soc']} {comp[0]['occupation']}, {stat[rw['statistic']]}" if len(comp) == 1 else
                   "unweighted mean of " + " and ".join(f"SOC {x['soc']} {x['occupation']} ({x['value']:.2f})" for x in comp) + f", {stat[rw['statistic']]}")
            note = why_role.get(role, "")
            if rw["statistic"] != rw["statistic_wanted"]:
                note += f" BLS does not publish the {stat[rw['statistic_wanted']]} for this area (top-coded or suppressed), so the {stat[rw['statistic']]} is used."
            if rw["area"] == "state":
                note += " Not published for the metropolitan area; statewide value used."
            other = "state" if rw["area"] == "metro" else "metro"
            alt = [tab.get((other, x["soc"]), {}).get(rw["statistic"]) for x in comp]
            if all(v is not None for v in alt) and alt:
                note += f" {names[other].split(' (')[0]}: {sum(alt) / len(alt):.2f}."
            o[f"staff.{role}.wage_per_hour"] = A(rw["value"], "usd/hour", "measured",
                                                 f"BLS Occupational Employment and Wage Statistics, May {rw['year']} estimates, {names[rw['area']]}, all industries "
                                                 f"(BLS public API series OEU{rw['area_code']}000000<SOC><datatype>); {how}", url=src["landing"], file=self.F("bls_oews"), note=note.strip())

    def override_staffing(self):
        S, o = self.shared["staff"]["shared"], self.overrides
        ref_arr = self.shared["patient"]["shared"]["arrivals_per_day"]["value"]
        k = self.arrivals_per_day / ref_arr
        n = (self.E["roster"] or {}).get("counts") or {}

        def levels(ref):
            mid = max(2, round(ref[2] * k))
            step = max(1, round((ref[3] - ref[2]) * k))
            return [max(1, mid + (i - 2) * step) for i in range(5)]

        pl, rl = levels(S["provider_levels"]["value"]), levels(S["rn_levels"]["value"])
        base = (f"{RULE}the calibrated RWJUH roster ({{ref}}) scaled by ED arrivals per day ({self.arrivals_per_day:.0f} here / {ref_arr} at RWJUH = x{k:.2f}), i.e. the same arrivals per "
                "person-shift as the model that reproduces RWJUH's published ED time and LWBS rate. Not this hospital's roster, which is not public")
        mix = S["provider_role_mix"]["value"]
        need_att = pl[2] * 3 * 7 * mix["attending"] / 4.0
        rn_note = ""
        if "rn_fte" in self.attrs:
            rn_note = f" Hospital-wide registered-nurse FTE (rn_fte) is {self.attrs['rn_fte']['value']}; the ED's share of it is not public."
        o["staff.shared.provider_levels"] = A(
            pl, "providers on shift", "assumed", base.format(ref="/".join(str(x) for x in S["provider_levels"]["value"])), index="level",
            note="FIRST GUESS for calibration against validation_median_ed_time_min and validation_lwbs_rate. Roster cross-check: the default level puts "
                 f"{pl[2]} providers on each of 3 shifts; at the model's provider mix ({mix}) and about 4 eight-hour clinical shifts per full-time physician per week that is roughly "
                 f"{need_att:.0f} full-time attending equivalents" + (f", against {n['em_physicians']} emergency physicians affiliated with the hospital (CMS, em_physicians)" if n else "") + ".")
        o["staff.shared.rn_levels"] = A(rl, "nurses on shift", "assumed", base.format(ref="/".join(str(x) for x in S["rn_levels"]["value"])), index="level",
                                        note="FIRST GUESS for calibration. ED nurse staffing is not in any public dataset." + rn_note)
        sup = {r: max(1, round(v * k)) for r, v in S["support_staff_per_shift"]["value"].items()}
        o["staff.shared.support_staff_per_shift"] = A(sup, "people/shift", "assumed", base.format(ref=str(S["support_staff_per_shift"]["value"])), index="staff_role")
        ag = [0] + [max(1, round(v * k)) for v in S["agency_nurses_per_shift"]["value"][1:]]
        o["staff.shared.agency_nurses_per_shift"] = A(ag, "nurses/shift", "assumed", base.format(ref=str(S["agency_nurses_per_shift"]["value"])), index="agency_contract option")

    def override_flu(self):
        f, o = self.E["fluview"], self.overrides
        if not f:
            self.miss("CDC ILINet flu-season parameters for the hospital's HHS region", self.src_unavailable("fluview"), "event.flu_wave parameters stay at the HHS Region 2 values in catalog/event.yaml")
            return
        h, n = f["region"], f["nat"]
        DS = (f"CDC ILINet weekly weighted percent of outpatient visits for influenza-like illness (wILI), HHS Region {f['hhs_region']} ({', '.join(f['hhs_region_states'].split())}), obtained through "
              f"the Delphi Epidata API mirror; {h['n_seasons']} seasons {h['seasons_used'][0]} to {h['seasons_used'][-1]} excluding 2019-20, 2020-21, 2021-22")
        kw = dict(url=f["source"]["url"], file=self.F("fluview"))
        o["event.flu_wave.duration_days"] = A(int(h["wave_duration_days_median"]), "days", "measured",
                                              f"{DS}; per season, number of weeks with wILI at or above the off-season baseline (mean of weeks 21-39) plus half of the peak excess, x7; median across seasons",
                                              range=h["wave_duration_days_range"], note=f"Width of the wave at half its height; range = shortest to longest season. National median {int(n['wave_duration_days_median'])} days.", **kw)
        o["event.flu_wave.respiratory_share_uplift"] = A(h["mean_wave_excess_share_median"], "absolute share", "measured",
                                                         f"{DS}; mean excess of wILI over the off-season baseline during the wave weeks, median across seasons, expressed as a share of visits",
                                                         range=h["mean_wave_excess_share_range"],
                                                         note="PROXY: ILINet measures influenza-like illness as a share of OUTPATIENT-provider visits in the region, not the respiratory share of this hospital's ED "
                                                              f"arrivals. Peak-week excess median {h['peak_excess_share_median']}; peak wILI is {h['peak_over_baseline_median']}x the off-season baseline.", **kw)
        o["event.flu_wave.frequency_per_year"] = A(1, "per year", "measured", f"{DS}; share of seasons with at least 4 weeks of wILI above baseline + 2 SD = {h['seasons_with_wave_share']}; modal peak MMWR week {h['peak_week_mode']}", **kw)

    # ---- layout inputs ----------------------------------------------------------------------
    def layout_inputs(self):
        a = self.attrs
        rule = "Count by a stated rule from annual ED visits, not a public figure (see catalog/hospitals/%s.yaml: %s)."
        pubn = lambda k: (f"The hospital publishes this count ({a[k]['value']}; citation in catalog/hospitals/{self.id}.yaml: {k}). " if a[k]["source"] == "literature" else "")  # noqa: E731
        tb = (f"The hospital publishes a total of {a['ed_treatment_spaces']['value']} ED treatment rooms; how they divide into zones is a stated rule "
              f"(catalog/hospitals/{self.id}.yaml: adult_main_bays)." if a["ed_treatment_spaces"]["source"] == "literature" else rule % (self.id, "adult_main_bays"))
        notes = {
            "treatment_bay": tb, "resus_bay": pubn("resus_bays") or rule % (self.id, "resus_bays"), "fast_track": rule % (self.id, "fast_track_spaces"),
            "peds_ed": rule % (self.id, "peds_ed_spaces"), "triage": rule % (self.id, "triage_rooms"), "ct": rule % (self.id, "ct_scanners_ed"), "xray": rule % (self.id, "xray_rooms_ed"),
            "ultrasound": rule % (self.id, "ultrasound_units"), "mri": "Count assumed (1). Not simulated.", "ambulance_bay": rule % (self.id, "ambulance_bay_slots"),
            "ward_unit": "Beds here are the modelled pool available to ED admissions (a stated rule: ward_pool_beds), not the hospital's bed count.",
            "icu_bed": "Part of the modelled pool (one seventh, a stated rule), not the hospital's ICU bed count" + (f" ({a['icu_beds']['value']} on the cost report)." if "icu_beds" in a else "."),
            "stepdown_bed": "Part of the modelled pool (one seventh, a stated rule); the hospital's step-down bed count is not public.",
            "operating_room": (f"Capacity = operating rooms in the CMS Provider of Services file ({self.or_rooms})." if self.or_rooms else "Capacity assumed (12): the Provider of Services file carries no count for this hospital.") + " Not simulated.",
            "recovery": "Capacity assumed (1.5 per operating room). Not simulated.",
            "waiting_room": "Capacity assumed (0.6 seats per main and fast-track space).", "results_waiting": "Capacity assumed. Drawn but not used by the simulator.",
            "_default": "Generic emergency-department support space; whether and where the hospital has it is not public."}
        srcs = [dict(title="Generated by twin/layout.py (parametric generator of catalog/hospitals/build_layout.py); every room position is inferred",
                     url="twin/layout.py", accessed=dt.date.today().isoformat(), used_for="all room positions and sizes"),
                dict(title=f"catalog/hospitals/{self.id}.yaml and twin/reports/{self.id}/DATA.md", url=f"catalog/hospitals/{self.id}.yaml", accessed=dt.date.today().isoformat(),
                     used_for="room counts: each is a public figure or a stated rule, with its citation")]
        return self.counts, notes, srcs
