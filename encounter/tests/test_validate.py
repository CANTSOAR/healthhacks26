import copy
import json

import jsonschema
import pytest

from encounter.paths import CONTRACTS_DIR, SEED_CASES_DIR
from encounter.rubric import get_rubric
from encounter.validate import validate_case

from .conftest import SEED_IDS, seed_case

SCHEMA = json.loads((CONTRACTS_DIR / "case.schema.json").read_text())


@pytest.mark.parametrize("cid", SEED_IDS)
def test_seed_cases_conform_and_validate(cid):
    c = seed_case(cid)
    jsonschema.validate(c, SCHEMA)
    rep = validate_case(c, get_rubric())
    assert rep["ok"], rep
    assert rep["errors"] == [] and [x for x in rep["consistency"] if x["level"] == "contradiction"] == []
    assert c["status"] == "published" and c["review"]["needs_faculty_review"] is True and c["review"]["synthetic"] is True
    assert 15 <= len(c["facts"]) <= 30 and 5 <= len(c["objectives"]) <= 8
    kinds = {a["kind"] for a in c["chart"]["artifacts"]}
    assert "lab_report" in kinds and kinds & {"ecg", "xray", "ct", "prior_note"}
    assert c["sources"]


def test_at_least_three_seed_cases_one_concealing():
    files = sorted(SEED_CASES_DIR.glob("*.v1.json"))
    assert len(files) >= 3
    rules = {f["disclosure"]["rule"] for p in files for f in json.loads(p.read_text())["facts"]}
    assert "denied_until_confronted" in rules and "after_rapport" in rules


def test_good_mini_case(mini_case):
    assert validate_case(mini_case)["ok"]


def _errors(case):
    rep = validate_case(case)
    return rep, " | ".join(e["path"] + " " + e["message"] for e in rep["errors"])


def test_schema_violation(mini_case):
    del mini_case["profile"]["age"]
    mini_case["status"] = "live"
    rep, text = _errors(mini_case)
    assert not rep["ok"] and "age" in text and "/status" in text


def test_duplicate_ids(mini_case):
    mini_case["facts"].append(copy.deepcopy(mini_case["facts"][1]))
    mini_case["objectives"].append(copy.deepcopy(mini_case["objectives"][0]))
    rep, text = _errors(mini_case)
    assert "duplicate fact_id" in text and "duplicate objective_id" in text


def test_dangling_references(mini_case):
    mini_case["objectives"][0]["linked_fact_ids"] = ["f.nope.missing"]
    mini_case["chart"]["artifacts"][0]["linked_fact_ids"] = ["f.lab.ghost"]
    mini_case["chart"]["artifacts"][0]["section_id"] = "no_such_section"
    mini_case["facts"][1]["chart_section"] = "also_missing"
    mini_case["facts"][1]["source_ids"] = ["src.none"]
    mini_case["facts"][4]["disclosure"]["confront_with"] = ["art.nothing"]
    rep, text = _errors(mini_case)
    for needle in ("f.nope.missing", "f.lab.ghost", "no_such_section", "also_missing", "src.none", "art.nothing"):
        assert needle in text, needle
    assert not rep["ok"]


def test_disclosure_rules_missing_parameters(mini_case):
    mini_case["facts"][3]["disclosure"] = {"rule": "after_rapport"}
    mini_case["facts"][4]["disclosure"] = {"rule": "denied_until_confronted"}
    del mini_case["facts"][4]["cover_answer"]
    mini_case["facts"][6]["disclosure"] = {"rule": "on_request"}
    rep, text = _errors(mini_case)
    assert "rapport_needed" in text and "confront_with" in text and "cover_answer" in text and "on_request needs request" in text


def test_patient_cannot_voice_fact(mini_case):
    del mini_case["facts"][1]["patient_answer"]
    mini_case["facts"][2]["patient_knows"] = False
    rep, text = _errors(mini_case)
    assert "no patient_answer wording" in text and "patient_knows is false" in text


def test_objective_without_evidence_path(mini_case):
    mini_case["objectives"][0]["linked_fact_ids"] = []
    mini_case["objectives"][1]["linked_requests"] = []
    mini_case["objectives"][2] = {"objective_id": "obj.vague", "criterion": "Be good", "kind": "communication"}
    rep, text = _errors(mini_case)
    assert text.count("evidence path") >= 3


def test_critical_fact_unreachable(mini_case):
    # confrontation evidence is itself only obtainable by confronting -> cycle -> unreachable
    mini_case["facts"][4]["disclosure"]["confront_with"] = ["f.concealed.loop"]
    mini_case["facts"].append({"fact_id": "f.concealed.loop", "category": "concealed", "statement": "x", "patient_knows": True, "patient_answer": "x",
                               "cover_answer": "no", "disclosure": {"rule": "denied_until_confronted", "confront_with": ["f.concealed.alcohol"]}})
    rep, text = _errors(mini_case)
    assert "critical fact f.concealed.alcohol can never be released" in text


def test_contradictions(mini_case):
    c = mini_case
    c["facts"].append({"fact_id": "f.risk.smoking", "category": "risk", "statement": "Never smoked", "patient_knows": True, "patient_answer": "Never.",
                       "disclosure": {"rule": "if_asked"}, "polarity": "negative"})
    c["chart"]["artifacts"][0]["content"][0]["value"] = 120                     # artifact disagrees with linked fact (940)
    c["facts"].append({"fact_id": "f.allergies.penicillin", "category": "allergies", "statement": "Penicillin allergy: rash", "patient_knows": True,
                       "patient_answer": "Penicillin gives me a rash.", "disclosure": {"rule": "if_asked"}, "polarity": "positive"})
    c["facts"].append({"fact_id": "f.allergies.none", "category": "allergies", "statement": "No known drug allergies", "patient_knows": True,
                       "patient_answer": "None.", "disclosure": {"rule": "if_asked"}, "polarity": "negative"})
    c["facts"].append({"fact_id": "f.medications.abx", "category": "medications", "statement": "Taking amoxicillin 500 mg three times daily", "patient_knows": True,
                       "patient_answer": "Amoxicillin.", "disclosure": {"rule": "if_asked"}})
    c["prebrief"] = "A 35-year-old woman with pain. She has smoked for 60 years."
    rep = validate_case(c)
    kinds = {x["kind"] for x in rep["consistency"] if x["level"] == "contradiction"}
    assert {"fact_polarity", "artifact_value", "allergy_vs_medication", "allergy_polarity", "age"} <= kinds, kinds
    assert not rep["ok"]
    assert sum(1 for x in rep["consistency"] if x["kind"] == "age") == 2


def test_warnings_do_not_block(mini_case):
    mini_case["objectives"][1]["linked_requests"] = ["order:lipase", "order:unicorn"]
    rep = validate_case(mini_case)
    assert rep["ok"] and any("order:unicorn" in w["message"] for w in rep["warnings"])
