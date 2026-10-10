"""Shared fixtures. Every test runs offline, with an empty private dir and its own data dir, unless it says otherwise."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from encounter import api, providers
from encounter.paths import SEED_CASES_DIR
from encounter.session import EncounterManager
from encounter.store import CaseStore

SEED_IDS = ["chest-pain-line-cook", "abdominal-pain-grad-student", "breathless-retired-driver"]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    data = tmp_path / "data"
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setenv("ENCOUNTER_DATA_DIR", str(data))
    monkeypatch.setenv("ENCOUNTER_PRIVATE_DIR", str(private))
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE",
              "BEDROCK_MODEL_ID", "ANTHROPIC_MODEL", "AWS_BEARER_TOKEN_BEDROCK", "AWS_REGION", "AWS_DEFAULT_REGION", "BEDROCK_FAST_MODEL_ID",
              "BEDROCK_FALLBACK_MODEL_IDS", "ANTHROPIC_FAST_MODEL", "ENCOUNTER_INTENT_COMBINE", "ENCOUNTER_WORDING_TIER",
              "ENCOUNTER_LLM_TURN_TIMEOUT_S", "ENCOUNTER_ALLOW_NETWORK_IN_TESTS", "ENCOUNTER_GRADER_TIER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "aws_credentials_resolve", lambda: False)
    providers.reset_provider(providers.OfflineProvider())
    api.configure(None, None)
    api.register_sim_lookup(None)
    yield
    providers.reset_provider(None)
    api.configure(None, None)
    api.register_sim_lookup(None)


@pytest.fixture
def store(tmp_path):
    return CaseStore(tmp_path / "data")


@pytest.fixture
def manager(tmp_path):
    return EncounterManager(tmp_path / "data", provider_fn=lambda: providers.OfflineProvider())


def seed_case(case_id: str) -> dict:
    return json.loads((SEED_CASES_DIR / f"{case_id}.v1.json").read_text())


@pytest.fixture
def chest():
    return seed_case("chest-pain-line-cook")


@pytest.fixture
def mini_case():
    """A small hand-built case exercising every disclosure rule."""
    return copy.deepcopy(MINI)


MINI = {
    "schema_version": 1, "case_id": "mini", "version": 1, "status": "published", "title": "Mini case",
    "origin": {"kind": "authored"}, "review": {"needs_faculty_review": True, "synthetic": True},
    "prebrief": "Take a history.", "profile": {"name": "Test Patient", "age": 50, "gender": "female"},
    "faculty_truth": {"diagnosis": "Zebra syndrome of the pancreas", "expected_disposition": "admit", "expected_orders": ["order:lipase"]},
    "facts": [
        {"fact_id": "f.chief_complaint.pain", "category": "chief_complaint", "statement": "Upper abdominal pain for two days", "patient_knows": True,
         "patient_answer": "My upper stomach has hurt for two days.", "topics": ["chief_complaint", "pain_abdomen"], "disclosure": {"rule": "volunteered"}, "critical": True},
        {"fact_id": "f.social.smoking", "category": "social", "statement": "Smokes five cigarettes a day", "patient_knows": True,
         "patient_answer": "About five cigarettes a day.", "topics": ["smoking"], "disclosure": {"rule": "if_asked"}, "polarity": "positive"},
        {"fact_id": "f.ros.fever", "category": "ros", "statement": "No fever", "patient_knows": True, "patient_answer": "No, no fever at all.",
         "topics": ["fever"], "disclosure": {"rule": "if_asked"}, "polarity": "negative"},
        {"fact_id": "f.concealed.mood", "category": "concealed", "statement": "Low mood since losing her job in March", "patient_knows": True,
         "patient_answer": "I've felt low ever since I lost my job in March.", "cover_answer": "I'm fine, really.", "topics": ["mood"],
         "disclosure": {"rule": "after_rapport", "rapport_needed": 2}, "critical": True},
        {"fact_id": "f.concealed.alcohol", "category": "concealed", "statement": "Drinks a bottle of gin every evening", "patient_knows": True,
         "patient_answer": "All right. A bottle of gin every evening.", "cover_answer": "Only a sherry at Christmas.", "topics": ["alcohol"],
         "disclosure": {"rule": "denied_until_confronted", "confront_with": ["art.labs"]}, "critical": True, "polarity": "positive"},
        {"fact_id": "f.vitals.heart_rate", "category": "vitals", "statement": "Heart rate 104 beats/min", "value": 104, "unit": "beats/min",
         "patient_knows": False, "topics": ["heart rate"], "disclosure": {"rule": "chart_initial"}},
        {"fact_id": "f.lab.lipase", "category": "lab", "statement": "Lipase 940 U/L", "value": 940, "unit": "U/L", "label": "Lipase", "patient_knows": False,
         "topics": ["lipase"], "disclosure": {"rule": "on_request", "request": "order:lipase"}, "critical": True},
        {"fact_id": "f.exam.abdomen", "category": "exam", "statement": "Epigastric tenderness with guarding", "patient_knows": False,
         "topics": ["abdominal exam"], "disclosure": {"rule": "on_request", "request": "exam:abdomen"}},
        {"fact_id": "f.imaging.ct", "category": "imaging", "statement": "CT: swollen pancreas", "patient_knows": False, "topics": ["ct"],
         "disclosure": {"rule": "on_request", "request": "order:ct_abdomen"}},
    ],
    "chart": {"sections": [{"section_id": "vitals", "title": "Vital signs", "release": "initial"}, {"section_id": "labs", "title": "Labs", "release": "on_request"}],
              "artifacts": [
                  {"artifact_id": "art.labs", "kind": "lab_report", "title": "Blood results", "section_id": "labs",
                   "release": {"rule": "on_request", "request": "order:lipase"},
                   "content": [{"test": "Lipase", "value": 940, "unit": "U/L", "ref_range": "0-160", "flag": "H", "fact_id": "f.lab.lipase"}],
                   "interpretation": "Marked elevation suggests pancreatitis secret interpretation", "linked_fact_ids": ["f.lab.lipase"]},
                  {"artifact_id": "art.ct", "kind": "ct", "title": "CT report", "section_id": "imaging",
                   "release": {"rule": "on_request", "request": "order:ct_abdomen", "delay_turns": 2}, "content": "Swollen pancreas.",
                   "linked_fact_ids": ["f.imaging.ct"]}]},
    "objectives": [
        {"objective_id": "obj.alcohol", "criterion": "Uncovers the true alcohol intake", "kind": "elicit_fact", "linked_fact_ids": ["f.concealed.alcohol"], "critical": True, "rubric_domain": "listening"},
        {"objective_id": "obj.lipase", "criterion": "Requests a lipase", "kind": "action", "linked_requests": ["order:lipase"], "rubric_domain": "reasoning"},
        {"objective_id": "obj.empathy", "criterion": "Shows empathy", "kind": "communication", "evidence_rule": "empathic statements", "rubric_domain": "rapport"},
        {"objective_id": "obj.structure", "criterion": "Structured interview", "kind": "sequencing", "evidence_rule": "intro, open, summary, close", "rubric_domain": "opening"},
        {"objective_id": "obj.dispo", "criterion": "Admits the patient", "kind": "reasoning", "linked_fact_ids": ["f.lab.lipase"], "evidence_rule": "admit", "rubric_domain": "reasoning"},
    ],
    "rubric_id": "default", "sources": [],
    "unknown_response": "I really couldn't say.",
}


class FakeAnthropic:
    """Stands in for anthropic.Anthropic(): records calls, answers by prompt type.

    intent / wording / grade / describe / verify set the reply for that kind of call; `verify` defaults to "grounded".
    A value may be a callable taking the call's keyword arguments. `fail` fails every call; `fail_on` is a set of call
    kinds ("intent", "wording", "verify", "grade", "describe") that fail while the others succeed."""

    def __init__(self, intent=None, wording=None, grade=None, fail=False, describe=None, verify=None, fail_on=(), extract=None):
        self.calls = []
        self.intent, self.wording, self.grade, self.fail, self.describe = intent, wording, grade, fail, describe
        self.verify, self.fail_on, self.extract = verify, set(fail_on), extract
        self.messages = SimpleNamespace(create=self._create)

    @staticmethod
    def kind(system: str) -> str:
        if "You label" in system:
            return "intent"
        if "You voice a patient" in system:
            return "wording"
        if "You check one line of dialogue" in system:
            return "verify"
        if "clinical-skills teacher" in system:
            return "grade"
        if "structured draft of a teaching patient" in system:
            return "extract"
        if "clinical teacher turn" in system:
            return "describe"
        return "other"

    def _reply(self, system: str) -> str:
        kw = self.calls[-1] if self.calls else {}
        kind = self.kind(system)
        if kind in self.fail_on:
            raise RuntimeError(f"simulated failure of the {kind} call")
        val = {"intent": self.intent, "wording": self.wording, "verify": self.verify, "grade": self.grade, "describe": self.describe,
               "extract": self.extract}.get(kind)
        if callable(val):
            val = val(kw or {})
        if kind == "intent":
            return json.dumps(val or {"fact_ids": [], "requests": [], "open_question": False})
        if kind == "wording":
            return val if isinstance(val, str) else ""
        if kind == "verify":
            return json.dumps(val or {"grounded": True, "unsupported_claims": [], "omitted": []})
        if kind == "grade":
            return json.dumps(val or {"objectives": [], "rubric": [], "strengths": [], "next_time": []})
        if kind in ("describe", "extract"):
            return json.dumps(val or {})
        return "{}"

    def kinds(self) -> list[str]:
        return [self.kind(c["system"] if isinstance(c.get("system"), str) else c["system"][0]["text"]) for c in self.calls]

    def _create(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("simulated network failure")
        return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self._reply(kw.get("system", "")))],
                               stop_reason="end_turn")


class FakeBedrock(FakeAnthropic):
    """Stands in for boto3.client('bedrock-runtime'). `refuse` is a set of model IDs the account may not invoke."""

    def __init__(self, *a, refuse=(), **kw):
        super().__init__(*a, **kw)
        self.refuse = set(refuse)

    def converse(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("simulated AccessDeniedException")
        if kw.get("modelId") in self.refuse:
            raise RuntimeError("AccessDeniedException: model access is denied for this account (private marketplace eligibility)")
        system = kw["system"][0]["text"]
        return {"output": {"message": {"role": "assistant", "content": [{"text": self._reply(system)}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 10}}
