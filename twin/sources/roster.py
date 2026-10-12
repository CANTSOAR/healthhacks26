"""Clinician roster of a hospital from public CMS files - "every Medicare-enrolled clinician accounted for".

  1. Doctors and Clinicians 'Facility Affiliation Data' (Provider Data Catalog 27ea-46a8): clinician NPI <-> facility CMS number.
  2. Doctors and Clinicians 'National Downloadable File' (mj5m-pzi6): primary / secondary specialty, credential, graduation year.
  3. Medicare Physician & Other Practitioners - by Provider and Service (calendar 2024): emergency-department evaluation and
     management services (HCPCS 99281-99285, critical care 99291, place of service = facility) billed under each NPI. This is
     what identifies emergency-medicine nurse practitioners and physician assistants, whose CMS specialty is just 'NURSE
     PRACTITIONER' / 'PHYSICIAN ASSISTANT'.
  4. NPPES monthly dissemination file: every taxonomy code of each NPI (decoded with the NUCC code list when reachable).

Tracked output (roster.json): one row per clinician with NPI, specialty, credential, graduation year - NO NAMES. Names stay
in the gitignored raw files.

What this does NOT cover: residents and fellows (not Medicare-enrolled as billing clinicians - use the cost report's intern
and resident FTE), nurses and other employed staff (use the Provider of Services / cost report FTE counts), clinicians who
are not enrolled in Medicare or did not bill enough Medicare services at the hospital to be affiliated by CMS, and how
many hours anyone works in this hospital's emergency department (a clinician can be affiliated with several hospitals).
"""
from __future__ import annotations

import re
import zipfile

import pandas as pd

from ._common import RAW, SourceUnavailable, download, http_get, norm_ccn, out_dir, pdc_dataset, write_json

NAME = "roster"
MUP_YEAR = 2024
MUP_URL = "https://data.cms.gov/sites/default/files/2026-05/b5ebab5a-f490-418a-9bce-4b9f31419356/PHY_R26_P05_V10_D24_Prov_Svc.csv"
MUP_LANDING = "https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider-and-service"
NPPES_PAGE = "https://download.cms.gov/nppes/NPI_Files.html"
NUCC_URL = "https://www.nucc.org/images/stories/CSV/nucc_taxonomy_251.csv"
ED_EM_CODES = ["99281", "99282", "99283", "99284", "99285", "99291"]
EM_APP_MIN_SERVICES = 11
APP_SPECIALTIES = ["NURSE PRACTITIONER", "PHYSICIAN ASSISTANT"]
NON_PHYSICIAN = set(APP_SPECIALTIES) | {
    "CERTIFIED REGISTERED NURSE ANESTHETIST (CRNA)", "CERTIFIED NURSE MIDWIFE (CNM)", "CERTIFIED CLINICAL NURSE SPECIALIST (CNS)",
    "ANESTHESIOLOGY ASSISTANT", "PHYSICAL THERAPY", "OCCUPATIONAL THERAPY", "SPEECH LANGUAGE PATHOLOGIST", "QUALIFIED SPEECH LANGUAGE PATHOLOGIST",
    "AUDIOLOGIST", "QUALIFIED AUDIOLOGIST", "CLINICAL PSYCHOLOGIST", "CLINICAL SOCIAL WORKER", "REGISTERED DIETITIAN OR NUTRITION PROFESSIONAL",
    "CHIROPRACTIC", "OPTOMETRY", "MARRIAGE AND FAMILY THERAPIST", "MENTAL HEALTH COUNSELOR", "PHYSICAL THERAPIST IN PRIVATE PRACTICE",
    "OCCUPATIONAL THERAPIST IN PRIVATE PRACTICE", "DENTIST", "ORAL SURGERY", "MAXILLOFACIAL SURGERY", "PODIATRY"}
POOLS = {"hospitalists": ["HOSPITALIST"], "radiologists": ["DIAGNOSTIC RADIOLOGY", "INTERVENTIONAL RADIOLOGY"],
         "critical_care_physicians": ["CRITICAL CARE (INTENSIVISTS)"], "anesthesiologists": ["ANESTHESIOLOGY"],
         "internal_medicine_physicians": ["INTERNAL MEDICINE"], "general_surgeons": ["GENERAL SURGERY"],
         "cardiologists": ["CARDIOVASCULAR DISEASE (CARDIOLOGY)", "INTERVENTIONAL CARDIOLOGY"], "neurologists": ["NEUROLOGY"],
         "psychiatrists": ["PSYCHIATRY"], "orthopedic_surgeons": ["ORTHOPEDIC SURGERY"], "crnas": ["CERTIFIED REGISTERED NURSE ANESTHETIST (CRNA)"]}


def _mup_ed(force: bool):
    """National table NPI -> ED E/M services (cached after the first pass over the 3 GB file)."""
    d = RAW / "mup"
    raw = d / MUP_URL.rsplit("/", 1)[1]
    rec = download(MUP_URL, raw, force=force)
    cache = d / f"ed_em_by_npi_{MUP_YEAR}.csv"
    if not cache.exists() or force:
        parts = []
        for ch in pd.read_csv(raw, dtype=str, chunksize=1_000_000, encoding="latin-1",
                              usecols=["Rndrng_NPI", "Rndrng_Prvdr_Type", "HCPCS_Cd", "Place_Of_Srvc", "Tot_Benes", "Tot_Srvcs"]):
            parts.append(ch[ch["HCPCS_Cd"].isin(ED_EM_CODES) & (ch["Place_Of_Srvc"] == "F")])
        m = pd.concat(parts)
        m["Tot_Srvcs"] = pd.to_numeric(m["Tot_Srvcs"], errors="coerce")
        # 99291 is critical care in any facility setting; it counts as ED work only next to ED visit codes
        ed = m[m["HCPCS_Cd"] != "99291"].groupby("Rndrng_NPI")["Tot_Srvcs"].sum().rename("ed_visit_services")
        cc = m[m["HCPCS_Cd"] == "99291"].groupby("Rndrng_NPI")["Tot_Srvcs"].sum().rename("critical_care_services")
        t = pd.concat([ed, cc], axis=1).fillna(0).reset_index().rename(columns={"Rndrng_NPI": "npi", "index": "npi"})
        t = t.merge(m.drop_duplicates("Rndrng_NPI")[["Rndrng_NPI", "Rndrng_Prvdr_Type"]].rename(columns={"Rndrng_NPI": "npi", "Rndrng_Prvdr_Type": "mup_provider_type"}), on="npi", how="left")
        t.to_csv(cache, index=False)
    src = {"dataset": f"CMS Medicare Physician & Other Practitioners - by Provider and Service, calendar year {MUP_YEAR}", "dataset_id": raw.name,
           "release": f"data year {MUP_YEAR} (file dated 2026-05)", "url": MUP_URL, "landing": MUP_LANDING, "raw_file": f"data/raw/mup/{raw.name}",
           "bytes": rec["bytes"], "sha256": rec["sha256"], "fetched_utc": rec["fetched_utc"],
           "filter": f"HCPCS_Cd in {ED_EM_CODES} and Place_Of_Srvc == 'F', summed over codes per Rndrng_NPI; then NPI in the hospital's roster",
           "note": "Original Medicare (fee-for-service) Part B only; rows with 10 or fewer beneficiaries are suppressed by CMS."}
    return pd.read_csv(cache, dtype={"npi": str}), src


def _nppes(force: bool):
    """National table NPI -> taxonomy codes (cached after the first pass over the ~10 GB file)."""
    d = RAW / "nppes"
    d.mkdir(parents=True, exist_ok=True)
    have = sorted(p for p in d.glob("NPPES_Data_Dissemination_*.zip") if "Weekly" not in p.name)
    if have and not force:
        z = have[-1]
        url = "https://download.cms.gov/nppes/" + z.name
    else:
        page = http_get(NPPES_PAGE, timeout=60).decode("utf-8", "replace")
        names = [n for n in re.findall(r"NPPES_Data_Dissemination_[A-Za-z]+_\d{4}(?:_V2)?\.zip", page)]
        if not names:
            raise SourceUnavailable("no monthly NPPES dissemination file listed on " + NPPES_PAGE)
        url = "https://download.cms.gov/nppes/" + names[0]
        z = d / names[0]
    rec = download(url, z, force=force)
    cache = d / (z.stem + "_taxonomy.csv")
    if not cache.exists() or force:
        tcols = [f"Healthcare Provider Taxonomy Code_{i}" for i in range(1, 16)]
        scols = [f"Healthcare Provider Primary Taxonomy Switch_{i}" for i in range(1, 16)]
        with zipfile.ZipFile(z) as zf:
            member = next(n for n in zf.namelist() if n.lower().startswith("npidata_pfile") and n.lower().endswith(".csv") and "fileheader" not in n.lower())
            first = True
            for ch in pd.read_csv(zf.open(member), dtype=str, chunksize=500_000, usecols=["NPI", "Entity Type Code"] + tcols + scols):
                ch = ch[ch["Entity Type Code"] == "1"]
                T, S = ch[tcols].to_numpy(), ch[scols].to_numpy()
                prim, allc = [], []
                for trow, srow in zip(T, S):
                    codes = [c for c in trow if isinstance(c, str)]
                    p = next((c for c, s in zip(trow, srow) if isinstance(c, str) and s == "Y"), codes[0] if codes else "")
                    prim.append(p)
                    allc.append("|".join(codes))
                pd.DataFrame({"npi": ch["NPI"].to_numpy(), "nppes_primary_taxonomy": prim, "nppes_taxonomies": allc}).to_csv(
                    cache, index=False, mode="w" if first else "a", header=first)
                first = False
    src = {"dataset": "CMS NPPES (National Plan and Provider Enumeration System) monthly data dissemination file", "dataset_id": z.name,
           "release": z.stem.replace("NPPES_Data_Dissemination_", "").replace("_V2", "").replace("_", " "), "url": url, "landing": NPPES_PAGE,
           "raw_file": f"data/raw/nppes/{z.name}", "bytes": rec["bytes"], "sha256": rec["sha256"], "fetched_utc": rec["fetched_utc"],
           "filter": "Entity Type Code == 1 (individuals); taxonomy code and primary-taxonomy switch columns 1-15; then NPI in the hospital's roster"}
    return pd.read_csv(cache, dtype=str).fillna(""), src


def _nucc():
    try:
        rec = download(NUCC_URL, RAW / "nppes" / "nucc_taxonomy.csv")
        t = pd.read_csv(RAW / "nppes" / "nucc_taxonomy.csv", dtype=str, encoding="latin-1").fillna("")
        t["name"] = (t["Classification"] + " / " + t["Specialization"]).str.strip(" /")
        return t.set_index("Code")["name"].to_dict(), {"dataset": "NUCC Health Care Provider Taxonomy code set, version 25.1", "url": NUCC_URL,
                                                       "sha256": rec["sha256"], "fetched_utc": rec["fetched_utc"]}
    except Exception as e:  # noqa: BLE001
        return {}, {"dataset": "NUCC Health Care Provider Taxonomy code set", "url": NUCC_URL, "unavailable": f"{type(e).__name__}: {e}"}


def fetch(ccn, force: bool = False) -> dict:
    ccn = norm_ccn(ccn)
    fa_path, fa_src = pdc_dataset("27ea-46a8", force)
    fa = pd.read_csv(fa_path, dtype=str, usecols=["NPI", "facility_type", "Facility Affiliations Certification Number"])
    fa.columns = ["npi", "facility_type", "ccn"]
    hosp = fa[fa["facility_type"] == "Hospital"].drop_duplicates(["npi", "ccn"])
    mine = fa[fa["ccn"] == ccn]
    if mine.empty:
        raise SourceUnavailable(f"Facility Affiliation Data has no clinician affiliated with certification number {ccn}")
    types_here = {k: int(v) for k, v in mine.drop_duplicates(["npi", "facility_type"])["facility_type"].value_counts().items()}
    npis = sorted(set(mine["npi"]))
    n_hosp = hosp[hosp["npi"].isin(npis)].groupby("npi")["ccn"].nunique()
    fa_src["filter"] = f"'Facility Affiliations Certification Number' == '{ccn}' (facility types found: {types_here})"

    ndf_path, ndf_src = pdc_dataset("mj5m-pzi6", force)
    ndf = pd.read_csv(ndf_path, dtype=str, usecols=["NPI", "Cred", "Grd_yr", "pri_spec", "sec_spec_all"])
    ndf = ndf[ndf["NPI"].isin(npis)].drop_duplicates("NPI").set_index("NPI")
    ndf_src["filter"] = "NPI in the hospital's Facility Affiliation rows; first row per NPI; columns Cred, Grd_yr, pri_spec, sec_spec_all"

    sources = {"facility_affiliation": fa_src, "national_downloadable_file": ndf_src}
    unavailable = {}
    try:
        mup, mup_src = _mup_ed(force)
        mup = mup.set_index("npi")
        sources["medicare_by_provider_and_service"] = mup_src
    except SourceUnavailable as e:
        mup, unavailable["medicare_by_provider_and_service"] = None, str(e)
    try:
        npp, npp_src = _nppes(force)
        npp = npp[npp["npi"].isin(npis)].set_index("npi")
        sources["nppes"] = npp_src
    except SourceUnavailable as e:
        npp, unavailable["nppes"] = None, str(e)
    nucc, nucc_src = _nucc()
    sources["nucc_taxonomy"] = nucc_src
    em_codes = sorted(c for c, n in nucc.items() if "emergency" in n.lower()) or ["207P00000X"]

    cols = ["npi", "pri_spec", "cred", "grd_yr", "sec_spec", "n_hospitals", "ed_visit_services", "critical_care_services", "nppes_primary_taxonomy",
            "nppes_any_emergency_taxonomy"]
    rows = []
    for n in npis:
        d = ndf.loc[n] if n in ndf.index else None
        g = lambda k: (None if d is None or pd.isna(d[k]) else str(d[k]))  # noqa: E731
        ed = cc = None
        if mup is not None:
            ed, cc = (int(mup.at[n, "ed_visit_services"]), int(mup.at[n, "critical_care_services"])) if n in mup.index else (0, 0)
        tax = anyem = None
        if npp is not None and n in npp.index:
            tax = npp.at[n, "nppes_primary_taxonomy"] or None
            anyem = int(any(c in em_codes for c in npp.at[n, "nppes_taxonomies"].split("|")))
        gy = g("Grd_yr")
        rows.append([n, g("pri_spec"), g("Cred"), int(gy) if gy and gy.isdigit() else None, g("sec_spec_all"), int(n_hosp.get(n, 0)), ed, cc, tax, anyem])
    df = pd.DataFrame(rows, columns=cols)
    spec = df["pri_spec"].fillna("(not in National Downloadable File)")
    is_app = df["pri_spec"].isin(APP_SPECIALTIES)
    is_phys = df["pri_spec"].notna() & ~df["pri_spec"].isin(NON_PHYSICIAN)
    em_pri = df["pri_spec"] == "EMERGENCY MEDICINE"
    em_sec = ~em_pri & df["sec_spec"].fillna("").str.contains("EMERGENCY MEDICINE")
    edv = df["ed_visit_services"].fillna(0)
    em_app = is_app & (edv >= EM_APP_MIN_SERVICES)
    em_tax_only = is_phys & ~em_pri & ~em_sec & (df["nppes_any_emergency_taxonomy"] == 1)
    app_em_tax = is_app & (df["nppes_any_emergency_taxonomy"] == 1)
    counts = {
        "clinicians_affiliated_total": int(len(df)), "physicians_total": int(is_phys.sum()), "apps_total": int(is_app.sum()),
        "nurse_practitioners": int((df["pri_spec"] == "NURSE PRACTITIONER").sum()), "physician_assistants": int((df["pri_spec"] == "PHYSICIAN ASSISTANT").sum()),
        "em_physicians": int(em_pri.sum()), "em_physicians_only_this_hospital": int((em_pri & (df["n_hospitals"] <= 1)).sum()),
        "em_physicians_secondary_specialty": int(em_sec.sum()), "em_physicians_nppes_taxonomy_only": int(em_tax_only.sum()),
        "em_physicians_billing_ed_visits": int((em_pri & (edv >= EM_APP_MIN_SERVICES)).sum()) if mup is not None else None,
        "em_apps": int(em_app.sum()) if mup is not None else None,
        "em_apps_nurse_practitioners": int((em_app & (df["pri_spec"] == "NURSE PRACTITIONER")).sum()) if mup is not None else None,
        "em_apps_physician_assistants": int((em_app & (df["pri_spec"] == "PHYSICIAN ASSISTANT")).sum()) if mup is not None else None,
        "apps_with_emergency_nppes_taxonomy": int(app_em_tax.sum()) if npp is not None else None,
        "non_em_physicians_billing_ed_visits": int((is_phys & ~em_pri & (edv >= EM_APP_MIN_SERVICES)).sum()) if mup is not None else None,
        "ed_visit_services_billed_by_em_physicians": int(edv[em_pri].sum()) if mup is not None else None,
        "ed_visit_services_billed_by_em_apps": int(edv[em_app].sum()) if mup is not None else None,
        "not_in_national_downloadable_file": int(df["pri_spec"].isna().sum()),
        "affiliated_with_other_hospitals_too": int((df["n_hospitals"] > 1).sum()),
    }
    for k, specs in POOLS.items():
        counts[k] = int(df["pri_spec"].isin(specs).sum())
    gy = df.loc[em_pri, "grd_yr"].dropna()
    out = {"source": {"dataset": "CMS Doctors and Clinicians: Facility Affiliation Data joined to the National Downloadable File, Medicare by-provider-and-service "
                                 "and NPPES", "release": fa_src.get("release"), "url": fa_src["url"], "landing": fa_src["landing"],
                      "sha256": fa_src["sha256"], "fetched_utc": fa_src["fetched_utc"], "filter": fa_src["filter"], "components": sources,
                      "unavailable": unavailable},
           "ccn": ccn,
           "definitions": {
               "em_physicians": "pri_spec == 'EMERGENCY MEDICINE' in the National Downloadable File",
               "em_apps": f"pri_spec in {APP_SPECIALTIES} and at least {EM_APP_MIN_SERVICES} emergency-department visit services (HCPCS 99281-99285, place of service "
                          f"facility) billed under the clinician's own NPI to original Medicare in {MUP_YEAR}. A LOWER BOUND: visits billed under a supervising "
                          "physician, Medicare Advantage / commercial / Medicaid visits and suppressed rows (10 or fewer beneficiaries) are not visible.",
               "physicians_total": "pri_spec present and not one of the non-physician specialties " + ", ".join(sorted(NON_PHYSICIAN)),
               "n_hospitals": "number of distinct hospital certification numbers the NPI is affiliated with in the Facility Affiliation file",
               "nppes_any_emergency_taxonomy": f"1 if any of the NPI's NPPES taxonomy codes is one of {em_codes} (NUCC names containing 'emergency')",
               "ed_visit_services": "services, not patients and not hours; billed anywhere in the country, not necessarily at this hospital"},
           "not_covered": [
               "Residents and fellows: not enrolled as Medicare billing clinicians. Use the cost report's intern and resident FTE (hcris.json).",
               "Nurses, technicians and all other employed staff: use registered-nurse FTE from the Provider of Services file and total FTE from the cost report.",
               "Clinicians not enrolled in Medicare, or without enough recent Medicare claims at this hospital for CMS to affiliate them.",
               "Hours worked: affiliation says a clinician practises at the hospital, not how much or in which department. "
               f"{counts['affiliated_with_other_hospitals_too']} of {counts['clinicians_affiliated_total']} clinicians are affiliated with other hospitals as well."],
           "counts": counts,
           "em_physician_graduation_year": {"median": float(gy.median()) if len(gy) else None, "min": int(gy.min()) if len(gy) else None, "max": int(gy.max()) if len(gy) else None},
           "by_specialty": [{"pri_spec": k, "n": int(v)} for k, v in spec.value_counts().items()],
           "by_credential": {str(k): int(v) for k, v in df["cred"].fillna("(blank)").value_counts().items()},
           "app_nppes_primary_taxonomy": [{"code": k, "name": nucc.get(k), "n": int(v)} for k, v in df.loc[is_app, "nppes_primary_taxonomy"].fillna("(none)").value_counts().items()],
           "columns": cols, "rows": rows}
    write_json(out, out_dir(ccn) / f"{NAME}.json", compact=True)
    return out
