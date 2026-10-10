#!/usr/bin/env python3
"""Normalize the complete CMS FY2027 ICD-10-PCS code/title file from retained ZIP."""
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE_DATASET = "w2-clinical-icd10pcs-proc-2027"
DATASET_ID = "cms-icd10pcs-2027-full"
CMS_URL = "https://www.cms.gov/files/zip/2027-icd-10-pcs-codes-file.zip"
CMS_INDEX = "https://www.cms.gov/medicare/coding-billing/ICD-10-codes"
MEMBER = "icd10pcs_codes_2027.txt"
CODE_LINE = re.compile(r"^([A-Z0-9]{7})\s+(.+)$")
LIMITS = [
    "Code/title reference only; not procedures performed, RWJ offerings, recommendations, protocols, utilization, outcomes, or patient records.",
    "CMS lists this code file for discharges October 1, 2026 through March 31, 2027; check CMS for later FY2027 updates.",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    source_manifest_path = BASE / "catalog" / f"{SOURCE_DATASET}.json"
    source_manifest = json.loads(source_manifest_path.read_text())
    raw_rel = f"raw/{SOURCE_DATASET}/source.zip"
    raw_path = BASE / raw_rel
    raw_bytes = raw_path.read_bytes()
    digest = sha256(raw_bytes)
    expected_digest = source_manifest.get("raw_sha256", {}).get(raw_rel)
    if source_manifest.get("source_url") != CMS_URL or "2027" not in source_manifest.get("title", ""):
        raise ValueError("Source manifest does not identify the official CMS FY2027 PCS release")
    if source_manifest.get("acquisition_status") != "acquired" or not expected_digest or digest != expected_digest:
        raise ValueError("Retained ZIP does not match the acquired source manifest SHA-256")
    if raw_rel not in source_manifest.get("raw_paths", []):
        raise ValueError("Retained ZIP is not listed in source manifest raw_paths")

    with zipfile.ZipFile(raw_path) as archive:
        names = archive.namelist()
        if MEMBER not in names:
            raise ValueError(f"Official ZIP is missing expected code file {MEMBER}")
        code_text = archive.read(MEMBER).decode("utf-8-sig")

    records = []
    seen = set()
    for line_number, line in enumerate(code_text.splitlines(), 1):
        match = CODE_LINE.fullmatch(line.strip())
        if not match:
            raise ValueError(f"Unexpected line {line_number} in {MEMBER}: {line[:120]!r}")
        code, title = match.group(1), match.group(2).strip()
        if code in seen:
            raise ValueError(f"Duplicate code {code} at source line {line_number}")
        seen.add(code)
        index = len(records) + 1
        records.append({
            "record_id": f"{DATASET_ID}:{index:06d}",
            "source_id": DATASET_ID,
            "source_record_id": code,
            "record_type": "ProcedureCode",
            "data": {"code": code, "title": title},
            "scope": "CMS FY2027 ICD-10-PCS code/title file",
            "provenance": {
                "source_url": CMS_URL,
                "retrieved_at": source_manifest["retrieved_at"],
                "raw_sha256": digest,
                "raw_path": raw_rel,
                "raw_artifact_kind": "original_downloaded_response_bytes",
                "locator": f"{MEMBER}:{line_number}",
                "transformation": "Parsed code and title from source line.",
            },
            "evidence_kind": "published_reference",
            "review_status": "unreviewed",
            "mapping_status": "unmapped",
            "limitations": LIMITS,
        })
    if not records:
        raise ValueError("No code records parsed")

    norm_rel = f"normalized/{DATASET_ID}.jsonl"
    (BASE / norm_rel).write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records))
    manifest = {
        "dataset_id": DATASET_ID,
        "source_id": DATASET_ID,
        "title": "FY2027 ICD-10-PCS complete code and title reference",
        "source_url": CMS_URL,
        "source_urls": [CMS_URL],
        "record_count": len(records),
        "raw_paths": [raw_rel],
        "raw_sha256": {raw_rel: digest},
        "normalized_path": norm_rel,
        "scope": f"All {len(records):,} unique seven-character ICD-10-PCS code/title entries in {MEMBER} within the retained CMS FY2027 release ZIP; CMS lists this file for discharges October 1, 2026 through March 31, 2027. Terminology catalog only: count is not procedures performed and does not describe RWJ offerings or capabilities.",
        "access": "public",
        "rights": {
            "license": "U.S. federal government work; CMS-published ICD-10-PCS code file",
            "terms_url": "https://www.cms.gov/about-cms/agency-information/aboutwebsite/website-policies/copyright-permissions",
            "scope": "Official public code-and-title reference; preserve CMS attribution; not a clinical guideline.",
        },
        "acquisition_status": "acquired",
        "retrieved_at": source_manifest["retrieved_at"],
        "limits": LIMITS,
        "provenance": {
            "method": "Deterministic normalization of retained original CMS ZIP download",
            "script": "scripts/acquire_full_pcs.py",
            "raw_artifact_kind": "original_downloaded_response_bytes",
            "source_member": MEMBER,
            "source_dataset_manifest": f"catalog/{SOURCE_DATASET}.json",
            "validated_source_sha256": digest,
            "official_release_index": CMS_INDEX,
            "official_release_period": "Discharges October 1, 2026 through March 31, 2027, per CMS ICD-10 files page checked 2026-10-10.",
        },
    }
    (BASE / "catalog" / f"{DATASET_ID}.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"dataset_id": DATASET_ID, "records": len(records), "duplicates": 0, "raw_sha256": digest, "normalized_bytes": (BASE / norm_rel).stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
