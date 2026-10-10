import json

import pytest

from encounter import providers
from encounter.disclosure import Engine, new_state
from encounter.patient import grounding_check, respond
from encounter.providers import AnthropicProvider, BedrockProvider, OfflineProvider, ProviderError, extract_json, select_provider
from encounter.session import EncounterManager

from .conftest import FakeAnthropic, FakeBedrock


# ------------------------------------------------------------------ selection by credential only

def test_offline_when_no_credentials():
    assert isinstance(select_provider(), OfflineProvider)
    import encounter
    providers.reset_provider(None)
    assert encounter.status() == {"llm": {"live": False, "provider": "offline", "model": None}, "voice": {"live": False, "provider": "browser"}}


def test_anthropic_when_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    p = select_provider()
    assert isinstance(p, AnthropicProvider) and p.model == "claude-opus-5-5" and p.live
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    assert select_provider().model == "claude-haiku-5-5"


def test_bedrock_wins_when_aws_credentials_resolve(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(providers, "aws_credentials_resolve", lambda: True)
    p = select_provider()
    assert isinstance(p, BedrockProvider) and p.model == "us.amazon.nova-pro-v1:0" and p.region == "us-east-1"
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    p = select_provider()
    assert p.model == "us.amazon.nova-micro-v1:0" and p.region == "us-west-2"


def test_voice_status_follows_key(monkeypatch):
    assert providers.voice_status() == {"live": False, "provider": "browser"}
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert providers.voice_status() == {"live": True, "provider": "elevenlabs"}


def test_no_flag_or_setting_selects_a_provider():
    import inspect
    src = inspect.getsource(providers.select_provider)
    assert "LLM_PROVIDER" not in src and "OFFLINE" not in src


# ------------------------------------------------------------------ request shapes against faked clients

def test_bedrock_converse_request_shape_works_for_nova():
    fake = FakeBedrock(intent={"fact_ids": ["f.social.smoking"], "requests": [], "open_question": False})
    p = BedrockProvider(client=fake, model="us.amazon.nova-micro-v1:0")
    out = p.complete_json("You label things", "<message>do you smoke</message>", max_tokens=200, schema={"type": "object"})
    assert out["fact_ids"] == ["f.social.smoking"]
    call = fake.calls[0]
    assert call["modelId"] == "us.amazon.nova-micro-v1:0"
    assert call["messages"] == [{"role": "user", "content": [{"text": "<message>do you smoke</message>"}]}]
    assert call["inferenceConfig"] == {"maxTokens": 200} and "temperature" not in json.dumps(call)
    assert "JSON" in call["system"][0]["text"]


def test_anthropic_request_shape():
    fake = FakeAnthropic(intent={"fact_ids": [], "requests": [], "open_question": True})
    p = AnthropicProvider(client=fake)
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    assert p.complete_json("You label things", "hello", max_tokens=100, schema=schema)["open_question"] is True
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["system"] == "You label things"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": schema} and call["output_config"]["effort"] == "low"
    for banned in ("temperature", "top_p", "top_k", "thinking", "tool_choice"):
        assert banned not in call                                 # rejected or unnecessary on current Claude models
    assert call["messages"] == [{"role": "user", "content": "hello"}]


def test_extract_json_tolerates_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": {"b": "}"}} hope that helps') == {"a": {"b": "}"}}
    with pytest.raises(ProviderError):
        extract_json("no json here")


# ------------------------------------------------------------------ role-play flow online

def _play(case, provider):
    eng, st = Engine(case), new_state()
    eng.start(st)
    return eng, st, (lambda text: respond(case, eng, st, text, provider))


@pytest.mark.parametrize("cls,fake_cls", [(AnthropicProvider, FakeAnthropic), (BedrockProvider, FakeBedrock)])
def test_online_intent_then_engine_then_wording(mini_case, cls, fake_cls):
    fake = fake_cls(intent={"fact_ids": ["f.social.smoking", "f.not.a.fact"], "requests": [], "open_question": False},
                    wording="Yeah... about five cigarettes a day, I'd say.")
    eng, st, say = _play(mini_case, cls(client=fake))
    r = say("You a smoker at all?")
    assert r["event"]["disclosed_fact_ids"] == ["f.social.smoking"]                  # invented ID dropped, engine decided
    assert r["reply"] == "Yeah... about five cigarettes a day, I'd say." and r["wording"] == "model"
    assert r["provider"] == cls.name and r["fallback"] is False
    prompts = json.dumps(fake.calls)
    # the model never sees hidden values or the faculty truth
    for secret in ("bottle of gin", "lost my job", "Zebra syndrome", "940", "sherry", "secret interpretation"):
        assert secret not in prompts, secret
    assert "f.concealed.alcohol" in prompts                                           # IDs and topics only


def test_model_cannot_release_a_withheld_fact(mini_case):
    fake = FakeAnthropic(intent={"fact_ids": ["f.concealed.alcohol"], "requests": [], "open_question": False},
                         wording="Honestly? A bottle of gin every evening.")
    eng, st, say = _play(mini_case, AnthropicProvider(client=fake))
    r = say("Do you drink?")
    assert r["event"]["disclosed_fact_ids"] == []
    wording_call = [c for c in fake.calls if "You voice a patient" in c["system"]][0]
    assert "Only a sherry at Christmas." in wording_call["messages"][0]["content"] and "gin" not in wording_call["messages"][0]["content"]
    # the model's reply introduced content outside the approved lines -> rejected, authored wording used
    assert r["reply"] == "Only a sherry at Christmas." and r["wording"] == "authored"
    assert r["event"]["wording_rejected"]["reasons"]


@pytest.mark.parametrize("bad", [
    "About five cigarettes a day, and I've had chest pain since Tuesday.",        # invented symptom
    "About fifteen cigarettes a day.",                                             # changed number
    "About five a day. I also take metformin.",                                    # invented medicine
    "Five cigarettes a day, plus a bottle of gin every evening.",                  # leaks an undisclosed fact
])
def test_post_check_rejects_unsupported_clinical_content(mini_case, bad):
    ok, reasons = grounding_check(bad, ["About five cigarettes a day."], mini_case, {"f.social.smoking"})
    assert not ok and reasons


def test_post_check_accepts_faithful_rephrasing(mini_case):
    ok, reasons = grounding_check("Um, about five cigarettes a day, I guess.", ["About five cigarettes a day."], mini_case, {"f.social.smoking"})
    assert ok, reasons


def test_runtime_failure_falls_back_to_offline_and_reports_it(tmp_path, mini_case):
    prov = AnthropicProvider(client=FakeAnthropic(fail=True))
    m = EncounterManager(tmp_path / "data", provider_fn=lambda: prov)
    eid = m.start(mini_case)["encounter_id"]
    r = m.turn(eid, "Do you smoke?")
    assert r["reply"] == "About five cigarettes a day."                     # the user's action still succeeds
    assert r["fallback"] is True and r["provider"] == "offline"
    assert r["llm"]["provider"] == "anthropic" and "simulated network failure" in r["llm"]["last_error"]
    out = m.finish(eid, "admit")
    assert out["feedback"]["grader"] == "offline" and out["feedback"]["fallback"] is True


def test_bedrock_failure_falls_back(tmp_path, mini_case):
    prov = BedrockProvider(client=FakeBedrock(fail=True))
    m = EncounterManager(tmp_path / "data", provider_fn=lambda: prov)
    eid = m.start(mini_case)["encounter_id"]
    r = m.turn(eid, "What brings you in?")
    assert "upper stomach" in r["reply"] and r["fallback"] is True
    assert "AccessDenied" in prov.status()["last_error"]
    # after repeated failures the provider cools down instead of making every turn slow
    m.turn(eid, "Do you smoke?")
    n = len(prov._client.calls)
    m.turn(eid, "Any fever?")
    assert len(prov._client.calls) == n


def test_empty_model_reply_is_a_failure(mini_case):
    eng, st, say = _play(mini_case, AnthropicProvider(client=FakeAnthropic(intent={"fact_ids": ["f.ros.fever"], "requests": [], "open_question": False}, wording="")))
    r = say("fever?")
    assert r["reply"] == "No, no fever at all." and r["fallback"] is True


# ------------------------------------------------------------------ online grader

def test_llm_grader_quotes_are_verified(tmp_path, mini_case):
    grade = {
        "objectives": [
            {"objective_id": "obj.empathy", "result": "met", "evidence": [{"turn": 2, "quote": "That sounds really hard"}], "suggestion": "Keep naming the emotion."},
            {"objective_id": "obj.structure", "result": "met", "evidence": [{"turn": 1, "quote": "Hello, I am Doctor Fabricated"}], "suggestion": "x"},
            {"objective_id": "obj.alcohol", "result": "met", "evidence": [{"turn": 3, "quote": "Do you drink alcohol?"}], "suggestion": "x"},
        ],
        "rubric": [{"key": "rapport_empathy", "score": "4", "rationale": "Named the emotion.", "evidence": [{"turn": 9, "quote": "many people feel that way"}]},
                   {"key": "reasoning", "score": "4", "rationale": "Great.", "evidence": [{"turn": 1, "quote": "this quote does not exist anywhere"}]}],
        "strengths": ["Warm tone."], "next_time": ["Order the lipase."],
    }
    prov = AnthropicProvider(client=FakeAnthropic(grade=grade, wording=""))
    prov._client.fail = False
    m = EncounterManager(tmp_path / "data", provider_fn=lambda: OfflineProvider())
    eid = m.start(mini_case)["encounter_id"]
    for line in ["What brings you in?", "That sounds really hard, and many people feel that way.", "Do you drink alcohol?"]:
        m.turn(eid, line)
    m._provider_fn = lambda: prov
    fb = m.finish(eid, "admit", summary="Pancreatitis likely.")["feedback"]
    assert fb["grader"] == "llm"
    by = {o["objective_id"]: o for o in fb["objectives"]}
    assert by["obj.empathy"]["result"] == "met" and by["obj.empathy"]["evidence"] == [{"turn": 2, "quote": "That sounds really hard"}]
    assert "verified quotes" in by["obj.empathy"]["basis"]
    assert by["obj.structure"]["uncertain"] and "discarded" in by["obj.structure"]["basis"]            # fabricated quote -> offline value kept
    assert by["obj.alcohol"]["result"] == "partly_demonstrated"                                        # ledger decides elicit_fact, not the model
    doms = {d["key"]: d for d in fb["rubric"]["domains"]}
    assert doms["rapport_empathy"]["score"] == 4 and doms["rapport_empathy"]["evidence"] == [{"turn": 2, "quote": "many people feel that way"}]
    assert doms["reasoning"]["score"] != 4 or doms["reasoning"]["uncertain"]
    assert "discarded" in doms["reasoning"]["rationale"]
    assert fb["strengths"][0] == "Warm tone." and fb["next_time"][0] == "Order the lipase."
    grader_prompt = [c for c in prov._client.calls if "clinical-skills teacher" in c["system"]][0]
    assert "[turn 2] STUDENT: That sounds really hard" in grader_prompt["messages"][0]["content"]
