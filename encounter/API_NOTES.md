# Encounter API notes (for the web and server agents)

Router: `encounter/api.py` exposes `router` (FastAPI `APIRouter`). Mount it under `/api`:

```python
from encounter.api import router as encounter_router, register_sim_lookup
app.include_router(encounter_router, prefix="/api")
register_sim_lookup(lambda run_id: (sim, b) if run_id in live_runs else None)   # enables POST /api/encounters {run_id, patient_id}

import encounter
encounter.status()   # -> {"llm": {live, provider, model, last_error?}, "voice": {live, provider}} for /api/status
```

Standalone for development: `.venv/bin/python -m uvicorn encounter.app:app --port 8010` (any free port).
Run-time data goes to `data/encounters/` (gitignored; override with `ENCOUNTER_DATA_DIR`).

Every example below is real output of the offline path, shortened (`"... N more"` marks cut lists, `...` cut strings).
All content is synthetic. There is no authentication: "faculty" and "student" are separate routes and views, not roles enforced by login.
Errors are `{"detail": {"message": "...", ...}}` with 404 (not found), 409 (wrong lifecycle state / finished encounter), 422 (bad input or a case that does not validate), 503 (no live simulation registered).

## What the pages need to know

**Patient Studio (faculty)**
- Three ways to create a draft, all `POST /api/cases`: a full or partial case body; `{"from_template": "<condition_group>", "overrides": {severity, seed, age, sex, ...any top-level case key}}`; `{"from_description": "free text"}`. All return a **draft** plus `validation` and `notes` to show the author.
- A partial body is completed for you: missing `fact_id` (from `category` + `label`/statement), `disclosure` (vitals: `chart_initial`; lab / imaging / exam: `on_request`; everything else: `if_asked`), `patient_knows`, `chart_section`, chart sections, and a first-person `patient_answer` drafted from the statement (flagged `patient_answer_auto: true`, shown as a warning to review).
- `topics` on a fact may be taxonomy keys (`smoking`, `alcohol`, `medications`, `allergies`, `onset`, `radiation`, `family_history`, `occupation`, `living_situation`, `mood`, `adherence`, ... see `encounter/taxonomy.py` `TOPICS`) and/or free trigger phrases. A fact named `f.social.smoking` works with no topics at all. No code is needed for a new case.
- Lifecycle: `draft -> approve -> publish`. Approve and publish return 422 with the validation report if the case has errors or contradictions. Any `PUT` returns the version to `draft`; a `PUT` on a published version creates version N+1 as a draft (`new_version_created: true`) and leaves the published one untouched.
- Preview a draft: `POST /api/encounters {"case_id": ..., "preview": true}`. Without `preview`, only a published version starts (409 otherwise).
- `GET /api/cases/{id}?view=faculty` is the only response that carries `faculty_truth`, cover answers, objectives and artifact interpretations. `GET /api/encounters/{id}?view=faculty` adds the full ledger (`ledger_full`) and the case snapshot.

**Encounter (student)**
- Start, then alternate `turn` (free text to the patient) and `request` (orders, examinations, artifacts). Send a fresh `request_id` per user action and reuse it on retry: the same ID always returns the same stored response and adds nothing to the ledger.
- Free text can also carry requests ("Can I get an ECG and a troponin?", "Let me listen to your chest"): the reply then has `notes` and newly `released_artifacts`.
- The right-hand chart is always `response.chart` (replace, do not merge): `sections[]` (only visible ones; `hidden_section_count` says how many are still locked) each with `facts[]`, `notes[]` (what the patient said while guarding something, `kind: "patient_reported"`, later `superseded: true`), `artifact_ids[]`; `artifacts[]` with `content` (lab rows `[{test, value, unit, ref_range, flag}]` or text); `pending_results[]` for delayed results.
- `disclosed[]` lists what THIS action released (animate these). `notes[]` are system lines for the transcript ("troponin: result added to the chart.").
- `available_requests[]` (in the start response and in `GET /encounters/{id}`) is the order / examination menu. It is a shared generic list merged with the case's own requests, so the menu does not give the case away; a request the case does not define returns `result: "not_available"`.
- `result` per action: `disclosed`, `answered` (the patient answered without releasing anything new), `repeat`, `patient_does_not_know`, `not_specified` (the case does not define it; the patient says its `unknown_response`), `no_fact_requested`, and for requests `released`, `pending`, `already_available`, `not_available`.
- `rapport` is an integer heuristic (see `encounter/disclosure.py`). Show it as a soft indicator at most; it is not a validated measure.
- `provider` is what actually answered this turn (`bedrock` | `anthropic` | `offline`); `fallback: true` means an online call failed and the offline path answered. `llm` repeats the provider status for the status indicator.
- Patient photo: `patient.image` is always a working URL (`/api/cases/{id}/image`): the real photo when the case names one under `.private/`, otherwise an SVG placeholder with initials.
- Voice: `POST /api/tts` returns `audio/mpeg` when `ELEVENLABS_API_KEY` is set, else **204**: on 204 use the browser's `speechSynthesis`. Send only the `reply` text.
- Finish: `POST .../finish` with `disposition` (`discharge|admit|transfer|undecided`), optional `orders` (strings; `"ct abdomen"`, `"order:cbc"` both work) and `summary`. The feedback is self-contained for the debrief page; `interaction_result` is the contract object written back to the simulator (`written_back` says whether a simulator took it).

---

## Faculty routes

### GET /api/cases?status=&all_versions=
Latest version per case (or every version with `all_versions=true`). Extra fields beyond the contract: `versions`, `seed`, `n_facts`, `n_objectives`, `needs_faculty_review`, `setting`, `learner_role`.
```json
[
  {
    "case_id": "abdominal-pain-grad-student",
    "version": 1,
    "status": "published",
    "title": "Lower abdominal pain in a 26-year-old graduate student",
    "origin": {
      "kind": "authored"
    },
    "profile": {
      "name": "Hannah Lindqvist",
      "age": 26,
      "gender": "female"
    },
    "updated": "2026-10-10T06:04:25+00:00",
    "versions": [
      1
    ],
    "seed": true,
    "n_facts": 28,
    "n_objectives": 7,
    "needs_faculty_review": true,
    "setting": "Emergency department treatment bay",
    "learner_role": "Emergency medicine resident"
  },
  "... 2 more"
]
```

### GET /api/cases/{case_id}?version=&view=faculty
The full case (`contracts/case.schema.json`) plus `versions`, `seed`, `updated`. `view=student` returns only `{case: <learner view>, patient, status}`.
```json
{
  "schema_version": 1,
  "case_id": "chest-pain-line-cook",
  "version": 1,
  "status": "published",
  "title": "Chest pressure in a 41-year-old line cook",
  "origin": {
    "kind": "authored"
  },
  "review": {
    "author": "HospitalGym overnight build (AI-drafted)",
    "needs_faculty_review": true,
    "synthetic": true
  },
  "intended_learner": "Medical students and first-year emergency medicine residents",
  "learner_role": "Emergency medicine resident",
  "setting": "Emergency department treatment bay",
  "rubric_id": "default",
  "unknown_response": "I'm not sure. I can't really tell you anything about that.",
  "prebrief": "You are the emergency medicine resident. Rafael Quintero, 41, walked in with chest pressure that started about two hours ago. Triage has taken vital signs. Take a focused history, request the examination and tests you ne...",
  "profile": {
    "name": "Rafael Quintero",
    "age": 41,
    "gender": "male",
    "race_ethnicity": "Hispanic/Latino",
    "background": "Line cook at a busy restaurant, works double shifts, lives with his partner and young daughter.",
    "personality": "Proud, guarded, minimises problems; warms up when treated with respect.",
    "speech_style": "Short, plain sentences. Deflects with 'I'm fine'."
  },
  "faculty_truth": {
    "diagnosis": "Cocaine-associated chest pain with possible non-ST-elevation myocardial infarction",
    "differential": [
      "Acute coronary syndrome",
      "Cocaine-induced coronary vasospasm",
      "Hypertensive urgency",
      "... 2 more"
    ],
    "teaching_points": [
      "Ask every chest pain patient about stimulant use, and ask again when the evidence does not fit the answer.",
      "A guarded patient is more likely to disclose after a non-judging explanation of why the question matters for treatment.",
      "A first troponin above the reference needs a repeat and observation, not discharge."
    ],
    "expected_disposition": "admit",
    "expected_orders": [
      "order:ecg",
      "order:troponin",
      "order:tox_screen"
    ],
    "severity": 0.7,
    "acuity": 2
  },
  "facts": [
    {
      "fact_id": "f.social.smoking",
      "category": "social",
      "statement": "Smokes about half a pack of cigarettes a day for 20 years (about 10 pack-years)",
      "patient_knows": true,
      "disclosure": {
        "rule": "if_asked"
      },
      "topics": [
        "smoking"
      ],
      "patient_answer": "About half a pack a day. I started when I was around twenty.",
      "critical": true,
      "polarity": "positive",
      "value": 10,
      "unit": "pack-years"
    },
    {
      "fact_id": "f.concealed.cocaine_use",
      "category": "concealed",
      "statement": "Used intranasal cocaine at about 1 am, roughly five hours before the pain began; uses it about twice a month to get through double shifts",
      "patient_knows": true,
      "disclosure": {
        "rule": "denied_until_confronted",
        "confront_with": [
          "art.tox_screen",
          "art.prior_ed_note"
        ]
      },
      "topics": [
        "drugs",
        "cocaine",
        "stimulants",
        "... 6 more"
      ],
      "patient_answer": "Okay. Yes. I did a couple of lines of coke around one this morning, to get through a double. I do it maybe twice a month. I didn't want it on my record, and I didn't want my partner finding out.",
      "critical": true,
      "polarity": "positive",
      "cover_answer": "No. I don't do drugs. Just the energy drinks.",
      "chart_section": "social"
    },
    {
      "fact_id": "f.lab.troponin",
      "category": "lab",
      "statement": "High-sensitivity troponin 31 ng/L at presentation (this laboratory's reference: below 14 ng/L)",
      "patient_knows": false,
      "disclosure": {
        "rule": "on_request",
        "request": "order:troponin"
      },
      "topics": [
        "troponin"
      ],
      "critical": true,
      "value": 31,
      "unit": "ng/L",
      "label": "Troponin",
      "chart_section": "labs"
    }
  ],
  "chart": {
    "sections": [
      {
        "section_id": "triage",
        "title": "Triage note",
        "release": "initial"
      },
      {
        "section_id": "vitals",
        "title": "Vital signs",
        "release": "initial"
      }
    ],
    "artifacts": [
      {
        "artifact_id": "art.tox_screen",
        "kind": "lab_report",
        "title": "Urine drug screen",
        "section_id": "labs",
        "release": {
          "rule": "on_request",
          "request": "order:tox_screen"
        },
        "synthetic": true,
        "content": [
          {
            "test": "Cocaine metabolite",
            "value": "detected",
            "unit": "",
            "ref_range": "not detected",
            "flag": "A",
            "fact_id": "f.lab.tox_cocaine"
          },
          {
            "test": "Amphetamines",
            "value": "not detected",
            "unit": "",
            "ref_range": "not detected",
            "flag": ""
          },
          {
            "test": "Opiates",
            "value": "not detected",
            "unit": "",
            "ref_range": "not detected",
            "flag": ""
          },
          "... 2 more"
        ],
        "interpretation": "Screening immunoassay consistent with recent cocaine exposure. A screen does not time the exposure or prove the cause of the chest pain.",
        "linked_fact_ids": [
          "f.lab.tox_cocaine"
        ],
        "source_ids": [
          "authored"
        ]
      }
    ]
  },
  "objectives": [
    {
      "objective_id": "obj.stimulant_use",
      "criterion": "Uncovers recent stimulant use despite the patient's initial denial",
      "kind": "elicit_fact",
      "linked_fact_ids": [
        "f.concealed.cocaine_use"
      ],
      "evidence_rule": "met when the patient discloses cocaine use; partly when the learner asks about drugs but accepts the denial",
      "critical": true,
      "rubric_domain": "listening",
      "feedback_met": "You noticed that the story and the evidence did not match, and raised it in a way that let him answer honestly.",
      "feedback_missed": "He denied drug use, but the previous visit note and the urine screen say otherwise. Request them, then raise what you found without judgement and explain why it changes treatment."
    }
  ],
  "sources": [
    {
      "source_id": "medlineplus_vitals",
      "title": "Vital signs (MedlinePlus Medical Encyclopedia)",
      "url": "https://medlineplus.gov/ency/article/002341.htm",
      "date": "fetched 2026-10-10",
      "role": "evidence_for_fact",
      "license": "US National Library of Medicine, public information",
      "supports": [
        "f.vitals.heart_rate",
        "f.vitals.blood_pressure",
        "f.vitals.other"
      ]
    }
  ],
  "updated": "2026-10-10T06:04:25+00:00",
  "versions": [
    1
  ],
  "seed": true
}
```

### POST /api/cases
Request (a partial case; note the second fact has no ID, rule or patient wording):
```json
{
  "title": "Dizzy spells in a 58-year-old teacher",
  "prebrief": "Take a history from Ms. Varga.",
  "profile": {
    "name": "Ilona Varga",
    "age": 58,
    "gender": "female"
  },
  "faculty_truth": {
    "diagnosis": "Orthostatic hypotension from a new tablet",
    "expected_disposition": "discharge"
  },
  "facts": [
    {
      "fact_id": "f.chief_complaint.dizziness",
      "category": "chief_complaint",
      "statement": "Light-headed on standing for five days",
      "patient_answer": "I get light-headed whenever I stand up.",
      "disclosure": {
        "rule": "volunteered"
      },
      "critical": true
    },
    {
      "category": "medications",
      "label": "current",
      "statement": "Takes ramipril; started doxazosin six days ago"
    },
    {
      "fact_id": "f.social.alcohol",
      "category": "social",
      "statement": "Half a bottle of wine most evenings",
      "patient_answer": "Half a bottle of wine most evenings.",
      "cover_answer": "Hardly anything.",
      "disclosure": {
        "rule": "after_rapport",
        "rapport_needed": 2
      }
    },
    {
      "fact_id": "f.vitals.postural_bp",
      "category": "vitals",
      "statement": "BP 138/84 lying, 104/62 standing",
      "disclosure": {
        "rule": "on_request",
        "request": "exam:vitals"
      }
    }
  ],
  "objectives": [
    {
      "criterion": "Measures lying and standing blood pressure",
      "kind": "action",
      "linked_requests": [
        "exam:vitals"
      ]
    }
  ]
}
```

Response `201` (the stored draft, plus `validation`, `notes`, `created_from`):
```json
{
  "title": "Dizzy spells in a 58-year-old teacher",
  "prebrief": "Take a history from Ms. Varga.",
  "profile": {
    "name": "Ilona Varga",
    "age": 58,
    "gender": "female"
  },
  "faculty_truth": {
    "diagnosis": "Orthostatic hypotension from a new tablet",
    "expected_disposition": "discharge"
  },
  "facts": [
    {
      "category": "medications",
      "label": "current",
      "statement": "Takes ramipril; started doxazosin six days ago",
      "fact_id": "f.medications.current",
      "disclosure": {
        "rule": "if_asked"
      },
      "patient_knows": true,
      "patient_answer": "I take ramipril; started doxazosin six days ago.",
      "patient_answer_auto": true,
      "chart_section": "medications"
    }
  ],
  "objectives": [
    {
      "criterion": "Measures lying and standing blood pressure",
      "kind": "action",
      "linked_requests": [
        "exam:vitals"
      ],
      "objective_id": "obj.measures_lying_and_standing_blood_pressu"
    }
  ],
  "schema_version": 1,
  "origin": {
    "kind": "authored"
  },
  "review": {
    "needs_faculty_review": true,
    "synthetic": true
  },
  "chart": {
    "sections": [
      {
        "section_id": "hpi",
        "title": "History of present illness",
        "release": "on_fact"
      }
    ],
    "artifacts": []
  },
  "rubric_id": "default",
  "sources": [],
  "unknown_response": "I'm not sure. I can't really tell you anything about that.",
  "case_id": "dizzy-spells-in-a-58-year-old-teacher-82c72e",
  "version": 1,
  "status": "draft",
  "updated": "2026-10-10T06:08:41+00:00",
  "validation": {
    "ok": true,
    "errors": [],
    "warnings": [
      {
        "path": "/facts/1/patient_answer",
        "message": "patient_answer was auto-drafted from the statement; review the wording"
      },
      {
        "path": "/facts/0",
        "message": "critical fact f.chief_complaint.dizziness is not linked to any objective"
      }
    ],
    "consistency": []
  },
  "notes": [],
  "created_from": {}
}
```

`{"from_template": "neuro", "overrides": {"severity": "severe", "seed": 4, "sex": "female", "age": 71}}` returns (fields shown: identity and review aids only):
```json
{
  "case_id": "draft-neuro-s4-severe",
  "version": 1,
  "status": "draft",
  "title": "Neurological symptoms in a 71-year-old woman",
  "origin": {
    "kind": "from_template",
    "condition_template": "neuro",
    "sim_seed": 4
  },
  "profile": {
    "name": "Farah Umarov",
    "age": 71,
    "gender": "female",
    "personality": "Friendly and cooperative, a little embarrassed to be here.",
    "speech_style": "Warm, conversational.",
    "background": "Office administrator at an insurance firm. Lives alone; a sibling lives nearby."
  },
  "validation": {
    "ok": true,
    "errors": [],
    "warnings": [
      {
        "path": "/facts/0",
        "message": "critical fact f.chief_complaint.neuro is not linked to any objective"
      },
      {
        "path": "/facts/19",
        "message": "critical fact f.lab.glucose is not linked to any objective"
      }
    ],
    "consistency": []
  },
  "notes": [
    "Draft generated from condition template 'neuro'. Review every fact before approval."
  ],
  "created_from": {
    "method": "template",
    "template_id": "neuro"
  }
}
```

`{"from_description": "Mr. Dale Horn, a 47-year-old man who works as a long-haul trucker, has had a fever and a bad cough for four days. He hides that he smokes two packs a day."}` returns:
```json
{
  "case_id": "draft-dale-horn-43ebee",
  "version": 1,
  "status": "draft",
  "title": "Shortness of breath in a 47-year-old man",
  "origin": {
    "kind": "from_template",
    "condition_template": "respiratory",
    "sim_seed": 3141790515
  },
  "profile": {
    "name": "Dale Horn",
    "age": 47,
    "gender": "male",
    "personality": "Friendly and cooperative, a little embarrassed to be here.",
    "speech_style": "Warm, conversational.",
    "background": "Works as a long-haul trucker."
  },
  "validation": {
    "ok": true,
    "errors": [],
    "warnings": [
      {
        "path": "/facts/22/patient_answer",
        "message": "patient_answer was auto-drafted from the statement; review the wording"
      },
      {
        "path": "/facts/0",
        "message": "critical fact f.chief_complaint.breathlessness is not linked to any objective"
      }
    ],
    "consistency": []
  },
  "notes": [
    "Closest condition template: 'respiratory' (severity band moderate). Clinical findings come from the template, not from the description; edit them to m...",
    "1 concealed item(s) were extracted from the description by pattern; the patient wording is auto-drafted and must be reviewed.",
    "... 1 more"
  ],
  "created_from": {
    "method": "offline",
    "fallback": false,
    "template_id": "respiratory"
  }
}
```

Offline, `from_description` picks the closest condition template by keyword, fills name / age / gender / occupation by pattern and turns "hides / denies / is embarrassed about ..." clauses into concealed facts. Online it asks the model for those fields. Either way the clinical findings come from the template and the result is a draft.

### PUT /api/cases/{case_id}
Body: any top-level case keys to replace (send the whole `facts` array to change facts). Response: the stored case plus `validation` and `new_version_created`:
```json
{
  "case_id": "dizzy-spells-in-a-58-year-old-teacher-82c72e",
  "version": 2,
  "status": "draft",
  "title": "Dizzy spells (revised)",
  "new_version_created": true,
  "validation": {
    "ok": true,
    "errors": [],
    "warnings": [
      {
        "path": "/facts/1/patient_answer",
        "message": "patient_answer was auto-drafted from the statement; review the wording"
      },
      "... 1 more"
    ],
    "consistency": []
  }
}
```

### POST /api/cases/{case_id}/validate
Optional `?version=`. With a JSON body of top-level keys it validates those unsaved edits merged over the stored case, without saving. A broken case:
```json
{
  "ok": false,
  "errors": [
    {
      "path": "/objectives/0/linked_fact_ids",
      "message": "linked fact 'f.missing' does not exist"
    }
  ],
  "warnings": [
    {
      "path": "/facts/1/patient_answer",
      "message": "patient_answer was auto-drafted from the statement; review the wording"
    },
    {
      "path": "/facts/0",
      "message": "critical fact f.chief_complaint.dizziness is not linked to any objective"
    }
  ],
  "consistency": []
}
```

A clean case:
```json
{
  "ok": true,
  "errors": [],
  "warnings": [
    {
      "path": "/facts/1/patient_answer",
      "message": "patient_answer was auto-drafted from the statement; review the wording"
    },
    {
      "path": "/facts/0",
      "message": "critical fact f.chief_complaint.dizziness is not linked to any objective"
    }
  ],
  "consistency": []
}
```

`consistency[]` items are `{level: "contradiction"|"warning", kind, message, paths}` with kinds `fact_polarity`, `fact_value`, `artifact_value`, `artifact_unit`, `allergy_vs_medication`, `allergy_polarity`, `age`, `polarity_vs_answer`. `ok` is false when there is any error or any `contradiction`.

### POST /api/cases/{case_id}/approve and /publish
`approve` takes an optional `{"reviewer": "name"}`:
```json
{
  "case_id": "dizzy-spells-in-a-58-year-old-teacher-82c72e",
  "version": 1,
  "status": "approved",
  "review": {
    "needs_faculty_review": true,
    "synthetic": true,
    "reviewer": "Prof. Example",
    "reviewed_at": "2026-10-10T06:08:42+00:00"
  },
  "updated": "2026-10-10T06:08:42+00:00"
}
```

`publish`:
```json
{
  "case_id": "dizzy-spells-in-a-58-year-old-teacher-82c72e",
  "version": 1,
  "status": "published",
  "updated": "2026-10-10T06:08:42+00:00"
}
```

When the case does not validate (422):
```json
{
  "detail": {
    "message": "case does not validate; fix errors and contradictions before approval",
    "ok": false,
    "errors": [
      {
        "path": "/objectives/0/linked_fact_ids",
        "message": "linked fact 'f.missing' does not exist"
      }
    ],
    "warnings": [
      {
        "path": "/facts/1/patient_answer",
        "message": "patient_answer was auto-drafted from the statement; review the wording"
      },
      "... 1 more"
    ],
    "consistency": []
  }
}
```

### GET /api/templates and /api/templates/{id}
```json
[
  {
    "id": "abdominal_pain",
    "condition_group": "abdominal_pain",
    "label": "Abdominal pain",
    "description": "Adult with abdominal pain, from gastroenteritis to appendicitis or acute pancreatitis.",
    "n_facts": 27,
    "n_objectives": 8,
    "typical_concealments": [
      "f.concealed.alcohol_intake"
    ],
    "synthetic": true,
    "needs_faculty_review": true,
    "bands": [
      "mild",
      "... 2 more"
    ]
  },
  "... 8 more"
]
```

One template (the YAML as JSON; two facts shown, one `choice` and one `numeric`):
```json
{
  "id": "chest_pain",
  "condition_group": "chest_pain",
  "label": "Chest pain",
  "synthetic": true,
  "needs_faculty_review": true,
  "complaint_label": "chest pain",
  "typical_concealments": [
    "f.concealed.stimulant_use"
  ],
  "facts": [
    {
      "fact_id": "f.hpi.radiation",
      "category": "hpi",
      "topics": [
        "radiation"
      ],
      "patient_knows": true,
      "disclosure": {
        "rule": "if_asked"
      },
      "critical": true,
      "discoverable_by": [
        "clinician_encounter"
      ],
      "kind": "choice",
      "options": {
        "mild": [
          {
            "statement": "No radiation",
            "patient_answer": "No, it stays in that one spot.",
            "polarity": "negative"
          }
        ],
        "moderate": [
          {
            "statement": "Sometimes spreads to the left arm",
            "patient_answer": "Sometimes I feel it in my left arm.",
            "polarity": "positive"
          }
        ],
        "severe": [
          {
            "statement": "Radiates to the left arm and jaw",
            "patient_answer": "It goes down my left arm, and my jaw aches.",
            "polarity": "positive"
          }
        ]
      },
      "chart_section": "hpi",
      "by_severity": {
        "mild": {
          "options": [
            "No radiation"
          ]
        },
        "moderate": {
          "options": [
            "Sometimes spreads to the left arm"
          ]
        },
        "severe": {
          "options": [
            "Radiates to the left arm and jaw"
          ]
        }
      }
    },
    {
      "fact_id": "f.lab.troponin",
      "category": "lab",
      "topics": [
        "troponin"
      ],
      "patient_knows": false,
      "disclosure": {
        "rule": "on_request",
        "request": "order:troponin"
      },
      "critical": true,
      "discoverable_by": [
        "lab_test",
        "clinician_encounter"
      ],
      "kind": "numeric",
      "label": "Troponin (high-sensitivity)",
      "unit": "ng/L",
      "ranges": {
        "mild": [
          3,
          9
        ],
        "moderate": [
          8,
          22
        ],
        "severe": [
          60,
          900
        ]
      },
      "decimals": 0,
      "statement": "High-sensitivity troponin {value} ng/L",
      "ref_high": 14,
      "ref_range": "below 14 (assay-specific; authored for this synthetic lab)",
      "source_ids": [
        "medlineplus_troponin"
      ],
      "chart_section": "labs",
      "by_severity": {
        "mild": {
          "range": [
            3,
            9
          ]
        },
        "moderate": {
          "range": [
            8,
            22
          ]
        },
        "severe": {
          "range": [
            60,
            900
          ]
        }
      }
    }
  ],
  "diagnoses": [
    {
      "band": "mild",
      "diagnosis": "Musculoskeletal chest wall pain",
      "expected_disposition": "discharge",
      "expected_orders": [
        "order:ecg",
        "exam:cardiac"
      ],
      "differential": [
        "Chest wall strain",
        "Pleurisy",
        "Acute coronary syndrome"
      ],
      "label": "Musculoskeletal chest wall pain"
    }
  ],
  "sources": [
    {
      "source_id": "medlineplus_vitals",
      "title": "Vital signs (MedlinePlus Medical Encyclopedia)",
      "url": "https://medlineplus.gov/ency/article/002341.htm",
      "date": "fetched 2026-10-10",
      "role": "evidence_for_fact",
      "license": "public information (US government health site)"
    }
  ]
}
```

### GET /api/rubrics and /api/rubrics/{id}
`default` resolves to the organizers' rubric when `.private/` has it (then the list also shows `organizer_encounter`), otherwise to the built-in one.
```json
[
  {
    "rubric_id": "builtin_encounter_v1",
    "title": "HospitalGym formative encounter rubric (built-in)",
    "source": "builtin",
    "is_default": true,
    "n_domains": 7,
    "domains": [
      {
        "key": "opening",
        "name": "Starting the encounter"
      },
      {
        "key": "rapport_empathy",
        "name": "Rapport and empathy"
      },
      "... 5 more"
    ]
  }
]
```

```json
{
  "rubric_id": "builtin_encounter_v1",
  "title": "HospitalGym formative encounter rubric (built-in)",
  "synthetic": true,
  "needs_faculty_review": true,
  "note": "Authored for this project as a stand-in with the same shape as the organizers' rubric (four-point scale, named domains, ...",
  "instructions": "Score only what the transcript and ledger show. Give N/A when the encounter offered no chance to demonstrate a domain.",
  "rating_scale": [
    {
      "score": 4,
      "label": "Well demonstrated",
      "meaning": "Reliable and well judged throughout"
    },
    "... 3 more"
  ],
  "allowed_scores": [
    4,
    "... 4 more"
  ],
  "domains": [
    {
      "id": 1,
      "key": "opening",
      "name": "Starting the encounter",
      "triggers_review_if_score_1": false,
      "descriptors": {
        "4": "Gives name and role, says what the conversation is for, asks permission, and lets the patient state the problem in their...",
        "3": "Clear start with a sensible focus; one element (role, purpose or permission) is thin.",
        "2": "Gets going, but the patient is not told who is asking or why, or is not invited to tell the story.",
        "1": "Starts cold with closed questions, or leaves the patient unsure what is happening."
      }
    },
    "... 6 more"
  ],
  "scoring": {
    "max_total": 28,
    "interpretation": "The total is a conversation starter for a debrief, not a grade. A 1 in clinical reasoning or in professional conduct sho...",
    "review_trigger_domain_ids": [
      6,
      "... 1 more"
    ]
  },
  "evidence_fields": [
    "strength",
    "... 2 more"
  ],
  "source": "builtin",
  "is_default": true,
  "requested_id": "default"
}
```

### GET /api/clinicians
From `.private/` when present (then each item also has the full `profile`), otherwise these built-in fictional stand-ins:
```json
{
  "source": "builtin",
  "fictional": true,
  "clinicians": [
    {
      "id": "amelia-okafor",
      "name": "Dr. Amelia Okafor",
      "credentials": "MD",
      "role": "Emergency Medicine Attending",
      "staff_role": "attending",
      "specialty": "Emergency Medicine",
      "years_in_role": 12,
      "communication_style": "Calm and direct. Asks residents for a one-line summary and a plan before giving her own.",
      "scope": "Supervises the department, resuscitations, final disposition decisions.",
      "source": "builtin"
    },
    "... 4 more"
  ]
}
```

### GET /api/cases/{case_id}/image
Binary image (PNG/JPEG) or `image/svg+xml` placeholder (header `X-Placeholder: 1`). 404 only when the case does not exist.

---

## Student routes

### POST /api/encounters
Body `{"case_id": "...", "version"?: 1, "preview"?: false, "learner"?: "name"}` or `{"run_id": "...", "patient_id": 123, "force"?: false}`. Response `201`:
```json
{
  "encounter_id": "enc-137be581a818",
  "case": {
    "case_id": "chest-pain-line-cook",
    "version": 1,
    "title": "Chest pressure in a 41-year-old line cook",
    "setting": "Emergency department treatment bay",
    "learner_role": "Emergency medicine resident",
    "intended_learner": "Medical students and first-year emergency medicine residents",
    "prebrief": "You are the emergency medicine resident. Rafael Quintero, 41, walked in with chest pressure that started about two hours ago. Triage has taken vital signs. Take a focused history, request the examinat...",
    "n_objectives": 8,
    "rubric": {
      "rubric_id": "builtin_encounter_v1",
      "title": "HospitalGym formative encounter rubric (built-in)",
      "domains": [
        {
          "key": "opening",
          "name": "Starting the encounter"
        },
        {
          "key": "rapport_empathy",
          "name": "Rapport and empathy"
        },
        "... 5 more"
      ]
    },
    "synthetic": true,
    "needs_faculty_review": true
  },
  "chart": {
    "sections": [
      {
        "section_id": "triage",
        "title": "Triage note",
        "release": "initial",
        "static_text": null,
        "facts": [],
        "notes": [],
        "artifact_ids": [
          "art.triage_note"
        ],
        "visible": true
      },
      {
        "section_id": "vitals",
        "title": "Vital signs",
        "release": "initial",
        "static_text": null,
        "facts": [
          {
            "fact_id": "f.vitals.heart_rate",
            "text": "Heart rate 112 beats/min",
            "category": "vitals",
            "turn": 0,
            "source": "chart",
            "rule": "chart_initial",
            "polarity": null,
            "label": "Heart rate",
            "value": 112,
            "unit": "beats/min"
          },
          {
            "fact_id": "f.vitals.blood_pressure",
            "text": "Blood pressure 168/102 mmHg",
            "category": "vitals",
            "turn": 0,
            "source": "chart",
            "rule": "chart_initial",
            "polarity": null,
            "label": "Blood pressure",
            "value": "168/102",
            "unit": "mmHg"
          },
          "... 1 more"
        ],
        "notes": [],
        "artifact_ids": [],
        "visible": true
      }
    ],
    "artifacts": [
      {
        "artifact_id": "art.triage_note",
        "kind": "document",
        "title": "Triage note",
        "content": "41-year-old man, walked in. Central chest pressure for about 2 hours, sweaty and restless at triage. Says he has 'no medical problems'. Pain 4/10 now. ESI 2. ECG requested per chest pain pathway (not ...",
        "synthetic": true,
        "section_id": "triage",
        "turn": 0,
        "linked_fact_ids": []
      }
    ],
    "hidden_section_count": 11,
    "pending_results": [],
    "n_disclosed": 3,
    "turn": 0
  },
  "patient": {
    "name": "Rafael Quintero",
    "age": 41,
    "gender": "male",
    "image": "/api/cases/chest-pain-line-cook/image"
  },
  "llm": {
    "provider": "offline",
    "live": false,
    "model": null
  },
  "available_requests": [
    {
      "request": "exam:abdomen",
      "kind": "exam",
      "label": "Abdomen"
    },
    {
      "request": "exam:cardiac",
      "kind": "exam",
      "label": "Cardiac"
    },
    "... 42 more"
  ],
  "rapport": 0,
  "status": "active",
  "preview": false,
  "opening_line": null,
  "sim": null
}
```

With `run_id`/`patient_id` the response also has `sim: {run_id, b, patient_id, held, t_start}` and `held`. 404 if the run is not live, 409 if the simulator says the patient cannot be played now, 503 if no simulator is registered.

### POST /api/encounters/{id}/turn
Body `{"text": "...", "request_id": "..."}`:
```json
{
  "encounter_id": "enc-137be581a818",
  "turn": 1,
  "request_id": "c1",
  "reply": "I've got this pressure in the middle of my chest. It started a couple of hours ago and it scared me enough to come in.",
  "notes": [],
  "disclosed": [
    {
      "fact_id": "f.chief_complaint.chest_pain",
      "chart_section": "hpi",
      "text": "Central chest pressure that began about two hours before arrival",
      "category": "chief_complaint",
      "rule": "volunteered"
    }
  ],
  "released_artifacts": [],
  "chart": {
    "sections": [
      {
        "section_id": "triage",
        "title": "Triage note",
        "release": "initial",
        "static_text": null,
        "facts": [],
        "notes": [],
        "artifact_ids": [
          "art.triage_note"
        ],
        "visible": true
      },
      "... 2 more"
    ],
    "artifacts": [
      {
        "artifact_id": "art.triage_note",
        "kind": "document",
        "title": "Triage note",
        "content": "41-year-old man, walked in. Central chest pressure for about 2 hours, sweaty and restless at triage. Says he has 'no medical problems'. Pain 4/10 now. ESI 2. EC...",
        "synthetic": true,
        "section_id": "triage",
        "turn": 0,
        "linked_fact_ids": []
      }
    ],
    "hidden_section_count": 10,
    "pending_results": [],
    "n_disclosed": 4,
    "turn": 1
  },
  "ledger_tail": [
    {
      "seq": 0,
      "time": "2026-10-10T06:08:42.922+00:00",
      "turn": 0,
      "actor": "system",
      "kind": "start",
      "text": null,
      "request": null,
      "request_id": null,
      "case_version": 1,
      "matched_intents": [],
      "disclosed_fact_ids": [
        "f.vitals.heart_rate",
        "... 2 more"
      ],
      "released_artifact_ids": [
        "art.triage_note"
      ],
      "rule_fired": {
        "f.vitals.heart_rate": "chart_initial",
        "f.vitals.blood_pressure": "chart_initial",
        "f.vitals.other": "chart_initial"
      },
      "result": "started",
      "rapport": 0,
      "rapport_delta": 0,
      "rapport_reasons": [],
      "reply": null,
      "provider": null,
      "fallback": false
    },
    "... 1 more"
  ],
  "rapport": 2,
  "result": "disclosed",
  "provider": "offline",
  "fallback": false,
  "llm": {
    "live": false,
    "provider": "offline",
    "model": null
  }
}
```

A guarded answer (the patient gives the authored cover answer; nothing is released, and the response does not say that something was withheld):
```json
{
  "reply": "No. I don't do drugs. Just the energy drinks.",
  "disclosed": [],
  "result": "answered",
  "rapport": 2,
  "provider": "offline",
  "fallback": false
}
```

The chart then carries it as a patient-reported note:
```json
{
  "section_id": "social",
  "title": "Social history",
  "release": "on_fact",
  "static_text": null,
  "facts": [],
  "notes": [
    {
      "note_id": "n2-0",
      "text": "No. I don't do drugs. Just the energy drinks.",
      "turn": 2,
      "kind": "patient_reported",
      "superseded": false
    }
  ],
  "artifact_ids": [],
  "visible": true
}
```

### POST /api/encounters/{id}/request
Body `{"request": "order:tox_screen" | "exam:abdomen" | "artifact:<id>", "request_id": "..."}`. Loose spellings are normalised (`"Order: Trop"` -> `order:troponin`). `reply` is null (the patient does not speak):
```json
{
  "reply": null,
  "notes": [
    "tox screen: result added to the chart.",
    "New in the chart: Urine drug screen."
  ],
  "request": "order:tox_screen",
  "result": "released",
  "disclosed": [
    {
      "fact_id": "f.lab.tox_cocaine",
      "chart_section": "labs",
      "text": "Urine drug screen: cocaine metabolite detected",
      "category": "lab",
      "rule": "on_request"
    }
  ],
  "released_artifacts": [
    {
      "artifact_id": "art.tox_screen",
      "kind": "lab_report",
      "title": "Urine drug screen",
      "section_id": "labs"
    }
  ],
  "rapport": 2,
  "provider": "offline",
  "fallback": false
}
```

The released artifact inside `chart.artifacts` (`interpretation` is held back until feedback):
```json
{
  "artifact_id": "art.tox_screen",
  "kind": "lab_report",
  "title": "Urine drug screen",
  "content": [
    {
      "test": "Cocaine metabolite",
      "value": "detected",
      "unit": "",
      "ref_range": "not detected",
      "flag": "A",
      "fact_id": "f.lab.tox_cocaine"
    },
    {
      "test": "Amphetamines",
      "value": "not detected",
      "unit": "",
      "ref_range": "not detected",
      "flag": ""
    },
    "... 3 more"
  ],
  "synthetic": true,
  "section_id": "labs",
  "turn": 3,
  "linked_fact_ids": [
    "f.lab.tox_cocaine"
  ]
}
```

A test the case does not define:
```json
{
  "notes": [
    "mri: not available in this case (no result is defined)."
  ],
  "disclosed": [],
  "result": "not_available",
  "request": "order:mri"
}
```

### GET /api/encounters/{id}?view=student
```json
{
  "encounter_id": "enc-137be581a818",
  "status": "active",
  "started": "2026-10-10T06:08:42+00:00",
  "finished": null,
  "turn": 5,
  "rapport": 2,
  "transcript": [
    {
      "turn": 1,
      "speaker": "student",
      "text": "Hi, I'm Dr. Shah, one of the residents. What brings you in today?"
    },
    {
      "turn": 1,
      "speaker": "patient",
      "text": "I've got this pressure in the middle of my chest. It started a couple of hours ago and it scared me enough to come in."
    },
    "... 6 more"
  ],
  "ledger": [
    {
      "seq": 0,
      "time": "2026-10-10T06:08:42.922+00:00",
      "turn": 0,
      "actor": "system",
      "kind": "start",
      "text": null,
      "request": null,
      "request_id": null,
      "case_version": 1,
      "matched_intents": [],
      "disclosed_fact_ids": [
        "f.vitals.heart_rate",
        "f.vitals.blood_pressure",
        "... 1 more"
      ],
      "released_artifact_ids": [
        "art.triage_note"
      ],
      "rule_fired": {
        "f.vitals.heart_rate": "chart_initial",
        "f.vitals.blood_pressure": "chart_initial",
        "f.vitals.other": "chart_initial"
      },
      "result": "started",
      "rapport": 0,
      "rapport_delta": 0,
      "rapport_reasons": [],
      "reply": null,
      "provider": null,
      "fallback": false
    },
    {
      "seq": 1,
      "time": "2026-10-10T06:08:42.944+00:00",
      "turn": 1,
      "actor": "learner",
      "kind": "turn",
      "text": "Hi, I'm Dr. Shah, one of the residents. What brings you in today?",
      "request": null,
      "request_id": "c1",
      "case_version": 1,
      "matched_intents": [
        "f.chief_complaint.chest_pain"
      ],
      "disclosed_fact_ids": [
        "f.chief_complaint.chest_pain"
      ],
      "released_artifact_ids": [],
      "rule_fired": {
        "f.chief_complaint.chest_pain": "volunteered"
      },
      "result": "disclosed",
      "rapport": 2,
      "rapport_delta": 2,
      "rapport_reasons": [
        "introduction",
        "open_question"
      ],
      "reply": "I've got this pressure in the middle of my chest. It started a couple of hours ago and it scared me enough to come in.",
      "provider": "offline",
      "fallback": false
    },
    "... 4 more"
  ],
  "preview": false,
  "sim": null,
  "feedback": null,
  "interaction_result": null,
  "written_back": false,
  "llm": {
    "live": false,
    "provider": "offline",
    "model": null
  }
}
```

### POST /api/encounters/{id}/finish
Body `{"disposition": "admit", "orders": ["ecg", "troponin"], "summary": "..."}` (all optional). Calling it twice returns the stored result with `already_finished: true`.
```json
{
  "encounter_id": "enc-137be581a818",
  "feedback": {
    "grader": "offline",
    "fallback": false,
    "quality": 0.449,
    "quality_parts": {
      "critical_fraction": 0.222,
      "objective_score": 0.458,
      "decision_score": 1.0,
      "formula": "0.5*critical_fraction + 0.3*objective_score + 0.2*decision_score"
    },
    "strengths": [
      "Uncovers recent stimulant use despite the patient's initial denial (objective met)",
      "Requests an ECG and a troponin (objective met)",
      "Opened by introducing yourself."
    ],
    "next_time": [
      "Characterises the chest pain: onset, character, radiation and associated symptoms: Work through onset, character, radiation and associated symptoms for any chest pain.",
      "Recognises that this patient needs observation and repeat testing rather than discharge: ST depression and a raised first troponin mean he should stay for serial testing.",
      "Elicits cardiac risk factors: smoking, blood pressure and family history: Ask about smoking, blood pressure, diabetes, cholesterol and heart disease in close relatives.",
      "... 2 more"
    ],
    "formative_note": "Formative coaching generated from transcript heuristics. It is not a validated measure of empathy, communication skill or clinical competence; review it with a teacher.",
    "requests_made": [
      "order:tox_screen",
      "order:mri",
      "order:ecg",
      "... 1 more"
    ],
    "debrief": {
      "diagnosis": "Cocaine-associated chest pain with possible non-ST-elevation myocardial infarction",
      "teaching_points": [
        "Ask every chest pain patient about stimulant use, and ask again when the evidence does not fit the answer.",
        "A guarded patient is more likely to disclose after a non-judging explanation of why the question matters for treatment.",
        "A first troponin above the reference needs a repeat and observation, not discharge."
      ],
      "expected_disposition": "admit"
    },
    "objectives": [
      {
        "objective_id": "obj.stimulant_use",
        "criterion": "Uncovers recent stimulant use despite the patient's initial denial",
        "kind": "elicit_fact",
        "result": "met",
        "evidence": [
          {
            "turn": 5,
            "quote": "I noticed your urine drug screen is positive for cocaine. Did you use anything last night?"
          }
        ],
        "uncertain": false,
        "suggestion": "You noticed that the story and the evidence did not match, and raised it in a way that let him answer honestly.",
        "critical": true,
        "rubric_domain": "listening",
        "basis": "ledger"
      },
      {
        "objective_id": "obj.initial_tests",
        "criterion": "Requests an ECG and a troponin",
        "kind": "action",
        "result": "met",
        "evidence": [
          {
            "turn": 5,
            "quote": "[order at finish] order:ecg"
          },
          {
            "turn": 5,
            "quote": "[order at finish] order:troponin"
          }
        ],
        "uncertain": false,
        "suggestion": "Keep doing this.",
        "critical": true,
        "rubric_domain": "reasoning",
        "basis": "ledger"
      }
    ],
    "rubric": {
      "rubric_id": "builtin_encounter_v1",
      "title": "HospitalGym formative encounter rubric (built-in)",
      "source": "builtin",
      "total": 14,
      "max_total": 24,
      "n_scored": 6,
      "review_recommended": false,
      "note": "Formative coaching generated from transcript heuristics. It is not a validated measure of empathy, communication skill or clinical competence; review it with a teacher.",
      "domains": [
        {
          "key": "history_gathering",
          "name": "Gathering the history",
          "score": 1,
          "rationale": "2 of 21 askable findings elicited; 2 of 9 critical findings reached; 1 open question(s).",
          "evidence": [
            {
              "turn": 1,
              "quote": "Hi, I'm Dr. Shah, one of the residents. What brings you in today?"
            },
            {
              "turn": 5,
              "quote": "I noticed your urine drug screen is positive for cocaine. Did you use anything last night?"
            }
          ],
          "uncertain": false,
          "descriptor": "Key history is missing and the interview does not hang together.",
          "triggers_review": false
        },
        {
          "key": "listening_cues",
          "name": "Listening and following cues",
          "score": 3,
          "rationale": "1 of 2 guarded finding(s) reached by following the patient's cues; 0 deflection(s) passed without follow-up.",
          "evidence": [
            {
              "turn": 5,
              "quote": "I noticed your urine drug screen is positive for cocaine. Did you use anything last night?"
            }
          ],
          "uncertain": true,
          "descriptor": "Follows the patient's story and asks sensible follow-up questions.",
          "triggers_review": false
        }
      ]
    },
    "elicited": [
      {
        "fact_id": "f.chief_complaint.chest_pain",
        "text": "Central chest pressure that began about two hours before arrival",
        "category": "chief_complaint",
        "critical": true,
        "rule": "volunteered",
        "turn": 1,
        "by": "Hi, I'm Dr. Shah, one of the residents. What brings you in today?"
      }
    ],
    "missed": [
      {
        "fact_id": "f.hpi.onset",
        "text": "Onset at rest, around 6 am, while getting ready for a shift; woke feeling unwell",
        "category": "hpi",
        "critical": true,
        "rule": "if_asked",
        "asked": false,
        "how_to_reach": "ask about it directly"
      }
    ],
    "structure": {
      "opening": {
        "observed": true,
        "detail": "introduced self",
        "evidence": [
          {
            "turn": 1,
            "quote": "Hi, I'm Dr. Shah, one of the residents. What brings you in today?"
          }
        ]
      },
      "open_to_closed": {
        "observed": true,
        "detail": "first question was open",
        "evidence": [
          {
            "turn": 1,
            "quote": "Hi, I'm Dr. Shah, one of the residents. What brings you in today?"
          }
        ]
      },
      "summarising": {
        "observed": false,
        "detail": "no summary back to the patient",
        "evidence": []
      },
      "closing": {
        "observed": false,
        "detail": "no closing in the last three turns",
        "evidence": []
      },
      "topic_order": [
        "chief_complaint",
        "concealed"
      ],
      "topic_returns": 0,
      "n_learner_turns": 3,
      "n_open_questions": 1,
      "n_requests": 2
    },
    "communication": {
      "note": "Formative coaching generated from transcript heuristics. It is not a validated measure of empathy, communication skill or clinical competence; review it with a teacher.",
      "empathy_statements": [],
      "normalising_statements": [],
      "judgmental_language": [],
      "jargon": [],
      "stacked_questions": [],
      "missed_cues": [],
      "re_asked_fact_ids": {},
      "explanations": [],
      "final_rapport": 2
    },
    "artifact_interpretations": [
      {
        "artifact_id": "art.tox_screen",
        "title": "Urine drug screen",
        "interpretation": "Screening immunoassay consistent with recent cocaine exposure. A screen does not time the exposure or prove the cause of the chest pain."
      }
    ]
  },
  "interaction_result": {
    "interaction_id": "enc-137be581a818",
    "interaction_type": "clinician_encounter",
    "patient_id": 0,
    "participants": [
      {
        "entity_id": 0,
        "role": "patient",
        "played_by": "ai"
      },
      {
        "entity_id": "learner",
        "role": "resident",
        "played_by": "human"
      }
    ],
    "resolver": "played",
    "duration_min": 9.2,
    "information_gained": [
      "f.chief_complaint.chest_pain",
      "f.concealed.cocaine_use",
      "f.lab.tox_cocaine",
      "... 3 more"
    ],
    "decision": {
      "kind": "disposition",
      "orders": [
        "tox screen (lab)",
        "mri (imaging)",
        "ecg (bedside)",
        "... 1 more"
      ],
      "disposition": "admit",
      "detail": "Chest pressure after cocaine use; needs ECG and serial troponin."
    },
    "quality": 0.449,
    "session_ref": "enc-137be581a818",
    "objective_results": [
      {
        "objective_id": "obj.characterise_pain",
        "result": "not_observed"
      },
      {
        "objective_id": "obj.cardiac_risk",
        "result": "not_observed"
      },
      {
        "objective_id": "obj.stimulant_use",
        "result": "met"
      },
      "... 5 more"
    ]
  },
  "written_back": false
}
```

- `objectives[].result` is one of `met | partly_demonstrated | not_observed | not_assessable`; `evidence[]` are `{turn, quote}` taken from the transcript; `uncertain: true` marks thin evidence or heuristic judgements; `basis` says where the result came from.
- `rubric.domains[].score` is `1..4` or `"N/A"`. `review_recommended` is true when a domain flagged for review scored 1.
- `quality = 0.5*critical_fraction + 0.3*objective_score + 0.2*decision_score` and `duration_min = clamp(4 + 0.75*turns + 1.5*requests, 5, 120)` (simulated minutes); both are documented in `encounter/grader.py`.
- `decision.orders` are plain words with a category tag (`"ct abdomen (imaging)"`, `"troponin (lab)"`) because the simulator reads them as text.

### GET /api/encounters?case_id=
```json
[
  {
    "encounter_id": "enc-137be581a818",
    "case_id": "chest-pain-line-cook",
    "case_version": 1,
    "title": "Chest pressure in a 41-year-old line cook",
    "patient": "Rafael Quintero",
    "status": "finished",
    "started": "2026-10-10T06:08:42+00:00",
    "finished": "2026-10-10T06:08:42+00:00",
    "turns": 5,
    "preview": false,
    "quality": 0.449,
    "duration_min": 9.2,
    "grader": "offline",
    "rubric_total": 14,
    "rubric_max": 24,
    "n_disclosed": 6,
    "sim": null,
    "written_back": false
  }
]
```

### POST /api/tts
Body `{"text": "...", "voice"?: "<elevenlabs voice id>"}`. `200 audio/mpeg` with a key, otherwise `204` with an empty body.

### GET /api/encounter/status
```json
{
  "llm": {
    "live": false,
    "provider": "offline",
    "model": null
  },
  "voice": {
    "live": false,
    "provider": "browser"
  }
}
```


## Round 2 changes (additive; nothing above was removed)

**Validation and approval**
- The validation report has one more key, `needs_acknowledgement` (bool). Warnings may carry `"level": "attention"` (thin case: no chief complaint, fewer than 5 history facts, no diagnosis, no expected disposition, no objectives, nothing in the chart at the start). New errors: a non-numeric value in a numeric lab row or in a lab/vital fact with a unit. New contradiction kind: `stopped_medication_not_listed`.
- `POST /api/cases/{id}/approve` accepts `acknowledge_warnings`. Omitted: approval proceeds as before and the response lists `warnings_to_acknowledge` (also stored as `review.warnings_at_approval`, `review.warnings_acknowledged: false`). `false`: 409 `{detail: {message, needs_acknowledgement: true, warnings: [...]}}` while attention warnings exist. `true`: approves and records the acknowledgement. Recommended page flow: call with `false`, show the warnings with an "I have read these" tick, then call with `true`.

**From a description**
- `POST /api/cases {from_description}` now returns a draft that contains only what the text states. The response adds nothing new at top level, but `notes[]` always holds three lines starting "Taken from your text:", "Scaffolded for you to edit:", "Missing, needs your input:" (the same lists are stored in `review.taken_from_text`, `review.scaffolded`, `review.missing`). When no presenting complaint can be read, a note starting "WARNING:" is added. The draft always has `validation.needs_acknowledgement: true`.

**Encounter turns**
- New `result` values: `answered_negative_by_default` (a plain "no" on a topic the case does not define; never added to the chart; switch off per case with top-level `"default_negatives": false`), `answered_from_persona` (feelings / ideas / concerns with no authored concern fact), `nothing_more_to_add`, `deflected_off_topic` (off-topic and prompt-injection attempts), and for requests `default_normal`.
- Ledger events add `default_negative_topics[]` and `default_results[]`; `rule_fired` may hold `open_prompt` (a fact released by "tell me more" / "anything else?") or `template_default_normal` (keyed by the request).

**Orders and examinations**
- `available_requests[]` is now the case's own requests plus the standard workup for its presentation (10 to 20 items instead of 44). Every offered item returns the case's result or a default normal result.
- A default normal result appears in `chart.artifacts[]` with `artifact_id: "default.<kind>.<name>"`, `default_normal: true`, `synthetic: true` and a `note` to show next to it ("Default normal result (synthetic) ..."). It discloses no fact and is not evidence for objectives.
- Anything outside the menu returns `not_available` ("not available in this scenario") and is not included in `interaction_result.decision.orders`.
- Cases may carry `standard_workup: ["order:cbc", ...]`; fact disclosure may carry `also_requests: [...]` (other requests that release the same finding).

**Feedback**
- `elicited[]` and `missed[]` items add `label` (learner-facing name; use it instead of `fact_id`). Suggestions no longer contain raw identifiers and never ask for something already requested. A disposition given on the finish form is always evidence for the reasoning objective.
- `faculty_truth.acceptable_dispositions[]` (optional) lists every disposition the grader accepts; simulated patients get both the simulator's and the template's.

**Simulated patients**
- `ClinicianEncounterResolver.playable(sim, b, patient_id)` -> `{"playable": bool, "reason": str|None}` without holding the patient. `start` (and so `POST /api/encounters {run_id, patient_id}`) answers 409 "this patient cannot be played: ..." for a child whose condition template is adult-only or who is under 5.
- The case keeps the patient's age (children stay children, "accompanied by a parent") and shows the triage level the hospital view shows (`patient_detail().acuity`); the hidden true acuity stays in `faculty_truth.acuity`, with `faculty_truth.triage_acuity` beside it.

## Round 3 changes (after overnight/QA_REPORT_2.md; additive except where marked BEHAVIOUR CHANGE)

**Lifecycle**

- BEHAVIOUR CHANGE: `POST /api/cases/{id}/approve` is now a hard gate. While the validation report has `needs_acknowledgement: true`, any call without
  `"acknowledge_warnings": true` (no body, `{}`, `{"reviewer": ...}`, `false`, a non-boolean) returns **409**
  `{detail: {message, needs_acknowledgement: true, warnings: [{path, message, level: "attention"}]}}` and the case stays a draft. A case with no attention
  warnings (the seed cases) still approves without the flag. The Studio flow (send `false`, show the warnings, send `true`) is unchanged.
- BEHAVIOUR CHANGE: a case with no `chief_complaint` fact now has a validation **error** (`/facts`, "no chief complaint ...") instead of an attention warning, so
  approve returns 422 and it cannot be published.
- New attention warning at `/review/source_description`: "description coverage incomplete: N of M sentence(s) of the source description are not fully reflected
  in any fact or artifact: ...". Only for cases that carry `review.source_description`.

**Cases drafted from a description** (`POST /api/cases {from_description}`); response shape unchanged, new content:

- `review.coverage`: `{sentences, covered, uncovered: [{text, missing_words: [...]}], unplaced: [text]}`: the completeness check. Every sentence of the description is
  either reflected in the case or listed verbatim in `review.missing` / the "Missing, needs your input" note (entries beginning "not placed anywhere in the draft"
  or "not fully captured, check this sentence").
- Top-level `"default_negatives": false` and `"unknown_response": "I'm not sure about that, to be honest."` on these drafts: what the text did not say is unknown,
  never "no". The author can set `default_negatives: true`. Seed and template cases are unchanged (default on).
- Facts may carry `source_text` (the exact words of the description a vital, lab value or concealed item was read from), `complaint_part: true` (one symptom of the
  presenting complaint, also covered by the chief-complaint fact) and `needs_review: true`. Faculty-only, like every other fact field.
- New fact shapes: one `chief_complaint` fact always (when the text has any clinical clause), one `hpi` fact per symptom, ONE `medications` fact listing every
  item (`f.medications.current`, or `f.medications.<name>` when the only medicine is implied by a concealed "stopped taking ..."), ONE `allergies` fact listing every
  allergy with its reaction, `lab` facts released `on_request` by the matching order (`order:cbc`, `order:coags`, `order:bmp`, ...) with a `lab_report` artifact
  per order (`art.lab_<order>`), an `art.medication_list` artifact (`order:medication_list`), `f.social.accompanied_by`, `pmh`, `ros` (stated negatives),
  `family` and leftover-sentence facts. `faculty_truth.severity_basis` holds the word the severity band was read from.
- Title is `"<complaint> in a <age>-year-old <man|woman|boy|girl|patient>"`, or `"<who> (presenting complaint not stated)"`; never a template's complaint label.

**Encounter turns** (`POST /api/encounters/{id}/turn`); same response shape:

- New `result` values in ledger events: `answered_noncommittal` (the case's source description touches the topic but no fact answers it, or a "has it been getting
  worse?" question with no matching fact; the patient says a neutral line instead of "no") and `answered_from_case_summary` ("what brings you in?" on a case with no
  chief-complaint fact: answered from the title or prebrief in the first person).
- `matched_intents[].via` (faculty view only) can now be `"the case's own wording"`, `"pain, asked in general"` or `"general invitation to say what is held back"`,
  with `score: null`, when the match came from the safety net rather than a topic.
- Faculty ledger events may carry `restated_fact_ids` (a fact the care team already knew, voiced to this listener for the first time: no "Like I said") and
  `deflected_fact_ids`. "Like I said:" is now used only for a fact the patient already voiced in a turn of this same encounter.
- A general invitation ("is there something you're afraid to tell me?", "anything you haven't mentioned?") counts as asking about every undisclosed
  `after_rapport` fact: released if rapport is sufficient, otherwise deflected and volunteered later once rapport is reached.

**Feedback** (`POST /api/encounters/{id}/finish`):

- `feedback.missed[]` items gain `status`: `"asked_not_disclosed"` or `"not_asked"` (`asked` is kept and agrees with it). For an asked concealed fact
  `how_to_reach` now starts "you asked; ...". `asked` is true when the matcher credited the question, when the patient gave a cover answer or deflection,
  or when the question's wording matches the fact.
- A turn that carries an empathy or normalising cue is never counted as judgmental; `communication.judgmental_language` and the rapport / closure rationales
  use the filtered list. "Acknowledged the patient's feelings" is not listed under `strengths` when the rapport domain scores 1.
- Reasoning rationale: when the chosen disposition is one of several in `faculty_truth.acceptable_dispositions` the text reads "is one of the dispositions this
  case accepts (...)" instead of "matches / differs from the case's expected disposition".


## Round 4 changes (description reader self-check; additive)

- Description drafts: `default_negatives` is now **true when the coverage check placed every sentence** (`review.coverage.uncovered` and `.unplaced` both empty) and
  false otherwise; `soft_negatives` (bool, new, top level) is the opposite. With `soft_negatives`, a yes/no question about the patient's own body or habits on a
  topic the draft does not hold gets "Not that I've noticed." / "Not that I know of." / "I don't think so." with the new ledger `result`
  `answered_soft_negative_by_default` (never written to the chart). In both modes a question that overlaps any fact or the source description is never answered
  negatively (`answered_noncommittal` or the fact's own rule).
- `disclosure.empathy_needed` (int, optional, on `after_rapport` facts): turns with an empathy or normalising cue required in addition to `rapport_needed`.
  Description drafts set `{"rule": "after_rapport", "rapport_needed": 3, "empathy_needed": 1}` on concealed items, because an introduction, an agenda and one open
  question already score 3. Seed cases do not use it. Encounter state gains `empathic_turns`.
- `answers_by: "accompanying adult"` (top level, new) on drafts for a child under 4 or described by a parent: every answer is worded as the adult speaking about
  the child ("She's had a fever ..."). `profile.speech_style` says so.
- New fact shapes from descriptions: `f.hpi.severity` ("pain rated 8/10"), `f.medications.none` ("takes no regular medications"), `f.pmh.pregnant`, one `hpi` fact
  per relative clause of the complaint (", which gets worse when ..."), marital status under `f.social.living_situation`.
- `review.missing` may contain entries starting "wording to review:" from the reader's own wording check (`encounter.describe.wording_problems(case)`).
- A greeting or agenda-setting turn that happens to be a question ("Hello, I'm Dr. Lee. Is it okay if I ask some questions?") now has result `no_fact_requested`
  and a greeting reply instead of the off-topic line. "Do you have pain anywhere?" when the only pain fact is concealed returns that fact's cover answer.
