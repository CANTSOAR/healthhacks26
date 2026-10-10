"""CDC/NCHS NHAMCS Emergency Department public-use microdata -> small weighted extracts.

Source: https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/nhamcs/stata/ (Stata files),
documentation https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHAMCS/doc22-ed-508.pdf
Every estimate uses the patient visit weight PATWT. Records are visits, the sampled hospitals are anonymous.
MAIN years 2019 + 2021 + 2022 are pooled (2022 is the latest released file; 2020 is left out as a pandemic outlier).
The month profile additionally pools 2014-2018 because each hospital reports only a 4-week period, so one year is noisy.

Heavy step (about 300 MB of .dta): run on deepstack, then copy data/processed/nhamcs_* back.
  python data/fetch/nhamcs.py            (downloads into data/raw/nhamcs, writes data/processed/nhamcs_*)
"""
from __future__ import annotations

import calendar
import zipfile

import numpy as np
import pandas as pd

from _common import PROCESSED, RAW, download, write_json

BASE = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/nhamcs/stata/"
ZIPS = {2014: "ed2014-stata.zip", 2015: "ED2015-stata.zip", 2016: "ED2016-stata.zip", 2017: "ed2017-stata.zip",
        2018: "ED2018-stata.zip", 2019: "ED2019-stata.zip", 2021: "ed2021-stata.zip", 2022: "ed2022-stata.zip"}
MAIN_YEARS = [2019, 2021, 2022]
MONTH_YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022]
RAWDIR = RAW / "nhamcs"

LAB_VARS = ["ABG", "BAC", "BMP", "BNP", "BUNCREAT", "CARDENZ", "CBC", "CMP", "BLOODCX", "TRTCX", "URINECX", "WOUNDCX", "OTHCX",
            "DDIMER", "ELECTROL", "GLUCOSE", "LACTATE", "LFT", "PTTINR", "OTHERBLD", "TOXSCREN", "URINE"]
POC_VARS = ["HIVTEST", "FLUTEST", "PREGTEST", "COVIDTEST"]  # rapid / point-of-care style tests, reported separately
KEEP = ["VMONTH", "VDAYR", "ARRTIME", "WAITTIME", "LOV", "AGE", "ARREMS", "AMBTRANSFER", "PAYTYPER", "IMMEDR", "RFV13D", "INJURY",
        "ANYIMAGE", "XRAY", "CATSCAN", "MRI", "ULTRASND", "LWBS", "LBTC", "LEFTAMA", "DOA", "DIEDED", "TRANOTH", "TRANPSYC",
        "ADMITHOS", "OBSHOS", "OBSDIS", "ADMIT", "LOS", "BOARDED", "MSA", "EMEDRES", "REGION", "HOSPCODE", "PATWT", "RESINT",
        "ATTPHYS", "NURSEPR", "PHYSASST"] + LAB_VARS + POC_VARS

# Reason for Visit Classification (NCHS RVC, doc22-ed appendix II), 4-digit "broader category" RFV13D -> our condition_group.
# First matching rule wins; everything else (and blank) is other_medical. This mapping is OURS, not NCHS's.
CONDITION_RULES = [
    ("mental_health_substance", [(1100, 1199), (2300, 2349), (5818, 5829), (5910, 5916)],
     "psychological/mental symptoms 1100-1199; mental disorders 2300-2349; self-harm, suicide attempt, intentional overdose 5818-5829; adverse effect of drug abuse / alcohol 5910-5916"),
    ("chest_pain", [(1050, 1050), (1260, 1274)], "chest pain and related symptoms 1050; palpitations, heart pain, other heart symptoms 1260-1274"),
    ("respiratory", [(1400, 1499), (2600, 2649)], "respiratory symptoms 1400-1499 (cough, shortness of breath, throat); respiratory diseases 2600-2649"),
    ("abdominal_pain", [(1500, 1639), (2650, 2699)], "digestive symptoms 1500-1639 (abdominal pain 1545, nausea, vomiting, diarrhea); digestive diseases 2650-2699"),
    ("neuro", [(1200, 1259), (2350, 2399), (1030, 1030), (5840, 5842)],
     "nervous-system symptoms 1200-1259 (headache, dizziness, convulsions); nervous-system diseases 2350-2399; syncope 1030; unconscious / altered consciousness 5840-5842"),
    ("infection_fever", [(1005, 1012), (2001, 2099), (5935, 5935)], "chills, fever, temperature symptoms 1005-1012; infective and parasitic diseases 2001-2099; SIRS/sepsis 5935"),
    ("injury_trauma", [(5001, 5817), (5830, 5830)], "injury by type/location 5001-5799; late effects, motor vehicle accident, accident NOS, violence 5800-5817; rape 5830"),
    ("musculoskeletal", [(1900, 1999), (2900, 2949)], "musculoskeletal symptoms 1900-1999 (back, neck, limb pain); musculoskeletal diseases 2900-2949"),
]
CONDITIONS = ["chest_pain", "respiratory", "abdominal_pain", "injury_trauma", "neuro", "infection_fever",
              "mental_health_substance", "musculoskeletal", "other_medical"]


def load(year: int, cols: list[str] | None = None) -> pd.DataFrame:
    z = download(BASE + ZIPS[year], RAWDIR / f"ed{year}-stata.zip")
    d = RAWDIR / f"ed{year}"
    if not list(d.glob("*.dta")):
        d.mkdir(exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.lower().endswith(".dta"):
                    zf.extract(n, d)
    f = sorted(d.rglob("*.dta"))[0]
    df = pd.read_stata(f, convert_categoricals=False)
    df.columns = [c.upper() for c in df.columns]
    if cols:
        df = df[[c for c in cols if c in df.columns]].copy()
    df["YEAR_"] = year
    return df


def wshare(df: pd.DataFrame, key, cats) -> dict:
    s = df.groupby(key)["PATWT"].sum()
    tot = s.sum()
    return {str(c): round(float(s.get(c, 0.0) / tot), 5) for c in cats}


def wmean(x, w) -> float:
    return float(np.average(x, weights=w)) if len(x) else float("nan")


def wquant(x, w, qs) -> list[float]:
    x = np.asarray(x, float); w = np.asarray(w, float)
    if len(x) == 0:
        return [float("nan")] * len(qs)
    o = np.argsort(x); x, w = x[o], w[o]
    c = (np.cumsum(w) - 0.5 * w) / w.sum()
    return [float(np.interp(q, c, x)) for q in qs]


def condition_of(code: pd.Series) -> pd.Series:
    out = pd.Series("other_medical", index=code.index)
    done = pd.Series(False, index=code.index)
    for name, ranges, _ in CONDITION_RULES:
        m = pd.Series(False, index=code.index)
        for lo, hi in ranges:
            m |= code.between(lo, hi)
        m &= ~done
        out[m] = name
        done |= m
    return out


def prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for v in LAB_VARS + POC_VARS:
        if v not in df:
            df[v] = 0
    df["lab"] = (df[LAB_VARS] == 1).any(axis=1).astype(int)
    df["lab_or_poc"] = ((df[LAB_VARS + POC_VARS] == 1).any(axis=1)).astype(int)
    df["hour"] = pd.to_numeric(df["ARRTIME"], errors="coerce")
    df.loc[df["hour"] < 0, "hour"] = np.nan
    df["hour"] = (df["hour"] // 100)
    df["dow_mon0"] = (df["VDAYR"] - 2) % 7           # VDAYR 1=Sunday..7=Saturday
    df["condition"] = condition_of(df["RFV13D"])
    df["acuity"] = df["IMMEDR"].where(df["IMMEDR"].between(1, 5))
    df["admit"] = ((df["ADMITHOS"] == 1) | (df["OBSHOS"] == 1)).astype(int)
    df["left"] = ((df["LWBS"] == 1) | (df["LBTC"] == 1) | (df["LEFTAMA"] == 1)).astype(int)
    df["transfer_out"] = ((df["TRANOTH"] == 1) | (df["TRANPSYC"] == 1)).astype(int)
    df["mode"] = np.where(df["ARREMS"] == 1, np.where(df["AMBTRANSFER"] == 1, "transfer", "ambulance"),
                          np.where(df["ARREMS"] == 2, "walk_in", None))
    df["age_band"] = pd.cut(df["AGE"], [-1, 17, 44, 64, 200], labels=["age_0_17", "age_18_44", "age_45_64", "age_65_plus"]).astype(str)
    pay = {1: "commercial", 2: "medicare", 3: "medicaid", 4: "other", 5: "self_pay", 6: "self_pay", 7: "other"}
    df["payer"] = df["PAYTYPER"].map(pay)
    df["metro_teaching"] = ((df["MSA"] == 1) & (df.get("EMEDRES", 0) == 1))
    return df


def by_acuity(df: pd.DataFrame, subset: str) -> list[dict]:
    rows = []
    groups = [(str(a), df[df["acuity"] == a]) for a in range(1, 6)] + [("triaged_1_5", df[df["acuity"].notna()]), ("all_visits", df)]
    for name, g in groups:
        seen = g[(g["LWBS"] != 1) & (g["DOA"] != 1)]
        w = seen["PATWT"]
        r = {"subset": subset, "acuity": name, "n_unweighted": int(len(g)), "weighted_visits_per_year": round(float(g["PATWT"].sum() / len(MAIN_YEARS)))}
        for out, col in [("p_imaging", "ANYIMAGE"), ("p_xray", "XRAY"), ("p_ct", "CATSCAN"), ("p_mri", "MRI"), ("p_ultrasound", "ULTRASND"),
                         ("p_lab", "lab"), ("p_lab_or_rapid_test", "lab_or_poc"), ("p_admit", "admit"), ("p_transfer_out", "transfer_out")]:
            r[out] = round(wmean((seen[col] == 1).astype(float), w), 4) if len(seen) else None
        img = seen[seen["ANYIMAGE"] == 1]
        r["p_ct_given_imaging"] = round(wmean((img["CATSCAN"] == 1).astype(float), img["PATWT"]), 4) if len(img) else None
        r["n_imaging_unweighted"] = int(len(img))
        adm = seen[seen["ADMITHOS"] == 1]
        known = adm[adm["ADMIT"].between(1, 6)]
        r["p_icu_given_admit"] = round(wmean((known["ADMIT"] == 1).astype(float), known["PATWT"]), 4) if len(known) >= 30 else None
        r["p_stepdown_given_admit"] = round(wmean((known["ADMIT"] == 2).astype(float), known["PATWT"]), 4) if len(known) >= 30 else None
        r["p_lwbs"] = round(wmean((g["LWBS"] == 1).astype(float), g["PATWT"]), 4)
        r["p_left_any"] = round(wmean(g["left"].astype(float), g["PATWT"]), 4)
        r["p_ambulance"] = round(wmean((g.loc[g["ARREMS"].isin([1, 2]), "ARREMS"] == 1).astype(float), g.loc[g["ARREMS"].isin([1, 2]), "PATWT"]), 4)
        wt = g[g["WAITTIME"] >= 0]
        q = wquant(wt["WAITTIME"], wt["PATWT"], [.5, .75, .9])
        r.update(wait_n=int(len(wt)), wait_median=round(q[0], 1), wait_p75=round(q[1], 1), wait_p90=round(q[2], 1),
                 wait_mean=round(wmean(wt["WAITTIME"], wt["PATWT"]), 1) if len(wt) else None)
        for lab, sub in [("all", seen), ("discharged", seen[(seen["admit"] == 0) & (seen["transfer_out"] == 0) & (seen["left"] == 0) & (seen["OBSDIS"] != 1) & (seen["DIEDED"] != 1)]),
                         ("admitted", seen[seen["admit"] == 1])]:
            lv = sub[sub["LOV"] >= 0]
            q = wquant(lv["LOV"], lv["PATWT"], [.5, .75, .9])
            r.update({f"lov_{lab}_n": int(len(lv)), f"lov_{lab}_median": round(q[0], 1), f"lov_{lab}_p75": round(q[1], 1),
                      f"lov_{lab}_p90": round(q[2], 1), f"lov_{lab}_mean": round(wmean(lv["LOV"], lv["PATWT"]), 1) if len(lv) else None})
        bd = seen[(seen["admit"] == 1) & (seen["BOARDED"] >= 0)]
        q = wquant(bd["BOARDED"], bd["PATWT"], [.5, .9])
        r.update(boarded_n=int(len(bd)), boarded_median=round(q[0], 1), boarded_p90=round(q[1], 1),
                 boarded_mean=round(wmean(bd["BOARDED"], bd["PATWT"]), 1) if len(bd) else None)
        rows.append(r)
    return rows


def treatment_model(df: pd.DataFrame) -> dict:
    """Weighted least squares of in-department minutes after first provider contact (LOV - WAITTIME - boarding)
    on acuity dummies + test indicators + admission, to separate a 'no tests' base time per acuity from test-attributable time."""
    g = df[df["acuity"].notna() & (df["LOV"] >= 0) & (df["WAITTIME"] >= 0) & (df["left"] == 0) & (df["DOA"] != 1) & (df["DIEDED"] != 1)
           & (df["OBSDIS"] != 1) & (df["OBSHOS"] != 1)].copy()
    g["y"] = g["LOV"] - g["WAITTIME"] - np.where(g["BOARDED"] > 0, g["BOARDED"], 0)
    g = g[g["y"] >= 0]
    cap = wquant(g["y"], g["PATWT"], [.99])[0]
    g["y"] = g["y"].clip(upper=cap)
    names = [f"esi{a}" for a in range(1, 6)] + ["xray", "ct", "mri", "ultrasound", "lab", "admitted"]
    X = np.column_stack([(g["acuity"] == a).astype(float) for a in range(1, 6)] +
                        [(g[c] == 1).astype(float) for c in ["XRAY", "CATSCAN", "MRI", "ULTRASND", "lab", "admit"]])
    w = g["PATWT"].to_numpy(float)
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], g["y"].to_numpy(float) * sw, rcond=None)
    resid = g["y"].to_numpy(float) - X @ beta
    out = {"n_unweighted": int(len(g)), "winsorized_at_p99_min": round(cap, 1), "coefficients_min": {n: round(float(b), 1) for n, b in zip(names, beta)},
           "r2_weighted": round(float(1 - np.average(resid ** 2, weights=w) / np.average((g["y"] - np.average(g["y"], weights=w)) ** 2, weights=w)), 3),
           "outcome": "LOV - WAITTIME - BOARDED(if >0), minutes; visits with a valid 1-5 triage level, excluding left-before-completion, DOA, died in ED, observation-unit stays",
           "by_acuity": {}}
    for a in range(1, 6):
        s = g[g["acuity"] == a]
        nt = s[(s["ANYIMAGE"] != 1) & (s["lab"] != 1) & (s["admit"] == 0)]
        q = wquant(s["y"], s["PATWT"], [.5])
        m = wmean(s["y"], s["PATWT"])
        sd = float(np.sqrt(np.average((s["y"] - m) ** 2, weights=s["PATWT"])))
        out["by_acuity"][f"esi{a}"] = {
            "n": int(len(s)), "mean_after_provider_min": round(m, 1), "median_after_provider_min": round(q[0], 1), "cv": round(sd / m, 2),
            "p_admit_in_model_sample": round(wmean(s["admit"].astype(float), s["PATWT"]), 4),
            "no_test_no_admit_n": int(len(nt)),
            "no_test_no_admit_mean_min": round(wmean(nt["y"], nt["PATWT"]), 1) if len(nt) >= 30 else None,
            "no_test_no_admit_median_min": round(wquant(nt["y"], nt["PATWT"], [.5])[0], 1) if len(nt) >= 30 else None}
    return out


def mixes(df: pd.DataFrame) -> dict:
    tri = df[df["acuity"].notna()]
    imm = df.groupby("IMMEDR")["PATWT"].sum(); imm = imm / imm.sum()
    known_mode = df[df["mode"].notna()]
    amb = tri[tri["ARREMS"].isin([1, 2])]
    return {
        "n_unweighted": int(len(df)), "n_hospitals_year_pairs": int(df.groupby("YEAR_")["HOSPCODE"].nunique().sum()),
        "weighted_visits_per_year": round(float(df["PATWT"].sum() / len(MAIN_YEARS))),
        "triage_item_raw_share": {str(int(k)): round(float(v), 4) for k, v in imm.items()},
        "triage_share_with_level_1_to_5": round(float(tri["PATWT"].sum() / df["PATWT"].sum()), 4),
        "acuity_mix_among_triaged": [wshare(tri, "acuity", range(1, 6))[str(a)] for a in range(1, 6)],
        "acuity_n_unweighted": [int((tri["acuity"] == a).sum()) for a in range(1, 6)],
        "condition_mix": wshare(df, "condition", CONDITIONS),
        "condition_n_unweighted": {c: int((df["condition"] == c).sum()) for c in CONDITIONS},
        "arrival_mode_mix": wshare(known_mode, "mode", ["walk_in", "ambulance", "transfer"]),
        "arrival_mode_unknown_share": round(float(1 - known_mode["PATWT"].sum() / df["PATWT"].sum()), 4),
        "ambulance_share_by_acuity": [round(wmean((amb.loc[amb["acuity"] == a, "ARREMS"] == 1).astype(float), amb.loc[amb["acuity"] == a, "PATWT"]), 4) for a in range(1, 6)],
        "age_band_mix": wshare(df, "age_band", ["age_0_17", "age_18_44", "age_45_64", "age_65_plus"]),
        "payer_mix": wshare(df[df["payer"].notna()], "payer", ["medicare", "medicaid", "commercial", "self_pay", "other"]),
        "payer_unknown_share": round(float(1 - df.loc[df["payer"].notna(), "PATWT"].sum() / df["PATWT"].sum()), 4),
        "p_lwbs": round(wmean((df["LWBS"] == 1).astype(float), df["PATWT"]), 4),
        "p_left_before_complete_or_ama": round(wmean(((df["LBTC"] == 1) | (df["LEFTAMA"] == 1)).astype(float), df["PATWT"]), 4),
        "p_admit_all_visits": round(wmean(df["admit"].astype(float), df["PATWT"]), 4),
        "provider_seen_share": {k: round(wmean((df[v] == 1).astype(float), df["PATWT"]), 4) for k, v in
                                [("attending", "ATTPHYS"), ("resident_intern", "RESINT"), ("nurse_practitioner", "NURSEPR"), ("physician_assistant", "PHYSASST")]},
    }


def main() -> None:
    main_df = prep(pd.concat([load(y, KEEP) for y in MAIN_YEARS], ignore_index=True))
    subsets = {"all_hospitals": main_df, "metro_teaching": main_df[main_df["metro_teaching"]]}
    src = {"dataset": "CDC/NCHS National Hospital Ambulatory Medical Care Survey, Emergency Department public-use files",
           "years_pooled": MAIN_YEARS, "url": BASE, "weights": "PATWT (patient visit weight)",
           "subsets": {"all_hospitals": "every sampled visit", "metro_teaching": "MSA==1 (metropolitan) and EMEDRES==1 (hospital has an emergency medicine residency)"},
           "records_per_year": {str(y): int((main_df["YEAR_"] == y).sum()) for y in MAIN_YEARS}}

    # ---- arrival profiles
    prof = {"source": src}
    for name, d in subsets.items():
        h = d[d["hour"].notna()].groupby("hour")["PATWT"].sum().reindex(range(24), fill_value=0)
        dw = d.groupby("dow_mon0")["PATWT"].sum().reindex(range(7), fill_value=0)
        prof[name] = {"arrival_hour_profile": [round(float(x), 4) for x in h / h.mean()],
                      "hour_n_unweighted": int(d["hour"].notna().sum()),
                      "hour_missing_share": round(float(d.loc[d["hour"].isna(), "PATWT"].sum() / d["PATWT"].sum()), 4),
                      "arrival_dow_profile_mon0": [round(float(x), 4) for x in dw / dw.mean()],
                      "dow_n_unweighted": [int((d["dow_mon0"] == i).sum()) for i in range(7)]}
    prof["by_year_all_hospitals"] = {}
    for y in MAIN_YEARS:
        d = main_df[main_df["YEAR_"] == y]
        h = d[d["hour"].notna()].groupby("hour")["PATWT"].sum().reindex(range(24), fill_value=0)
        dw = d.groupby("dow_mon0")["PATWT"].sum().reindex(range(7), fill_value=0)
        prof["by_year_all_hospitals"][str(y)] = {"arrival_hour_profile": [round(float(x), 4) for x in h / h.mean()],
                                                 "arrival_dow_profile_mon0": [round(float(x), 4) for x in dw / dw.mean()]}
    # month profile: per-day rate, pooled over more years
    mrows = []
    for y in MONTH_YEARS:
        d = main_df[main_df["YEAR_"] == y] if y in MAIN_YEARS else load(y, ["VMONTH", "PATWT"])
        s = d.groupby("VMONTH")["PATWT"].sum().reindex(range(1, 13), fill_value=0)
        n = d.groupby("VMONTH")["PATWT"].size().reindex(range(1, 13), fill_value=0)
        for m in range(1, 13):
            mrows.append({"year": y, "month": m, "weighted_visits": float(s[m]), "n_unweighted": int(n[m]),
                          "per_day": float(s[m]) / calendar.monthrange(y, m)[1]})
    md = pd.DataFrame(mrows)
    md["rel"] = md["per_day"] / md.groupby("year")["per_day"].transform("mean")
    pooled = md.groupby("month")["rel"].mean()
    prof["month"] = {"years_pooled": MONTH_YEARS,
                     "method": "weighted visits per calendar day by month, divided by that year's mean; then the unweighted mean across years, renormalised to mean 1",
                     "arrival_month_profile_jan0": [round(float(x), 4) for x in pooled / pooled.mean()],
                     "between_year_sd": [round(float(x), 4) for x in md.groupby("month")["rel"].std()],
                     "main_years_only_jan0": [round(float(x), 4) for x in (lambda p: p / p.mean())(md[md["year"].isin(MAIN_YEARS)].groupby("month")["rel"].mean())]}
    write_json(prof, PROCESSED / "nhamcs_ed_arrival_profiles.json")
    md.round(4).to_csv(PROCESSED / "nhamcs_ed_month_by_year.csv", index=False)

    # ---- mixes
    mx = {"source": src, "condition_mapping": {n: t for n, _, t in CONDITION_RULES} | {"other_medical": "all other RFV codes and blank"},
          "condition_mapping_variable": "RFV13D (first-listed reason for visit, NCHS Reason for Visit Classification, 4-digit broader category)",
          "payer_mapping": "PAYTYPER 1 private->commercial, 2->medicare, 3 Medicaid/CHIP->medicaid, 5 self-pay + 6 no charge/charity->self_pay, 4 workers comp + 7 other->other; unknown/blank excluded",
          "arrival_mode_mapping": "ARREMS==1 and AMBTRANSFER!=1 -> ambulance; ARREMS==1 and AMBTRANSFER==1 (transferred from another hospital/urgent care) -> transfer; ARREMS==2 -> walk_in; unknown excluded"}
    for name, d in subsets.items():
        mx[name] = mixes(d)
    mx["by_year_all_hospitals"] = {str(y): {k: v for k, v in mixes(main_df[main_df["YEAR_"] == y]).items()
                                            if k in ("acuity_mix_among_triaged", "triage_share_with_level_1_to_5", "p_lwbs", "p_admit_all_visits", "weighted_visits_per_year")}
                                   for y in MAIN_YEARS}
    write_json(mx, PROCESSED / "nhamcs_ed_mix.json")

    # ---- by acuity
    rows = []
    for name, d in subsets.items():
        rows += by_acuity(d, name)
    pd.DataFrame(rows).to_csv(PROCESSED / "nhamcs_ed_by_acuity.csv", index=False)

    # ---- condition x acuity (row-normalised within acuity), all hospitals
    tri = main_df[main_df["acuity"].notna()]
    ca = (tri.groupby(["acuity", "condition"])["PATWT"].sum().unstack(fill_value=0).reindex(columns=CONDITIONS, fill_value=0))
    ca = ca.div(ca.sum(axis=1), axis=0).round(4)
    ca.index = [f"esi{int(a)}" for a in ca.index]
    ca.to_csv(PROCESSED / "nhamcs_ed_condition_by_acuity.csv", index_label="acuity")
    # ---- p_admit and tests by condition
    seen = main_df[(main_df["LWBS"] != 1)]
    cond = seen.groupby("condition").apply(lambda g: pd.Series({
        "n_unweighted": len(g), "p_admit": wmean(g["admit"].astype(float), g["PATWT"]), "p_imaging": wmean((g["ANYIMAGE"] == 1).astype(float), g["PATWT"]),
        "p_ct": wmean((g["CATSCAN"] == 1).astype(float), g["PATWT"]), "p_lab": wmean(g["lab"].astype(float), g["PATWT"]),
        "p_ambulance": wmean((g.loc[g["ARREMS"].isin([1, 2]), "ARREMS"] == 1).astype(float), g.loc[g["ARREMS"].isin([1, 2]), "PATWT"]),
        "lov_median": wquant(g.loc[g["LOV"] >= 0, "LOV"], g.loc[g["LOV"] >= 0, "PATWT"], [.5])[0]})).reindex(CONDITIONS).round(4)
    cond.to_csv(PROCESSED / "nhamcs_ed_by_condition.csv", index_label="condition_group")

    # ---- treatment-time model and inpatient LOS of ED admissions
    tm = {"source": src}
    for name, d in subsets.items():
        tm[name] = treatment_model(d)
    adm = main_df[(main_df["ADMITHOS"] == 1) & (main_df["LOS"] >= 1)]
    q = wquant(adm["LOS"], adm["PATWT"], [.25, .5, .75, .9])
    m = wmean(adm["LOS"].clip(upper=60), adm["PATWT"])
    sd = float(np.sqrt(np.average((adm["LOS"].clip(upper=60) - m) ** 2, weights=adm["PATWT"])))
    tm["inpatient_los_of_ed_admissions_days"] = {"variable": "LOS (if admitted, length of stay in hospital in days), ADMITHOS==1, LOS>=1, capped at 60 for the mean",
                                                 "n_unweighted": int(len(adm)), "known_share_of_admissions": round(float(adm["PATWT"].sum() / main_df.loc[main_df["ADMITHOS"] == 1, "PATWT"].sum()), 3),
                                                 "mean": round(m, 2), "cv": round(sd / m, 2), "p25": q[0], "median": q[1], "p75": q[2], "p90": q[3]}
    write_json(tm, PROCESSED / "nhamcs_ed_treatment_time_model.json")
    print(open(PROCESSED / "nhamcs_ed_mix.json").read()[:6000])
    print(pd.DataFrame(rows).T.to_string())
    print(tm)
    print(prof["all_hospitals"], prof["month"])
    print(cond.to_string()); print(ca.to_string())


if __name__ == "__main__":
    main()
