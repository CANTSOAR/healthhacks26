import copy

import pytest

from encounter.store import CaseError, to_first_person


def test_seed_cases_listed_and_read_only(store):
    rows = store.list("published")
    assert {"chest-pain-line-cook", "abdominal-pain-grad-student", "breathless-retired-driver"} <= {r["case_id"] for r in rows}
    assert all(r["seed"] for r in rows)


def test_lifecycle_draft_approved_published(store, mini_case):
    body = copy.deepcopy(mini_case)
    del body["case_id"]
    c = store.create(body)
    assert c["status"] == "draft" and c["version"] == 1
    cid = c["case_id"]
    with pytest.raises(CaseError) as e:
        store.publish(cid)                                   # draft cannot jump to published
    assert e.value.status == 409
    a = store.approve(cid, "Dr. Faculty")
    assert a["status"] == "approved" and a["review"]["reviewer"] == "Dr. Faculty" and a["review"]["reviewed_at"]
    p = store.publish(cid)
    assert p["status"] == "published" and p["version"] == 1
    with pytest.raises(CaseError):
        store.publish(cid)


def test_invalid_case_cannot_be_approved(store, mini_case):
    mini_case["objectives"][0]["linked_fact_ids"] = ["f.missing.fact"]
    c = store.create(mini_case)
    with pytest.raises(CaseError) as e:
        store.approve(c["case_id"])
    assert e.value.status == 422 and e.value.detail["errors"]


def test_published_is_immutable_and_edit_creates_new_draft_version(store, mini_case):
    cid = store.create(mini_case)["case_id"]
    store.approve(cid)
    store.publish(cid)
    v2 = store.update(cid, {"title": "Edited title"})
    assert v2["version"] == 2 and v2["status"] == "draft" and v2["title"] == "Edited title"
    assert "reviewer" not in v2["review"]
    v1 = store.get(cid, 1)
    assert v1["status"] == "published" and v1["title"] == "Mini case"                # untouched
    assert store.get(cid, status="published")["version"] == 1                         # students still get v1
    assert store.versions(cid) == [1, 2]
    with pytest.raises(CaseError) as e:
        store._write({**{k: v for k, v in v1.items() if not k.startswith("_")}, "title": "hack"})
    assert e.value.status == 409 and store.get(cid, 1)["title"] == "Mini case"
    # editing a draft stays in place; editing an approved version returns it to draft
    v2b = store.update(cid, {"prebrief": "x"})
    assert v2b["version"] == 2
    store.approve(cid)
    assert store.update(cid, {"prebrief": "y"})["status"] == "draft"


def test_editing_a_seed_case_creates_a_draft_in_the_data_dir(store):
    v2 = store.update("chest-pain-line-cook", {"title": "My variant"})
    assert v2["version"] == 2 and v2["status"] == "draft" and not v2["_seed"]
    assert store.get("chest-pain-line-cook", 1)["title"] != "My variant"
    assert (store.cases_dir / "chest-pain-line-cook.v2.json").is_file()


def test_partial_body_gets_defaults_and_auto_patient_answers(store):
    c = store.create({"title": "Quick", "profile": {"name": "Jo Park", "age": 30, "gender": "female"},
                      "facts": [{"category": "social", "label": "smoking", "statement": "Smokes ten cigarettes a day"},
                                {"fact_id": "f.vitals.hr", "category": "vitals", "statement": "Heart rate 80"}]})
    f = {x["fact_id"]: x for x in c["facts"]}
    assert f["f.social.smoking"]["patient_answer"] == "I smoke ten cigarettes a day." and f["f.social.smoking"]["patient_answer_auto"]
    assert f["f.social.smoking"]["disclosure"]["rule"] == "if_asked"
    assert f["f.vitals.hr"]["disclosure"]["rule"] == "chart_initial" and f["f.vitals.hr"]["patient_knows"] is False
    assert {s["section_id"] for s in c["chart"]["sections"]} >= {"social", "vitals"}
    assert c["rubric_id"] == "default" and c["status"] == "draft"


def test_to_first_person():
    assert to_first_person("Denies chest pain") == "I do not have chest pain."
    assert to_first_person("She lives alone") == "I live alone."
    assert to_first_person("Takes metformin twice daily") == "I take metformin twice daily."


def test_encounter_keeps_the_version_it_started_with(store, manager, mini_case):
    cid = store.create(mini_case)["case_id"]
    store.approve(cid)
    store.publish(cid)
    enc = manager.start(store.get(cid, status="published"))
    v2 = store.update(cid, {"facts": [dict(f, patient_answer="CHANGED") if f.get("patient_answer") else f for f in mini_case["facts"]]})
    store.approve(cid)
    store.publish(cid)
    r = manager.turn(enc["encounter_id"], "Do you smoke?")
    assert r["reply"] == "About five cigarettes a day."
    assert manager.get(enc["encounter_id"])["case"]["version"] == 1
    assert all(e["case_version"] == 1 for e in manager.get(enc["encounter_id"], "faculty")["ledger_full"])
    enc2 = manager.start(store.get(cid, status="published"))
    assert enc2["case"]["version"] == 2 and manager.turn(enc2["encounter_id"], "Do you smoke?")["reply"] == "CHANGED"
