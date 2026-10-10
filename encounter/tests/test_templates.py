import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from encounter import templates as tpl
from encounter.paths import CONTRACTS_DIR, REPO_ROOT, TEMPLATES_DIR
from encounter.providers import AnthropicProvider
from encounter.rubric import get_rubric
from encounter.validate import validate_case

from .conftest import FakeAnthropic

GROUPS = yaml.safe_load((CONTRACTS_DIR / "enums.yaml").read_text())["condition_group"]
CASE_SCHEMA = json.loads((CONTRACTS_DIR / "case.schema.json").read_text())
CATALOG_SCHEMA = json.loads((CONTRACTS_DIR / "catalog.schema.json").read_text())
CASE_VALIDATOR = jsonschema.Draft202012Validator(CASE_SCHEMA)
CATS = set(CASE_SCHEMA["properties"]["facts"]["items"]["properties"]["category"]["enum"])


def test_one_template_per_condition_group():
    assert sorted(p.stem for p in TEMPLATES_DIR.glob("*.yaml")) == sorted(GROUPS)


@pytest.mark.parametrize("group", GROUPS)
def test_template_file_shape(group):
    t = yaml.safe_load((TEMPLATES_DIR / f"{group}.yaml").read_text())
    jsonschema.validate(t, CATALOG_SCHEMA)
    assert t["synthetic"] is True and t["needs_faculty_review"] is True and t["condition_group"] == group
    assert isinstance(t["facts"], list) and len(t["facts"]) >= 15
    ids = [f["fact_id"] for f in t["facts"]]
    assert len(ids) == len(set(ids))
    for f in t["facts"]:
        assert f["fact_id"].startswith(f"f.{f['category']}.") and f["category"] in CATS
        assert f["disclosure"]["rule"] in ("volunteered", "if_asked", "after_rapport", "denied_until_confronted", "chart_initial", "on_request")
        assert f["discoverable_by"]
    cats = {f["category"] for f in t["facts"]}
    assert {"chief_complaint", "hpi", "pmh", "medications", "allergies", "social", "family", "vitals", "exam", "lab"} <= cats
    assert t["typical_concealments"] and set(t["typical_concealments"]) <= set(ids)
    assert t["objectives"] and t["rubric_links"]["rubric_id"] == "default" and t["sources"]
    for s in t["sources"]:
        assert s.get("url", "").startswith("https://") or "unsourced" in s["title"]


@pytest.mark.parametrize("group", GROUPS)
def test_instantiation_is_valid_and_deterministic(group):
    for sev in (0.05, 0.5, 0.95):
        for seed in (1, 11):
            for sex in ("male", "female"):
                lt = {"patient_id": 100 + seed, "seed": seed, "condition_group": group, "condition_template": group, "severity": sev, "acuity": 3,
                      "true_disposition": "admit" if sev > 0.6 else "discharge", "age": 40 + seed, "sex": sex, "facts": []}
                c = tpl.instantiate_case(group, lt)
                assert c == tpl.instantiate_case(group, lt)                                   # same patient, same case
                assert not list(CASE_VALIDATOR.iter_errors(c))
                rep = validate_case(c, get_rubric())
                assert rep["ok"], (group, sev, seed, sex, rep["errors"], rep["consistency"])
                assert c["origin"] == {"kind": "from_sim_patient", "condition_template": group, "sim_seed": seed, "sim_patient_id": 100 + seed}
                assert c["profile"]["age"] == 40 + seed and c["profile"]["gender"] == sex
                assert c["faculty_truth"]["expected_disposition"] == lt["true_disposition"] and c["faculty_truth"]["severity"] == sev
                assert 15 <= len(c["facts"]) <= 30
                init = [a for a in c["chart"]["artifacts"] if a["release"]["rule"] == "initial"]
                assert [a["artifact_id"] for a in init] == ["art.triage_note"]
                assert all(f["disclosure"]["rule"] == "chart_initial" for f in c["facts"] if f["category"] == "vitals")
                assert all(f["disclosure"]["rule"] == "on_request" for f in c["facts"] if f["category"] in ("lab", "imaging"))
                assert c["review"]["needs_faculty_review"] is True


def test_different_seed_or_severity_changes_the_case():
    base = {"patient_id": 1, "seed": 5, "severity": 0.5, "sex": "female", "age": 50, "true_disposition": "admit"}
    a = tpl.instantiate_case("chest_pain", base)
    b = tpl.instantiate_case("chest_pain", {**base, "seed": 6})
    c = tpl.instantiate_case("chest_pain", {**base, "severity": 0.9})
    assert a["profile"]["name"] != b["profile"]["name"] or a["facts"] != b["facts"]
    cc = lambda x: next(f["statement"] for f in x["facts"] if f["category"] == "chief_complaint")
    assert cc(a) != cc(c)


def test_latent_truth_values_override_template_draws():
    lt = {"patient_id": 9, "seed": 9, "severity": 0.9, "sex": "male", "age": 60, "true_disposition": "admit", "diagnosis": "Sim says NSTEMI",
          "facts": [{"fact_id": "f.lab.troponin", "category": "lab", "value": 777}, {"fact_id": "f.vitals.heart_rate", "category": "vitals", "value": 133}]}
    c = tpl.instantiate_case("chest_pain", lt)
    f = {x["fact_id"]: x for x in c["facts"]}
    assert f["f.lab.troponin"]["value"] == 777 and "777" in f["f.lab.troponin"]["statement"] and f["f.lab.troponin"]["flag"] == "H"
    assert f["f.vitals.heart_rate"]["value"] == 133
    assert c["faculty_truth"]["diagnosis"] == "Sim says NSTEMI"
    row = next(a for a in c["chart"]["artifacts"] if a["artifact_id"] == "art.cardiac_labs")["content"][0]
    assert row["value"] == 777 and row["fact_id"] == "f.lab.troponin"          # artifact agrees with the fact


def test_sample_fact_values_match_instantiation_and_latent_truth_shape():
    schema = json.loads((CONTRACTS_DIR / "interaction.schema.json").read_text())
    vals = tpl.sample_fact_values("abdominal_pain", 0.8, 21, age=44, sex="F")
    lt = {"patient_id": 3, "seed": 21, "condition_group": "abdominal_pain", "condition_template": "abdominal_pain", "severity": 0.8, "acuity": 2,
          "true_disposition": "admit", "age": 44, "sex": "F", "facts": vals}
    jsonschema.validate(lt, {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/latent_truth"})
    c = tpl.instantiate_case("abdominal_pain", {**lt, "facts": []})
    assert {v["fact_id"]: v["value"] for v in vals} == {f["fact_id"]: f.get("value") for f in c["facts"]}


def test_from_description_offline_is_a_draft():
    out = tpl.from_description("72 year old woman with sudden slurred speech and right arm weakness, critical. She is reluctant to admit she stopped her blood thinner.")
    c = out["case"]
    assert out["method"] == "offline" and out["template_id"] == "neuro" and c["status"] == "draft"
    assert c["profile"]["age"] == 72 and c["profile"]["gender"] == "female" and c["faculty_truth"]["severity"] > 0.67
    assert validate_case(c)["ok"]
    assert any(f["category"] == "concealed" and f.get("patient_answer_auto") for f in c["facts"])
    assert c["review"]["needs_faculty_review"] and out["notes"]


RUTH = "Ruth Adeyemi, 39, a baker, presents with low back pain for two weeks. She lifts kettlebells three times a week. She hides that she is taking her sister's oxycodone."


def _ruth_draft(**over):
    d = {"template_id": "musculoskeletal", "name": "Ruth Adeyemi", "age": 39, "gender": "female", "occupation": "baker", "severity": "mild",
         "personality": "Cheerful", "speech_style": "",
         "complaint": {"text": "low back pain", "duration": "two weeks", "source": "low back pain for two weeks"},
         "facts": [{"category": "social", "slug": "kettlebells", "statement": "Lifts kettlebells three times a week",
                    "patient_answer": "I lift kettlebells three times a week.", "topics": ["exercise"], "negative": False,
                    "source": "She lifts kettlebells three times a week"}],
         "concealed": [{"slug": "painkillers from sister", "statement": "Is taking her sister's oxycodone", "reveal_answer": "I've been taking my sister's oxycodone.",
                        "cover_answer": "Just the usual stuff.", "topics": ["drugs", "medications"], "source": "she is taking her sister's oxycodone"}]}
    d.update(over)
    return d


def test_from_description_online_uses_model_fields_and_stays_a_draft():
    fake = FakeAnthropic(extract=_ruth_draft())
    out = tpl.from_description(RUTH, AnthropicProvider(client=fake))
    c = out["case"]
    assert out["method"] == "anthropic" and out["fallback"] is False and c["status"] == "draft" and c["origin"]["condition_template"] == "musculoskeletal"
    assert c["profile"]["name"] == "Ruth Adeyemi" and c["profile"]["age"] == 39 and c["profile"]["personality"] == "Cheerful"
    f = {x["fact_id"]: x for x in c["facts"]}
    assert f["f.social.kettlebells"]["patient_answer"] == "I lift kettlebells three times a week." and f["f.social.kettlebells"]["drafted_by"] == "model"
    hid = f["f.concealed.painkillers_from_sister"]
    assert hid["disclosure"]["rule"] == "after_rapport" and hid["cover_answer"] == "Just the usual stuff."
    cc = next(x for x in c["facts"] if x["category"] == "chief_complaint")
    assert "low back pain" in cc["patient_answer"] and "two weeks" in cc["patient_answer"]
    assert validate_case(c)["ok"]
    assert "<description>" in fake.calls[0]["messages"][0]["content"]
    assert c["review"]["coverage"]["uncovered"] == []                       # the same coverage check as the offline path


def test_from_description_online_drops_what_the_description_does_not_support():
    """Anything the model invents is rejected item by item and listed; supported items survive."""
    invented = [
        {"category": "pmh", "slug": "diabetes", "statement": "Has type 2 diabetes", "patient_answer": "I have diabetes.", "topics": ["diabetes"],
         "negative": False, "source": "She has type 2 diabetes"},                                              # quote not in the text
        {"category": "social", "slug": "kettlebells5", "statement": "Lifts kettlebells five times a week", "patient_answer": "I lift kettlebells five times a week.",
         "topics": ["exercise"], "negative": False, "source": "She lifts kettlebells three times a week"},      # changed number
        {"category": "medications", "slug": "naproxen", "statement": "Lifts kettlebells and takes naproxen", "patient_answer": "I lift kettlebells and take naproxen.",
         "topics": ["medications"], "negative": False, "source": "She lifts kettlebells"},                       # invented medicine
    ]
    d = _ruth_draft()
    d["facts"] = d["facts"] + invented
    d["concealed"][0]["cover_answer"] = "Only two oxycodone a day."                                               # a cover that leaks and invents
    out = tpl.from_description(RUTH, AnthropicProvider(client=FakeAnthropic(extract=d)))
    c = out["case"]
    text = " ".join(str(x.get("statement")) + " " + str(x.get("patient_answer")) for x in c["facts"]).lower()
    assert out["method"] == "anthropic" and "diabetes" not in text and "naproxen" not in text and "five times" not in text
    assert len(out["model_rejected"]) == 3 and any("source quote" in r["reasons"][0] for r in out["model_rejected"])
    assert any("Dropped a model-proposed fact" in n for n in out["notes"])
    hid = next(x for x in c["facts"] if x["category"] == "concealed")
    assert "oxycodone" not in hid["cover_answer"] and "two" not in hid["cover_answer"].lower() and hid["cover_answer_auto"]
    assert validate_case(c)["ok"]


def test_from_description_online_falls_back_when_the_model_draft_covers_less():
    d = _ruth_draft(facts=[], concealed=[])                 # the model "forgot" the kettlebells and the oxycodone
    out = tpl.from_description(RUTH, AnthropicProvider(client=FakeAnthropic(extract=d)))
    assert out["method"] == "offline" and out["fallback"] is True and any("uncovered" in n for n in out["notes"])
    out = tpl.from_description(RUTH, AnthropicProvider(client=FakeAnthropic(extract={"facts": "nonsense"})))
    assert out["method"] == "offline" and out["fallback"] is True


def test_from_description_falls_back_when_model_fails():
    out = tpl.from_description("25 year old man with a twisted ankle", AnthropicProvider(client=FakeAnthropic(fail=True)))
    assert out["method"] == "offline" and out["fallback"] is True and out["template_id"] == "injury_trauma" and out["case"]["status"] == "draft"


def test_nothing_private_in_tracked_templates_or_cases():
    """Guard for the public repo: names from the organizers' pack must not appear in tracked content.
    The names are read from .private/ at test time (never written here); skipped when the pack is absent."""
    import csv
    private = REPO_ROOT / ".private"
    banned: set[str] = set()
    for p in private.glob("shp/**/faculty-provided-sample-patient-details.csv"):
        with open(p, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("patient-name") or "").strip()
                if name:
                    banned |= {name, name.split()[-1]}
                if (row.get("patient-uuid") or "").strip():
                    banned.add(row["patient-uuid"].strip())
    for p in private.glob("shp/**/*profiles/*.json"):
        try:
            name = (json.loads(p.read_text()).get("clinician_overview") or {}).get("name")
        except Exception:
            name = None
        if name:
            banned.add(name)
    if not banned:
        pytest.skip("organizers' pack not present")
    common = {"Lee", "Patel", "Nelson", "Greene", "Rivera", "Armstrong", "Sinclair", "Ramirez"}      # surnames too common to scan for alone
    banned -= common
    files = [p for ext in ("*.py", "*.json", "*.md", "*.yaml") for p in (REPO_ROOT / "encounter").rglob(ext)] + list(TEMPLATES_DIR.glob("*.yaml"))
    assert len(files) > 30
    for p in files:
        if p == Path(__file__):
            continue
        text = p.read_text(errors="ignore")
        for b in banned:
            assert b not in text, (str(p), b)
