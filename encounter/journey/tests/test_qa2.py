"""Regressions for the second QA pass (overnight/QA_REPORT_2.md): N3 (colleague identity), N5 (care plan and
record correctness), N6 (unsupported-statement checking and the colleague accepting non-answers)."""
import json
import re
from pathlib import Path

import pytest

from encounter import providers
from encounter.clinicians import BUILTIN, list_clinicians
from encounter.journey import claims
from encounter.journey import definition as defs
from encounter.journey import handoff as ho
from encounter.journey import stages as st
from encounter.journey.manager import FICTIONAL, ORGANIZER, ORGANIZER_FLAG, JourneyManager, pick_clinician
from encounter.paths import REPO_ROOT
from encounter.session import EncounterManager
from encounter.tests.conftest import seed_case

HF, CHEST = "breathless-retired-driver", "chest-pain-line-cook"
INVENTED = "Dr. Quillon Varnsworth-Testcase"            # stands in for an organizer profile; no such profile exists


@pytest.fixture
def jm(tmp_path):
    enc = EncounterManager(tmp_path / "data", provider_fn=lambda: providers.OfflineProvider())
    return JourneyManager(enc, tmp_path / "data", enc.provider)


def _fake_organizer_pack(tmp_path, monkeypatch):
    d = tmp_path / "pack" / "shp" / "sample" / "clinician-profiles"
    d.mkdir(parents=True)
    for i, role in enumerate(["Attending Physician, Cardiology", "Charge Nurse", "Clinical Pharmacist", "Resident"]):
        (d / f"organizer_{i}.json").write_text(json.dumps({"clinician_overview": {"name": f"{INVENTED} {i}", "full_title": f"{INVENTED} {i}, MD",
                                                                                    "role": role, "credentials": "MD"}}))
    monkeypatch.setenv("ENCOUNTER_PRIVATE_DIR", str(tmp_path / "pack"))
    assert list_clinicians()["source"] == "organizer_private"


def _to(jm, case_id, template, until, seed=9, q=1.0):
    jid = jm.start(seed_case(case_id), defs.get_definition(template), seed=seed)["journey_id"]
    jm.auto_until(jid, until=until, quality=q)
    return jid


def _everything(jm, jid, sids):
    return json.dumps([jm.view(jid), jm.care_plan(jid), jm.log(jid)] + [jm.stage_view(jid, s) for s in sids], ensure_ascii=False)


# ---------------------------------------------------------------- N3

@pytest.mark.parametrize("template", ["ed-to-ward", "heart-failure-admission"])
def test_n3_colleagues_are_the_invented_stand_ins_even_when_organizer_profiles_are_on_disk(jm, tmp_path, monkeypatch, template):
    _fake_organizer_pack(tmp_path, monkeypatch)
    monkeypatch.delenv(ORGANIZER_FLAG, raising=False)
    d = defs.get_definition(template)
    case = HF if template == "heart-failure-admission" else CHEST
    jid = _to(jm, case, template, "handoff")
    v = jm.start_stage(jid, "handoff", "human", learner="Nurse Test")
    col = v["handoff"]["colleague"]
    builtin_names = {c["name"] for c in BUILTIN}
    assert col["name"] in builtin_names and col["source"] == "builtin" and col["fictional"] is True and col["source_label"] == FICTIONAL
    jm.submit_sbar(jid, "handoff", {"situation": "The patient came in unwell.", "recommendation": "Please review."})
    for _ in range(8):
        if jm.stage_view(jid, "handoff")["handoff"]["phase"] != "questions":
            break
        jm.turn(jid, "handoff", "I don't know.")
    jm.finish(jid, "handoff")
    text = _everything(jm, jid, [s["stage_id"] for s in d["stages"]]) + json.dumps(jm.debrief(jid)) + json.dumps(jm._load(jid))
    assert "Varnsworth" not in text and "organizer_private" not in text and "organizer-0" not in text
    titles = [e.get("element_label") for e in jm.view(jid)["record"]["entries"] if e["kind"] == "handoff"]
    assert titles and all("Varnsworth" not in str(t) for t in titles)
    for s in jm.view(jid)["stages"]:
        for c in s["counterparts"]:
            if c["kind"] == "colleague":
                assert c["name"] in builtin_names and c["source_label"] == FICTIONAL
        assert s["played_by"] == "human" or s["player"] in builtin_names


def test_n3_organizer_profiles_are_opt_in_and_never_called_fictional(jm, tmp_path, monkeypatch):
    _fake_organizer_pack(tmp_path, monkeypatch)
    assert pick_clinician("attending", "helen-brandt")["name"] == "Dr. Helen Brandt"
    monkeypatch.setenv(ORGANIZER_FLAG, "1")
    c = pick_clinician("attending", "helen-brandt")
    assert "Varnsworth" in c["name"] and c["fictional"] is False and c["source_label"] == ORGANIZER
    jid = _to(jm, CHEST, "ed-to-ward", "handoff")
    v = jm.start_stage(jid, "handoff", "human")
    assert v["handoff"]["colleague"]["source_label"] == ORGANIZER and v["handoff"]["colleague"]["fictional"] is False
    cp = next(c for c in v["stage"]["counterparts"] if c["kind"] == "colleague")
    assert cp["source_label"] == ORGANIZER and cp["fictional"] is False
    # a journey saved with an organizer profile is recast with the stand-ins when it is loaded without the flag
    monkeypatch.delenv(ORGANIZER_FLAG)
    jm._cache.clear()
    after = _everything(jm, jid, ["triage", "handoff"])
    assert "Varnsworth" not in after and jm.stage_view(jid, "handoff")["handoff"]["colleague"]["source_label"] == FICTIONAL


def test_n3_no_organizer_clinician_name_is_in_a_tracked_journey_file():
    """Reads the real organizer pack when it is on this machine (skipped otherwise); prints nothing from it."""
    names = set()
    for p in (REPO_ROOT / ".private").glob("shp/**/*profiles/*.json"):
        try:
            ov = (json.loads(p.read_text()).get("clinician_overview") or {})
        except Exception:
            continue
        for n in (ov.get("name"), ov.get("full_title")):
            n = re.sub(r"^(dr\.?|prof\.?)\s+", "", str(n or "").split(",")[0].strip(), flags=re.I)
            if len(n) >= 5:
                names.add(n.lower())
                names.add(n.split()[-1].lower()) if len(n.split()[-1]) >= 6 else None
    if not names:
        pytest.skip("the organizer pack is not on this machine")
    builtin = " ".join(c["name"] for c in BUILTIN).lower()
    names = {n for n in names if n not in builtin}
    roots = [REPO_ROOT / "encounter" / "journey", REPO_ROOT / "encounter" / "journeys", REPO_ROOT / "web" / "app" / "journey",
             REPO_ROOT / "web" / "components" / "journey", REPO_ROOT / "web" / "lib" / "journey"]
    hits = []
    for root in roots:
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".json", ".ts", ".tsx", ".mjs", ".md") and "__pycache__" not in f.parts:
                low = f.read_text(errors="ignore").lower()
                hits += [f.name for n in names if re.search(rf"\b{re.escape(n)}\b", low)]
    assert not hits, f"an organizer clinician's name appears in: {sorted(set(hits))}"


# ---------------------------------------------------------------- N5

def _physician_stage(jm, note="Chest pain, cause not yet clear.", orders=("order:bmp", "order:cbc"), template="ed-to-ward", case=CHEST):
    jid = _to(jm, case, template, "clinician")
    v = jm.start_stage(jid, "clinician", "human", learner="Dr Test")
    results = {}
    avail = {r["request"] for r in v["encounter"]["available_requests"]}
    for o in orders:
        assert o in avail, f"{o} is not orderable at this stage: {sorted(avail)}"
        results[o] = jm.request(jid, "clinician", o)
    return jid, results, note


def test_n5_a_default_normal_result_is_a_result_not_result_not_back(jm):
    jid, results, note = _physician_stage(jm)
    defaulted = [o for o, r in results.items() if r["result"] == "default_normal"]
    assert defaulted, {o: r["result"] for o, r in results.items()}           # QA's BMP and CBC: the scenario defines neither
    out = jm.finish(jid, "clinician", {"note": note, "disposition": "admit"})
    entries = out["record"]["entries"]
    for o in defaulted:
        order = next(e for e in entries if e["kind"] == "order" and e.get("request") == o)
        assert order["order_status"] == "resulted" and order["default_normal"] is True
        art = next(e for e in entries if e["kind"] == "artifact" and e.get("request") == o)
        assert "default normal result, synthetic" in art["text"] and art["synthetic"] is True
    cp = jm.care_plan(jid)
    assert not [q for q in cp["open_questions"] if q["text"].startswith("Result not back")]
    for o in defaulted:
        row = next(r for r in cp["orders"] if r.get("request") == o)
        assert row["order_status"] == "resulted" and row["results"], row
    # and the handoff does not treat them as pending, so they cannot be "lost at handoff"
    jm.auto_until(jid, until="handoff", quality=1.0)
    j = jm._load(jid)
    hdef = next(s for s in j["definition"]["stages"] if s["stage_id"] == "handoff")
    pend = [i for i in ho.expected_items(j["record"], hdef) if i["kind"] == "pending_results"]
    assert not [i for i in pend if any(o.split(":")[1] in i["text"].lower() for o in defaulted)]


def test_n5_plan_rows_are_plan_entries_and_problems_are_problems(jm):
    jid, _, _ = _physician_stage(jm, orders=())
    jm.finish(jid, "clinician", {"note": "Chest pain, cause not yet clear.", "disposition": "admit"})
    jm.auto_until(jid, until="handoff", quality=1.0)
    jm.start_stage(jid, "handoff", "human", learner="Nurse Test")
    v = jm.submit_sbar(jid, "handoff", {"situation": "He came in with chest pain.", "recommendation": "Please review him on the ward."})
    for _ in range(8):
        if v["handoff"]["phase"] != "questions":
            break
        v = jm.turn(jid, "handoff", "I don't know.")
    jm.finish(jid, "handoff")
    cp = jm.care_plan(jid)
    assert all(r["kind"] in ("plan", "handoff") for r in cp["plan"])
    assert not [r for r in cp["plan"] + cp["other_actions"] if "don't know" in r["text"].lower() or r.get("in_reply_to")]
    assert [r for r in cp["plan"] if r["text"] == "Please review him on the ward."]          # the SBAR's Recommendation is a plan row
    assert cp["problems"] and all(r["kind"] == "fact" for r in cp["problems"])
    assert all(c["problem"]["kind"] == "fact" for c in cp["coordinated_plan"])
    note_texts = {r["text"] for r in cp["notes"]}
    assert note_texts and not note_texts & {r["text"] for r in cp["problems"]}
    prof = jm._load(jid)["case"]["profile"]
    assert not [r for r in cp["problems"] if re.fullmatch(rf"{prof['age']}-year-old \w+\.?", r["text"])]   # the demographic line
    assert any("not resolved" in q["text"] and "I don't know." in q["text"] for q in cp["open_questions"])


def test_n5_a_patient_statement_is_labelled_a_patient_statement(jm):
    f = {"category": "hpi"}
    assert st._source_for(f, "open_prompt", spoken=True) == "patient_statement"          # "Tell me more about that."
    assert st._source_for(f, "if_asked") == "patient_statement"
    assert st._source_for({"category": "exam"}, "on_request", spoken=True) == "measurement"   # "let me listen to your chest"
    assert st._source_for({"category": "lab"}, "on_request") == "chart_artifact"
    assert st._source_for(f, "chart_initial", spoken=True) == "chart_artifact"
    jid = jm.start(seed_case(CHEST), defs.get_definition("ed-to-ward"), seed=5)["journey_id"]
    jm.start_stage(jid, "triage", "human", learner="Nurse Test")
    for line in ["What brings you in today?", "Tell me more about that.", "Tell me more about that.", "Anything else?"]:
        v = jm.turn(jid, "triage", line)
    spoken = [e for e in v["record"]["entries"] if e["kind"] == "fact" and e.get("turn") and e.get("rule") not in ("on_request", "chart_initial")]
    assert spoken and all(e["source"] == "patient_statement" and e["source_label"] == "patient statement" for e in spoken), \
        [(e["rule"], e["source"]) for e in spoken]


def test_n5_recommendation_feedback_does_not_claim_the_colleague_drew_it_out(jm):
    jid = _to(jm, HF, "heart-failure-admission", "handoff")
    jm.start_stage(jid, "handoff", "human")
    disp = next(e for e in jm.view(jid)["record"]["entries"] if e["kind"] == "decision" and e.get("key") == "disposition")
    jm.submit_sbar(jid, "handoff", {"situation": f"Leonard Asante came in short of breath and we will {disp['value']} him."})
    out = jm.finish(jid, "handoff")                                              # the colleague's questions were never answered
    R = out["handoff"]["grading"]["elements"]["R"]
    assert any(c["kind"] == "disposition" and not c["prompted"] for c in R["conveyed"])
    assert "only when the colleague asked" not in R["feedback"] and "mentioned under Situation" in R["feedback"]
    obj = {o["objective_id"]: o for o in out["stage"]["objectives"]}["sbar.recommendation"]
    assert "only when the colleague asked" not in obj["feedback"]
    assert all(ev["location"] == "SBAR, Situation" for ev in obj["evidence"])     # quoted where it was actually said


# ---------------------------------------------------------------- N6

def _flagged(grading):
    return {u["quote"]: u["reason"] for el in grading["elements"].values() for u in el["unsupported"]}


def test_n6_qa_sbar_examples_are_all_flagged(jm):
    jid = _to(jm, CHEST, "ed-to-ward", "handoff")
    j = jm._load(jid)
    rtext = ho._record_text(j["record"], j["case"], "handoff").lower()
    assert "warfarin" not in rtext and not re.search(r"\bct\b", rtext) and "latex" not in rtext
    jm.start_stage(jid, "handoff", "human")
    jm.submit_sbar(jid, "handoff", {"situation": "He came in with chest pain.", "background": "He is allergic to latex and is on warfarin.",
                                    "assessment": "Troponin was 900 and the CT showed a large bleed.", "recommendation": "Please review him."})
    out = jm.finish(jid, "handoff")
    q = _flagged(out["handoff"]["grading"])
    assert "latex" in q["He is allergic to latex"]
    assert "warfarin" in q["is on warfarin."]
    assert "900" in q["Troponin was 900"]
    assert "CT" in q["the CT showed a large bleed."]
    assert out["handoff"]["grading"]["checked"] == claims.SCOPE_NOTE and "not checked" in claims.SCOPE_NOTE
    b = next(e for e in out["record"]["entries"] if e["kind"] == "handoff" and e.get("element") == "B")
    assert b["status"] == "unsupported" and b["flag"] == claims.FLAG


def test_n6_studio_example_medicines_are_flagged(jm):
    jid = _to(jm, HF, "heart-failure-admission", "handoff")
    j = jm._load(jid)
    rtext = ho._record_text(j["record"], j["case"], "handoff").lower()
    assert "omeprazole" not in rtext and "insulin" not in rtext
    jm.start_stage(jid, "handoff", "human")
    jm.submit_sbar(jid, "handoff", {"background": "She is allergic to latex and takes omeprazole and insulin."})
    q = _flagged(jm.finish(jid, "handoff")["handoff"]["grading"])
    assert any("omeprazole" in r for r in q.values()) and any("insulin" in r for r in q.values()) and any("latex" in r for r in q.values())


def test_n6_claim_rules_do_not_flag_what_the_record_holds_or_requests_or_hedged_reasoning():
    rt = ("Leonard 68 male. Chest pain for two hours. No known drug allergies. Takes lisinopril 10 mg. Ordered: Troponin. "
          "Troponin 12 normal. Hypertension for ten years. Chest X-ray: clear lung fields.")
    ok = [("A", "He has chest pain and hypertension."), ("A", "I think he has pneumonia."), ("R", "Please get a CT and start heparin."),
          ("A", "Troponin was normal."), ("B", "He takes lisinopril."), ("R", "Needs a CT head."), ("A", "The chest X-ray showed clear lung fields."),
          ("S", "He came in in April."), ("A", "The pain has been getting worse since this morning.")]
    for el, s in ok:
        assert [claims.claim_reason(c, el, rt, s) for c in ho.clauses(s)] == [None] * len(ho.clauses(s)), s
    bad = [("A", "Patient has a pacemaker and had a stroke last year.", 2), ("B", "She takes omeprazole and insulin.", 2),
           ("A", "The CT showed a large bleed.", 1), ("A", "ECG shows ST elevation.", 1), ("B", "History of diabetes.", 1),
           ("B", "Allergic to shellfish.", 1), ("A", "The chest X-ray showed a collapsed lobe.", 1), ("S", "He is on metoprolol.", 1)]
    for el, s, n in bad:
        assert len([1 for c in ho.clauses(s) if claims.claim_reason(c, el, rt, s)]) == n, s


def test_n6_an_unsupported_stage_note_is_flagged_and_never_promoted(jm):
    note = "Patient has a pacemaker and had a stroke last year."
    jid, _, _ = _physician_stage(jm, orders=("order:bmp",))
    out = jm.finish(jid, "clinician", {"note": note, "disposition": "admit", "plan": ["Follow up the stroke clinic letter"]})
    e = next(x for x in out["record"]["entries"] if x["kind"] == "note" and x["stage_id"] == "clinician")
    assert e["status"] == "unsupported" and e["flag"] == claims.FLAG == "unsupported — not in the shared record"
    assert {u["quote"] for u in e["unsupported"]} == {"Patient has a pacemaker", "had a stroke last year."}
    cp = jm.care_plan(jid)
    assert note not in [r["text"] for r in cp["problems"]] and note not in [c["problem"]["text"] for c in cp["coordinated_plan"]]
    assert note not in [x["text"] for c in cp["coordinated_plan"] for x in c["evidence"] + c["actions"]]
    row = next(r for r in cp["notes"] if r["text"] == note)
    assert row["flag"] == claims.FLAG and row["status"] == "unsupported"
    assert any("pacemaker" in q["text"] for q in cp["open_questions"])
    # the flagged note is not support for a later statement, and the receiver is not expected to be told it
    jm.auto_until(jid, until="handoff", quality=1.0)
    j = jm._load(jid)
    hdef = next(s for s in j["definition"]["stages"] if s["stage_id"] == "handoff")
    assert note not in [i["text"] for i in ho.expected_items(j["record"], hdef)]
    jm.start_stage(jid, "handoff", "human")
    jm.submit_sbar(jid, "handoff", {"background": "He has a pacemaker."})
    assert "He has a pacemaker." in _flagged(jm.finish(jid, "handoff")["handoff"]["grading"])


def test_n6_the_colleague_does_not_accept_a_non_answer(jm):
    jid = _to(jm, HF, "heart-failure-admission", "handoff")
    jm.start_stage(jid, "handoff", "human")
    v = jm.submit_sbar(jid, "handoff", {"situation": "Leonard Asante, 68, came in with worsening shortness of breath over two weeks.",
                                        "background": "He has heart failure, diagnosed three years ago after a heart attack.",
                                        "assessment": "The chest X-ray shows an enlarged heart with small pleural effusions."})
    h = v["handoff"]
    assert h["questions"][-1]["about"] == "allergies"
    v = jm.turn(jid, "handoff", "Please admit and monitor.")                      # QA: accepted as the answer to "any allergies?"
    h = v["handoff"]
    last = h["messages"][-1]
    assert last["reask"] is True and "does not answer" in last["text"] and "allergies" in last["text"]
    assert [q["about"] for q in h["questions"]] == ["allergies"] and h["questions"][0]["answered"] is False
    v = jm.turn(jid, "handoff", "I don't know.")
    h = v["handoff"]
    q0 = h["questions"][0]
    assert q0["answered"] is True and q0["unresolved"] is True and q0["attempts"] == 2
    assert "unresolved" in h["messages"][-1]["text"]
    for _ in range(8):                                                           # "I don't know." to everything else as well
        if v["handoff"]["phase"] != "questions":
            break
        v = jm.turn(jid, "handoff", "I don't know.")
    out = jm.finish(jid, "handoff")
    g = out["handoff"]["grading"]
    beh = {b["behavior"]: b for b in g["behaviors"]}
    assert beh["Uncertainty named"]["observed"] != "yes" and beh["Uncertainty named"]["quote"] is None
    assert not [c for c in g["elements"]["B"]["conveyed"] if c["kind"] == "allergies"]
    recs = out["record"]["entries"]
    assert not [e for e in recs if e["kind"] == "handoff" and e.get("in_reply_to")]          # no non-answer filed as an answer
    openq = [e for e in recs if e["kind"] == "question" and e["stage_id"] == "handoff"]
    assert any("not resolved" in e["text"] and "allergies" in e["text"] for e in openq)
    assert jm.debrief(jid)["team"]["summary"]["handoff_questions_unresolved"] >= 1


def test_n6_uncertainty_named_needs_something_named():
    assert not ho.names_uncertainty("I don't know.") and not ho.names_uncertainty("Not sure.") and not ho.names_uncertainty("Please admit and monitor.")
    assert ho.names_uncertainty("The troponin is still pending.") and ho.names_uncertainty("I am not sure whether he took his tablets.")


def test_n6_a_real_answer_is_accepted_first_time(jm):
    jid = _to(jm, HF, "heart-failure-admission", "handoff")
    jm.start_stage(jid, "handoff", "human")
    v = jm.submit_sbar(jid, "handoff", {"situation": "Leonard Asante, 68, came in with worsening shortness of breath over two weeks.",
                                        "background": "He has heart failure, diagnosed three years ago after a heart attack.",
                                        "assessment": "The chest X-ray shows an enlarged heart with small pleural effusions."})
    v = jm.turn(jid, "handoff", "No known drug allergies.")
    q0 = v["handoff"]["questions"][0]
    assert q0["answered"] is True and not q0["unresolved"] and q0["attempts"] == 1 and not v["handoff"]["messages"][-1]["reask"]


# ---------------------------------------------------------------- honesty line

def test_care_plan_says_where_sampled_entries_came_from(jm):
    jid = _to(jm, CHEST, "ed-to-ward", "handoff")
    cp = jm.care_plan(jid)
    assert "nothing here comes from the hidden case" not in cp["assembled_from"]
    assert "shared record only" in cp["assembled_from"] and "copy them from the case file" in cp["assembled_from"]
    assert cp["n_sampled_entries"] == len([e for e in jm.view(jid)["record"]["entries"] if e["by"]["actor"] == "sampled"]) > 0
    assert all(e.get("copied_from_case") for e in jm.view(jid)["record"]["entries"] if e["by"]["actor"] == "sampled")
    assert cp["unsupported_check"] == claims.SCOPE_NOTE
    for e in jm.view(jid)["record"]["entries"]:                                   # a sampled concealed fact shows that it was confronted
        if e["kind"] == "fact" and e.get("rule") == "denied_until_confronted":
            assert e.get("after_confrontation") is True
