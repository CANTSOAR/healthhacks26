"""HHS 'COVID-19 Reported Patient Impact and Hospital Capacity by Facility' (healthdata.gov anag-cw7u).

Weekly, facility-level, keyed by CMS number: emergency department visits (7-day sum), inpatient beds and beds used,
staffed adult ICU beds and occupancy. Mandatory reporting ended on 2024-04-30, so the series stops in late April 2024;
the most recent 52 complete weeks are summarised and the vintage is stated wherever the numbers are used.
Suppressed cells (-999999, counts of 1-3) and weeks without a value are dropped, never imputed.
"""
from __future__ import annotations

import hashlib
import json
import statistics

from ._common import RAW, SourceUnavailable, http_get, norm_ccn, now, out_dir, write_json

NAME = "hhs_capacity"
API = "https://healthdata.gov/resource/anag-cw7u.json"
LANDING = "https://healthdata.gov/Hospital/COVID-19-Reported-Patient-Impact-and-Hospital-Capa/anag-cw7u"
FIELDS = {
    "previous_day_total_ed_visits_7_day_sum": "ed_visits",
    "inpatient_beds_7_day_avg": "inpatient_beds",
    "inpatient_beds_used_7_day_avg": "inpatient_beds_used",
    "all_adult_hospital_inpatient_beds_7_day_avg": "adult_inpatient_beds",
    "all_adult_hospital_inpatient_bed_occupied_7_day_avg": "adult_inpatient_beds_used",
    "total_staffed_adult_icu_beds_7_day_avg": "adult_icu_beds",
    "staffed_adult_icu_bed_occupancy_7_day_avg": "adult_icu_beds_used",
    "total_icu_beds_7_day_avg": "icu_beds",
    "icu_beds_used_7_day_avg": "icu_beds_used",
    "previous_day_admission_adult_covid_confirmed_7_day_sum": "adult_covid_admissions",
    "previous_day_admission_influenza_confirmed_7_day_sum": "influenza_admissions",
    "previous_day_covid_ed_visits_7_day_sum": "covid_ed_visits",
}
WEEKS = 52


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x <= -999 else x


def _stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    s = sorted(xs)
    q = lambda p: s[min(len(s) - 1, int(round(p * (len(s) - 1))))]  # noqa: E731
    return {"n_weeks": len(s), "mean": round(statistics.fmean(s), 2), "median": round(statistics.median(s), 2), "min": s[0], "max": s[-1],
            "p10": q(.10), "p90": q(.90), "cv": round(statistics.pstdev(s) / statistics.fmean(s), 4) if statistics.fmean(s) else None}


def fetch(ccn, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    raw = RAW / "hhs_capacity" / f"{ccn}.json"
    url = f"{API}?hospital_pk={ccn}&$order=collection_week&$limit=5000"
    if raw.exists() and not force:
        body = raw.read_bytes()
        fetched = json.loads((raw.with_suffix(".meta.json")).read_text())["fetched_utc"]
    else:
        body = http_get(url, timeout=120)
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(body)
        fetched = now()
        write_json({"url": url, "fetched_utc": fetched}, raw.with_suffix(".meta.json"))
    rows = json.loads(body)
    if not rows:
        raise SourceUnavailable(f"healthdata.gov anag-cw7u has no rows for hospital_pk {ccn}")
    weekly = []
    for r in rows:
        w = {"week": r["collection_week"][:10]}
        for src, dst in FIELDS.items():
            w[dst] = _num(r.get(src))
        weekly.append(w)
    last = weekly[-WEEKS:]
    ident = {k: rows[-1].get(k) for k in ["hospital_pk", "ccn", "hospital_name", "address", "city", "state", "zip", "hospital_subtype", "fips_code"]}

    # ED visits were an optional field and some hospitals stopped reporting them before the series ended, so the ED
    # window is the most recent 52 weeks that HAVE a value (stated in the summary); weeks with an implausible value
    # (outside 0.5-1.5 x the window median - partial weeks) are excluded and listed
    ed_weeks = [w for w in weekly if w["ed_visits"] is not None][-WEEKS:]
    n_missing_in_capacity_window = sum(1 for w in last if w["ed_visits"] is None)
    med = statistics.median([w["ed_visits"] for w in ed_weeks] or [0])
    used, dropped = [], []
    for w in ed_weeks:
        v = w["ed_visits"]
        if med and not (0.5 * med <= v <= 1.5 * med):
            dropped.append({"week": w["week"], "reason": "outside 0.5-1.5 x the window median", "value": v})
        else:
            used.append(w)
    ed = _stats([w["ed_visits"] for w in used])
    month = None
    if ed and ed["n_weeks"] >= 40:
        # a collection week starts on its date; assign it to the month of its 4th day
        import datetime as dt
        by = {}
        for w in used:
            m = (dt.date.fromisoformat(w["week"]) + dt.timedelta(days=3)).month
            by.setdefault(m, []).append(w["ed_visits"])
        if len(by) == 12:
            means = [statistics.fmean(by[m]) for m in range(1, 13)]
            mm = statistics.fmean(means)
            month = {"profile_jan0": [round(x / mm, 3) for x in means], "weeks_per_month": [len(by[m]) for m in range(1, 13)]}

    def occ(num, den):
        xs = [w[num] / w[den] for w in last if w[num] is not None and w[den]]
        return _stats([round(x, 4) for x in xs])

    summary = {"window": {"first_week": last[0]["week"], "last_week": last[-1]["week"], "weeks": len(last)},
               "ed_visits_window": ({"first_week": ed_weeks[0]["week"], "last_week": ed_weeks[-1]["week"], "weeks_with_value": len(ed_weeks),
                                     "weeks_missing_in_last_52_on_file": n_missing_in_capacity_window} if ed_weeks else None),
               "ed_visits_per_week": ed, "ed_visits_weeks_excluded": dropped,
               "ed_visits_per_day_mean": round(ed["mean"] / 7, 1) if ed else None,
               "ed_visits_annualised": int(round(ed["mean"] * 365.25 / 7)) if ed else None,
               "ed_visits_month_profile": month,
               "inpatient_beds": _stats([w["inpatient_beds"] for w in last]), "inpatient_beds_used": _stats([w["inpatient_beds_used"] for w in last]),
               "inpatient_occupancy": occ("inpatient_beds_used", "inpatient_beds"),
               "adult_inpatient_beds": _stats([w["adult_inpatient_beds"] for w in last]),
               "adult_inpatient_occupancy": occ("adult_inpatient_beds_used", "adult_inpatient_beds"),
               "adult_icu_beds": _stats([w["adult_icu_beds"] for w in last]), "adult_icu_occupancy": occ("adult_icu_beds_used", "adult_icu_beds"),
               "icu_beds": _stats([w["icu_beds"] for w in last]), "icu_occupancy": occ("icu_beds_used", "icu_beds"),
               "influenza_admissions_per_week": _stats([w["influenza_admissions"] for w in last]),
               "adult_covid_admissions_per_week": _stats([w["adult_covid_admissions"] for w in last])}
    out = {"source": {"dataset": "HHS COVID-19 Reported Patient Impact and Hospital Capacity by Facility (weekly)", "dataset_id": "anag-cw7u",
                      "release": f"series ends {weekly[-1]['week']} (hospital reporting to HHS stopped being mandatory after 2024-04-30); {len(weekly)} weeks on file from {weekly[0]['week']}",
                      "url": url, "landing": LANDING, "raw_file": f"data/raw/hhs_capacity/{ccn}.json", "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(), "fetched_utc": fetched,
                      "filter": f"hospital_pk == '{ccn}', ordered by collection_week; capacity summary over the last {WEEKS} weeks on file, ED-visit summary over the last {WEEKS} weeks that have a value; -999999 (suppressed) treated as missing",
                      "note": "The dataset has no all-cause admissions field (only COVID-19 and influenza admissions). Occupancy = beds used / beds, both 7-day averages. "
                              "'inpatient_beds' includes all staffed inpatient beds (adult and pediatric); definitions follow the HHS reporting guidance and differ "
                              "from the cost report's 'beds available'."},
           "ccn": ccn, "facility_in_file": ident, "fields": FIELDS, "summary": summary, "weekly_last_156": weekly[-156:]}
    write_json(out, out_dir(ccn) / f"{NAME}.json")
    return out
