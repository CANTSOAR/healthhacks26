#!/usr/bin/env python3
"""Bounded acquisition of public ICD-10 and RxNorm teaching terminology."""
import hashlib, io, json, re, subprocess, urllib.parse, zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
UA = "HealthHacksResearch/0.1 (bounded academic terminology acquisition)"
MAX_BYTES = 25_000_000

def fetch(url):
    result = subprocess.run(["curl", "-L", "--fail", "--silent", "--show-error", "--max-time", "90", "-A", UA, url], capture_output=True, timeout=95, check=True)
    body = result.stdout
    if len(body) > MAX_BYTES:
        raise ValueError(f"bounded response exceeds {MAX_BYTES} bytes: {url}")
    return body

def sha(body):
    return hashlib.sha256(body).hexdigest()

def save(dataset_id, title, source_urls, raw_files, rows, rights, scope, limits, retrieved):
    raw_paths, hashes = [], {}
    for name, body in raw_files.items():
        rel = f"raw/{dataset_id}/{name}"
        dest = BASE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        raw_paths.append(rel)
        hashes[rel] = sha(body)
    records = []
    for index, (row, raw_name, locator, record_type) in enumerate(rows, 1):
        rel = f"raw/{dataset_id}/{raw_name}"
        record_url = source_urls[0]
        if "query" in row:
            record_url = next((url for url in source_urls if urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("name") == [row["query"]]), record_url)
        records.append({
            "record_id": f"{dataset_id}:{index:06d}", "source_id": dataset_id,
            "source_record_id": str(row.get("code", row.get("rxcui", index))),
            "record_type": record_type, "data": row,
            "provenance": {
                "source_url": record_url, "retrieved_at": retrieved,
                "raw_sha256": hashes[rel], "raw_path": rel,
                "raw_artifact_kind": "original_downloaded_response_bytes" if rel.endswith(".zip") else "original_api_response_bytes",
                "locator": locator, "transformation": "Parsed source record; source text preserved in referenced raw artifact.",
                "acquisition_method": "HTTPS download; deterministic parse",
            },
            "evidence_kind": "published_reference", "review_status": "unreviewed",
            "mapping_status": "unmapped", "limitations": limits,
        })
    norm_rel = f"normalized/{dataset_id}.jsonl"
    norm_path = BASE / norm_rel
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    norm_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    manifest = {
        "dataset_id": dataset_id, "source_id": dataset_id, "title": title,
        "source_url": source_urls[0], "source_urls": source_urls,
        "record_count": len(records), "raw_paths": raw_paths, "raw_sha256": hashes,
        "normalized_path": norm_rel, "scope": scope, "access": "public",
        "rights": rights, "acquisition_status": "acquired", "retrieved_at": retrieved,
        "limits": limits,
        "provenance": {
            "method": "HTTPS source download; deterministic normalization",
            "script": "scripts/acquire_clinical_wave2.py",
            "raw_artifact_kind": "original_downloaded_response_bytes" if all(name.endswith(".zip") for name in raw_files) else "original_api_response_bytes",
        },
    }
    (BASE / "catalog" / f"{dataset_id}.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return len(records)

def codes_dataset(dataset_id, title, url, member, regex, record_type, rights, scope, limits, keep):
    retrieved = datetime.now(timezone.utc).isoformat()
    body = fetch(url)
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        content = archive.read(member).decode("utf-8-sig")
    rows = []
    selected_by_term = {}
    for line_no, line in enumerate(content.splitlines(), 1):
        match = re.match(regex, line.strip())
        if match:
            code, label = match.group(1), match.group(2).strip()
            if isinstance(keep, dict):
                category = next((term for term, quota in keep.items() if term in label.lower() and selected_by_term.get(term, 0) < quota), None)
                include = category is not None
                if include:
                    selected_by_term[category] = selected_by_term.get(category, 0) + 1
            else:
                include = keep(code, label)
            if include:
                rows.append(({"code": code, "title": label}, "source.zip", f"{member}:{line_no}", record_type))
                if len(rows) >= 500:
                    break
    if not rows:
        raise ValueError(f"No records parsed from {member}")
    return save(dataset_id, title, [url], {"source.zip": body}, rows, rights, scope, limits, retrieved)

def acquire():
    cms_rights = {"license": "U.S. federal government work; CMS-published ICD-10-PCS code file", "terms_url": "https://www.cms.gov/about-cms/agency-information/aboutwebsite/website-policies/copyright-permissions", "scope": "Official public code-and-title reference; preserve CMS attribution; not a clinical guideline."}
    cdc_rights = {"license": "U.S. federal government work; NCHS-published ICD-10-CM code file", "terms_url": "https://www.cdc.gov/other/agencymaterials.html", "scope": "Official public code-and-title reference; preserve CDC/NCHS attribution; not a clinical guideline."}
    limits = ["Terminology/coding reference only; not a diagnosis, procedure recommendation, care pathway, outcome rate, or patient-level dataset.", "Confirm the applicable release and official coding guidelines before any operational coding use.", "No locally calibrated prevalence, resource use, or care timing is supplied."]
    dx_terms = ("myocardial infarction", "chest pain", "heart failure", "atrial fibrillation", "cardiac arrhythmia", "sepsis", "pneumonia", "respiratory failure", "acute kidney injury", "syncope", "cerebral infarction", "stroke", "gastrointestinal hemorrhage", "shock", "hypoxemia")
    cm_url = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/icd10cm-code-descriptions-2027.zip"
    cm = codes_dataset("w2-clinical-icd10cm-dx-2027", "FY2027 ICD-10-CM selected acute-care diagnosis code descriptions", cm_url, "icd10cm-code-descriptions-2027/icd10cm-codes-2027.txt", r"^([A-Z][A-Z0-9]{2,6})\s+(.+)$", "DiagnosisCode", cdc_rights, "Selected FY2027 U.S. ICD-10-CM billable codes with titles containing common acute-care terms (MI, chest pain, heart failure, arrhythmia, sepsis, pneumonia, respiratory failure, AKI, syncope, stroke, GI hemorrhage, shock, hypoxemia); up to 500 records; full source release ZIP preserved.", limits, lambda code, title: any(term in title.lower() for term in dx_terms))
    pcs_terms = {"coronary": 100, "transfusion": 80, "ventilation": 57, "endotracheal": 6, "dialysis": 11, "extirpation": 100, "thrombolytic": 20, "pacemaker": 77}
    pcs_url = "https://www.cms.gov/files/zip/2027-icd-10-pcs-codes-file.zip"
    pcs = codes_dataset("w2-clinical-icd10pcs-proc-2027", "FY2027 ICD-10-PCS selected procedure code descriptions", pcs_url, "icd10pcs_codes_2027.txt", r"^([A-Z0-9]{7})\s+(.+)$", "ProcedureCode", cms_rights, "Selected FY2027 inpatient ICD-10-PCS titles in up to eight illustrative categories: coronary, transfusion, ventilation, endotracheal, dialysis, extirpation, thrombolytic, and pacemaker; full source release ZIP preserved. Extirpation is a PCS operation title, not proof a code means thrombectomy.", limits, pcs_terms)
    rx_urls, raw_files, rows = [], {}, []
    retrieved = datetime.now(timezone.utc).isoformat()
    for term in ["aspirin", "nitroglycerin", "heparin", "metoprolol", "furosemide"]:
        url = "https://rxnav.nlm.nih.gov/REST/drugs.json?" + urllib.parse.urlencode({"name": term})
        body = fetch(url)
        raw_name = term + ".json"
        raw_files[raw_name] = body
        rx_urls.append(url)
        result = json.loads(body)
        for group in result.get("drugGroup", {}).get("conceptGroup", []) or []:
            tty = group.get("tty")
            for concept in group.get("conceptProperties", []) or []:
                rows.append(({"query": term, "rxcui": concept.get("rxcui"), "name": concept.get("name"), "synonym": concept.get("synonym"), "tty": tty}, raw_name, f"drugGroup.conceptGroup[tty={tty}].conceptProperties[rxcui={concept.get('rxcui')}]", "RxNormDrugConcept"))
    rx_rights = {"license": "NLM RxNav/RxNorm API public access", "terms_url": "https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html", "scope": "Selected ingredient name queries returning RxNorm drug concept names, forms and strengths; NLM service terms apply; third-party marks/names remain with owners."}
    rx_limits = ["Identity/form lookups only; results are not a hospital formulary, medication order, dose, treatment, interaction check, or recommendation.", "Name query may return many concepts, obsolete or branded presentations; a qualified reviewer must select concepts for a use case.", "No administration routes, dose selection, or clinical indications are inferred."]
    rx = save("w2-clinical-rxnorm-forms", "NLM RxNorm selected drug form and strength concepts", rx_urls, raw_files, rows, rx_rights, "Five teaching-relevant ingredient name queries; concept records preserve source term type (TTY) and RxCUI.", rx_limits, retrieved)
    return {"icd10cm": cm, "icd10pcs": pcs, "rxnorm": rx}

if __name__ == "__main__":
    print(json.dumps(acquire()))
