from encounter.session import EncounterError

import pytest

PARAPHRASES = [
    ["Do you smoke?", "Are you a smoker?", "Do you use tobacco?", "how many cigarettes do you smoke"],
    ["Any allergies?", "Are you allergic to any medications?", "any drug allergies?"],
    ["What medications do you take?", "are you on any meds?", "do you take any pills regularly"],
    ["Do you use any drugs?", "any recreational drug use?", "have you taken cocaine?"],
]


def test_repeated_and_paraphrased_questions_give_consistent_answers(manager, chest):
    eid = manager.start(chest)["encounter_id"]
    for group in PARAPHRASES:
        replies = [manager.turn(eid, q)["reply"].replace("Like I said: ", "") for q in group]
        assert len(set(replies)) == 1, (group, replies)
    # asked again much later: same content, and the chart still holds one entry per fact
    assert manager.turn(eid, "remind me, do you smoke?")["reply"].replace("Like I said: ", "") == "About half a pack a day. I started when I was around twenty."
    chart = manager.get(eid)["chart"]
    ids = [f["fact_id"] for s in chart["sections"] for f in s["facts"]]
    assert len(ids) == len(set(ids))
    assert "f.concealed.cocaine_use" not in ids


def test_denial_is_consistent_until_confronted_then_truth_is_consistent(manager, chest):
    eid = manager.start(chest)["encounter_id"]
    cover = "No. I don't do drugs. Just the energy drinks."
    assert [manager.turn(eid, q)["reply"].replace("Like I said: ", "") for q in ("Do you use drugs?", "Any cocaine?", "Are you sure, no drugs at all?")] == [cover] * 3
    manager.request(eid, "order:tox_screen")
    r = manager.turn(eid, "Your urine drug screen shows cocaine. Did you use cocaine recently?")
    assert "f.concealed.cocaine_use" in [d["fact_id"] for d in r["disclosed"]]
    again = manager.turn(eid, "So you did use cocaine?")["reply"]
    assert "couple of lines" in again and cover not in again


def test_idempotent_retry_same_request_id(manager, chest):
    eid = manager.start(chest)["encounter_id"]
    a = manager.turn(eid, "Do you smoke?", "req-1")
    n = len(manager.get(eid, "faculty")["ledger_full"])
    b = manager.turn(eid, "Do you smoke?", "req-1")
    c = manager.turn(eid, "something else entirely", "req-1")            # same id: the stored response wins
    assert a == b == c
    assert len(manager.get(eid, "faculty")["ledger_full"]) == n and manager.get(eid)["turn"] == 1
    r1 = manager.request(eid, "order:troponin", "req-2")
    r2 = manager.request(eid, "order:troponin", "req-2")
    assert r1 == r2 and manager.get(eid)["turn"] == 2
    d = manager.turn(eid, "Do you smoke?", "req-3")
    assert d["turn"] == 3 and d["disclosed"] == []                       # a NEW request is a new event, but discloses nothing twice


def test_idempotency_survives_reload_from_disk(tmp_path, chest):
    from encounter.providers import OfflineProvider
    from encounter.session import EncounterManager
    m1 = EncounterManager(tmp_path / "data", provider_fn=lambda: OfflineProvider())
    eid = m1.start(chest)["encounter_id"]
    a = m1.turn(eid, "Do you smoke?", "r1")
    m2 = EncounterManager(tmp_path / "data", provider_fn=lambda: OfflineProvider())      # e.g. after a server restart
    assert m2.turn(eid, "Do you smoke?", "r1") == a
    assert m2.get(eid)["turn"] == 1


def test_sessions_are_isolated(manager, chest):
    e1 = manager.start(chest)["encounter_id"]
    e2 = manager.start(chest)["encounter_id"]
    manager.turn(e1, "Do you smoke?")
    assert manager.get(e2)["turn"] == 0
    assert "f.social.smoking" not in str(manager.get(e2)["chart"])


def test_finished_encounter_rejects_turns_and_finish_is_idempotent(manager, chest):
    eid = manager.start(chest)["encounter_id"]
    manager.turn(eid, "What brings you in?")
    f1 = manager.finish(eid, "admit")
    f2 = manager.finish(eid, "discharge")
    assert f2["already_finished"] and f2["interaction_result"] == f1["interaction_result"]
    with pytest.raises(EncounterError) as e:
        manager.turn(eid, "one more thing")
    assert e.value.status == 409


def test_draft_cannot_start_without_preview(manager, mini_case):
    mini_case["status"] = "draft"
    with pytest.raises(EncounterError) as e:
        manager.start(mini_case)
    assert e.value.status == 409
    assert manager.start(mini_case, preview=True)["preview"] is True
