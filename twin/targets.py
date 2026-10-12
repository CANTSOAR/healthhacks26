"""Calibration targets for a hospital id, collected from public data already in the catalog.

    python -m twin.targets --hospital rwjuh_nb        # print the target table

Sources read: `catalog/hospitals/<id>.yaml` (the hospital's own published figures: CMS Care Compare OP-18b
and OP-22, HCRIS cost report) and `catalog/validation_targets.yaml` (the hospital's own block if present,
CMS peer groups, national NHAMCS survey tables). Targets are never simulator inputs.

Each target:
    key        name of the simulated quantity it is compared with (see twin/harness.py::metrics_of)
    value      the published value (centre of the interval)
    lo, hi     acceptance interval. Hospital-specific targets: what the published figure can mean (rounding,
               sampling error, definition). National priors: a wide band, they describe other hospitals.
    tol        scale used by the fit: loss = weight * ((simulated - value) / tol)^2
    weight     0 = reported only, never fitted
    scope      "hospital" (this hospital's own published value)  |  "national" (survey prior, soft)
               |  "input" (the simulator is driven by this number; a check, not a test)
    accept     True = an ensemble member must fall inside [lo, hi]
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CATALOG = ROOT / "catalog"
ACU = ["esi1", "esi2", "esi3", "esi4", "esi5"]
# coefficient of variation of a discharged ED stay; lognormal, research/operations-parameter-ranges.yaml ed_stay_lognormal_cv
STAY_CV = 0.9
ATTENDING_SHARE = 0.12           # assumed: largest share of the ED salary line that could be employed attending physicians
STEADY_SD = 1.5                  # free beds a single ward pool must keep, in standard deviations of its demand (sqrt of the load)
PAID_TO_WORKED = (1.0, 1.15)     # assumed: paid hours / worked hours (leave, education); widens the salary interval


@dataclass
class Target:
    key: str
    label: str
    value: float
    lo: float
    hi: float
    tol: float
    weight: float
    scope: str
    unit: str
    source: str
    note: str = ""
    accept: bool = False
    dead: float = 0.0          # half-width of a flat zone around `value` in the fit (published value is itself an interval)

    def inside(self, x: float) -> bool:
        return x is not None and not math.isnan(x) and self.lo - 1e-12 <= x <= self.hi + 1e-12

    def verdict(self, x: float) -> str:
        if x is None or math.isnan(x):
            return "n/a"
        return "inside" if self.inside(x) else ("OUTSIDE (low)" if x < self.lo else "OUTSIDE (high)")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def hospital_attrs(hospital_id: str) -> tuple[dict, dict]:
    """(attributes, whole file) of catalog/hospitals/<id>.yaml."""
    f = CATALOG / "hospitals" / f"{hospital_id}.yaml"
    if not f.exists():
        raise FileNotFoundError(f"no hospital file {f}")
    d = _load(f)
    v = d.get("variants") or {}
    hv = v.get(hospital_id) or next(iter(v.values()))
    return (hv.get("attributes") or {}), d


def _num(a):
    if isinstance(a, dict):
        a = a.get("value")
    return float(a) if isinstance(a, (int, float)) and not isinstance(a, bool) else None


def _first(attrs: dict, *keys):
    for k in keys:
        if k in attrs and _num(attrs[k]) is not None:
            return k, attrs[k]
    return None, None


def _series(a) -> list[float]:
    """Numbers of a weekly series attribute, whatever its layout (list of numbers or list of dicts)."""
    v = a.get("value") if isinstance(a, dict) else a
    out = []
    if isinstance(v, dict):
        v = list(v.values())
    for x in v or []:
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            out.append(float(x))
        elif isinstance(x, dict):
            for kk in ("value", "occupancy", "visits", "ed_visits", "v"):
                if isinstance(x.get(kk), (int, float)):
                    out.append(float(x[kk]))
                    break
    return out


def _pool_beds(hospital_id: str, attrs: dict):
    """Beds of the modelled ward pool (the layout decides; `ward_pool_beds` in the hospital file as a fallback)."""
    try:
        from sim import load_scenario
        return int(load_scenario("normal_week", overrides={"hospital_id": hospital_id, "no_calibration": True}).P["ward_cap0"])
    except Exception:       # noqa: BLE001
        v = _num(attrs.get("ward_pool_beds"))
        return int(v) if v else None


def roster(hospital_id: str) -> dict:
    """Public roster / payroll counts if the hospital file carries them (used as priors, never as targets)."""
    attrs, _ = hospital_attrs(hospital_id)
    out = {}
    for k in ("em_physicians", "em_apps", "rn_fte", "ed_rn_fte", "ed_salaries_per_year", "fte_employees"):
        if _num(attrs.get(k)) is not None:
            out[k] = dict(value=_num(attrs[k]), source=attrs[k].get("source", "?"), citation=str(attrs[k].get("citation", ""))[:300])
    return out


def collect_targets(hospital_id: str) -> dict[str, Target]:
    attrs, _ = hospital_attrs(hospital_id)
    vt = (_load(CATALOG / "validation_targets.yaml").get("variants") or {})
    own = (vt.get(hospital_id) or {}).get("attributes") or {}
    T: dict[str, Target] = {}
    cite = lambda a: re.sub(r"\s+", " ", str((a or {}).get("citation", "")))[:260]   # noqa: E731

    # ---- median ED time, discharged patients (CMS OP-18b)
    k, a = _first(attrs, "validation_median_ed_time_min", "median_ed_time_discharged_min", "op18b_median_min")
    if a is None and _num(own.get("median_ed_time_discharged_min")) is not None:
        a = own["median_ed_time_discharged_min"]
    if a is not None:
        v = _num(a)
        m = re.search(r"sample\s+(\d+)", str(a.get("citation", "")))
        n = int(m.group(1)) if m else 300
        # standard error of a sample median of a lognormal: 1.2533 * sd / sqrt(n), sd = cv * mean, mean ~ median * sqrt(1 + cv^2)
        se = 1.2533 * STAY_CV * v * math.sqrt(1 + STAY_CV ** 2) / math.sqrt(n)
        half = max(10.0, 1.96 * se)
        T["los_dc_median"] = Target(
            "los_dc_median", "Median ED time, discharged patients", v, v - half, v + half, max(5.0, half / 3), 4.0, "hospital", "min",
            "CMS Care Compare OP-18b: " + cite(a),
            f"CMS computes the median from a sample of {n} visits{'' if m else ' (sample size not published in the file; 300 assumed)'}; "
            f"interval = +/- 1.96 standard errors of a sample median of a lognormal stay with cv {STAY_CV} ({half:.0f} min). "
            "Excludes admitted, transferred and psychiatric patients; the simulator's discharged patients are compared.", True)

    # ---- left without being seen (CMS OP-22, whole percent)
    k, a = _first(attrs, "validation_lwbs_rate", "lwbs_rate", "op22_lwbs_rate")
    if a is None and _num(own.get("lwbs_rate")) is not None:
        a = own["lwbs_rate"]
    if a is not None:
        v = _num(a)
        lo = max(0.0, v - 0.005)
        T["lwbs_rate"] = Target(
            "lwbs_rate", "Left without being seen, share of arrivals", v, lo, v + 0.005, 0.002, 4.0, "hospital", "fraction",
            "CMS Care Compare OP-22: " + cite(a),
            "Published as a whole-number percent, so the true value is anywhere in the interval. The fit is indifferent inside "
            "+/- 0.3 points of the published value and penalises anything further out.", True, 0.003)

    # ---- ED visits per day (drives the arrival rate: an input check)
    k, a = _first(attrs, "ed_visits_per_year_cms", "ed_visits_per_year")
    if a is not None:
        v = _num(a) / 365.0
        T["arrivals_per_day"] = Target(
            "arrivals_per_day", "ED arrivals per day", v, 0.96 * v, 1.04 * v, 0.02 * v, 0.0, "input", "patients/day",
            f"{k}: " + cite(a), "The arrival rate is a simulator input (patient.shared.arrivals_per_day), so this only checks the "
            "arrival process (hour/weekday/season profile over the simulated window).", False)

    # ---- inpatient occupancy -> occupancy of the modelled ward pool (HCRIS annual figure; HHS weekly series as a second opinion)
    pub = []
    for key, name in (("inpatient_occupancy", "HCRIS cost report, annual, beds available"),
                      ("inpatient_occupancy_hhs", "HHS weekly capacity reports, staffed beds")):
        v = _num(attrs.get(key))
        if v is not None:
            pub.append((key, name, v, 0.3 < v <= 0.98, attrs[key]))
    ok = [p for p in pub if p[3]]
    if ok:
        k, name, v, _, a = ok[0]
        lo, hi = min(p[2] for p in ok) - 0.03, min(0.97, max(p[2] for p in ok) + 0.03)
        # a single pool is only a steady state if some beds stay free: keep 1.5 standard deviations of bed demand (sqrt of the load)
        beds = _pool_beds(hospital_id, attrs)
        cap = None
        if beds:
            root = (-STEADY_SD + math.sqrt(STEADY_SD ** 2 + 4.0 * beds)) / 2.0
            cap = root * root / beds
        aim = min(v, cap) if cap else v
        capped = aim < v - 1e-9
        v_pub, v = v, max(lo, aim)
        said = "; ".join(f"{p[1]}: {p[2]:.3f}" + ("" if p[3] else " (NOT USABLE: above 100 % of the reported beds)")
                         + (f", weekly range {p[4]['range'][0]:.2f}-{p[4]['range'][1]:.2f}" if isinstance(p[4].get("range"), list) else "")
                         for p in pub)
        T["ward_occupancy"] = Target(
            "ward_occupancy", "Inpatient occupancy (modelled ward pool)", v, lo, hi, 0.01, 2.0, "hospital", "fraction",
            f"{k}: " + cite(a),
            f"Public figures: {said}. Both are averages over ALL inpatient beds of the hospital; the simulator has one pool of beds that ED "
            f"admissions compete for, and matching that pool's occupancy to the hospital-wide figure is an assumption. The fit aims at "
            f"{v_pub:.3f} ({name}); the acceptance interval spans the usable public figures +/- 3 points."
            + (f" CAPPED: the fit aims at {v:.3f}, not {v_pub:.3f}. A single pool of {beds} beds run at {v_pub:.3f} leaves fewer free beds than "
               f"{STEADY_SD} standard deviations of its own demand; in the simulator that is not a steady state (a 1-2 % seasonal rise in "
               "arrivals plus the literature boarding penalty make it fill for weeks, and LWBS doubles on held-out seeds - found in the "
               "first calibration run of RWJUH). The published figure is an average over a hospital several times larger, where the same "
               "occupancy leaves far more slack in absolute beds." if capped else ""), True)

    if "ward_occupancy" in T:
        T["ward_occupancy_drift"] = Target(
            "ward_occupancy_drift", "Ward occupancy drift (last 10 days minus first 10)", 0.0, -0.03, 0.03, 0.01, 2.0, "stationarity", "fraction",
            "model requirement, not a published figure",
            "A baseline must be a steady state: a hospital's published annual figures cannot come from a pool that is still filling. "
            "Near-full pools drift because boarding lengthens stays (literature penalty), which feeds back into occupancy.", True)

    # ---- ED salaries per day (HCRIS Worksheet A line 91 column 1)
    sal, src = None, ""
    if _num(attrs.get("ed_salaries_per_year")) is not None:
        sal, src = _num(attrs["ed_salaries_per_year"]), "ed_salaries_per_year: " + cite(attrs["ed_salaries_per_year"])
    elif "ed_direct_cost_per_year" in attrs:
        m = re.search(r"salaries.*?([0-9]{6,})", str(attrs["ed_direct_cost_per_year"].get("citation", "")))
        if m:
            sal, src = float(m.group(1)), "ed_direct_cost_per_year (salaries in the citation): " + cite(attrs["ed_direct_cost_per_year"])
    if sal:
        v = sal / 365.0
        lo, hi = v * (0.9 / PAID_TO_WORKED[1] - ATTENDING_SHARE), v * 1.1
        T["ed_salaries_per_day"] = Target(
            "ed_salaries_per_day", "ED salaries per day (wages, no benefits, no physicians)", 0.5 * (lo + hi), lo, hi,
            0.07 * v, 1.0, "hospital", "usd/day", src,
            f"Published: {v / 1e3:.1f} k$/day (HCRIS Worksheet A line 91 column 1 = salaries the hospital pays in the Emergency cost centre, "
            "/ 365). Compared with the simulator's wage bill WITHOUT benefits and WITHOUT attending / resident pay. Three things the report "
            f"does not say widen the interval: it counts paid hours, the simulator worked hours (paid/worked 1.0 to {PAID_TO_WORKED[1]} "
            f"allowed); employed attending physicians may or may not be on the line (up to {100 * ATTENDING_SHARE:.0f} % of the bill allowed); "
            "+/- 10 % for wage levels (the simulator uses BLS area wages). The fit aims at the middle of the interval. In the model this "
            "target mostly decides how many nurses are on the floor, which patient flow alone cannot identify.", True)

    # ---- national priors (NHAMCS), soft
    grp = str((attrs.get("nhamcs_peer_group") or {}).get("value") or "nhamcs_metro_teaching")
    nh = (vt.get(grp) or {}).get("attributes") or {}
    lab = (vt.get(grp) or {}).get("label", grp)
    g = lambda key: (nh.get(key) or {}).get("value")   # noqa: E731
    if g("wait_to_provider_median_min") is not None:
        v = float(g("wait_to_provider_median_min"))
        T["wait_median"] = Target("wait_median", "Median arrival-to-provider wait", v, v - 7, v + 13, 5.0, 0.5, "national", "min", lab,
                                  "Survey median over many hospitals; a prior on the shape, not this hospital's value.")
    xs = g("wait_to_provider_p90_min_by_acuity")
    if xs:
        for i, v in enumerate(xs):
            if i in (1, 2, 3):
                T[f"wait_p90_esi{i + 1}"] = Target(f"wait_p90_esi{i + 1}", f"90th percentile wait, ESI {i + 1}", float(v), 0.5 * v, 1.5 * v,
                                                   0.4 * v, 0.15, "national", "min", lab,
                                                   "Pools hospitals and seasons, so it also contains between-hospital spread.")
    xs = g("length_of_visit_discharged_median_min_by_acuity")
    if xs:
        for i, v in enumerate(xs):
            if i in (1, 2, 3):
                T[f"los_dc_median_esi{i + 1}"] = Target(f"los_dc_median_esi{i + 1}", f"Median ED time, discharged, ESI {i + 1}", float(v),
                                                        0.75 * v, 1.25 * v, 0.2 * v, 0.2, "national", "min", lab, "")
    xs = g("length_of_visit_discharged_p90_min_by_acuity")
    if xs:
        v = float(xs[2])
        T["los_dc_p90_esi3"] = Target("los_dc_p90_esi3", "90th percentile ED time, discharged, ESI 3", v, 0.75 * v, 1.25 * v, 0.2 * v, 0.1,
                                      "national", "min", lab, "")
    if g("boarding_mean_min") is not None:
        v = float(g("boarding_mean_min"))
        T["boarding_min_per_admission"] = Target(
            "boarding_min_per_admission", "Mean boarding time per admission", v, 0.25 * v, 2.5 * v, 0.6 * v, 0.2, "national", "min", lab,
            "Survey mean (decision to admit until leaving the ED). Very skewed: the survey median is "
            f"{g('boarding_median_min')} min.")
    if g("admission_rate") is not None:
        v = float(g("admission_rate"))
        T["admit_rate"] = Target("admit_rate", "Admission decisions / arrivals", v, v - 0.03, v + 0.03, 0.01, 0.0, "national", "fraction", lab,
                                 "Follows from the measured admission probabilities by acuity (inputs); a check. The hospital's own "
                                 "ED admission count is not published (HCRIS discharges cover all inpatients).")
    return T


def loss(targets: dict[str, Target], sim: dict) -> float:
    """Weighted squared distance of simulated values from the targets (weight 0 targets ignored)."""
    tot = 0.0
    for k, t in targets.items():
        if t.weight <= 0 or k not in sim or sim[k] is None or math.isnan(float(sim[k])):
            continue
        tot += t.weight * (max(0.0, abs(float(sim[k]) - t.value) - t.dead) / t.tol) ** 2
    return tot


def accepted(targets: dict[str, Target], sim: dict) -> bool:
    return all(t.inside(float(sim[k])) for k, t in targets.items() if t.accept and k in sim)


def as_dicts(targets: dict[str, Target]) -> dict:
    return {k: asdict(t) for k, t in targets.items()}


def fmt(t: Target, x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if t.unit == "fraction":
        return f"{100 * x:.2f} %"
    if t.unit == "usd/day":
        return f"{x / 1e3:.1f} k$"
    return f"{x:.0f}" if abs(x) >= 100 else f"{x:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hospital", default="rwjuh_nb")
    a = ap.parse_args()
    T = collect_targets(a.hospital)
    print(f"Calibration targets for {a.hospital} ({len(T)}):")
    for t in T.values():
        print(f"  [{t.scope:8s}] {t.label:52s} {fmt(t, t.value):>9s}  interval {fmt(t, t.lo)} .. {fmt(t, t.hi)}  weight {t.weight}"
              f"{'  ACCEPT' if t.accept else ''}")
    print("Roster priors:", roster(a.hospital) or "none in the hospital file")


if __name__ == "__main__":
    main()
