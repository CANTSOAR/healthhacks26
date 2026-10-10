# Contract change requests from the encounter engine

Nothing here blocks: the routes in the "Encounter" section of `contracts/api.md` exist with the documented fields.
These are refinements the implementation already uses; please fold them into `contracts/` if you agree.
Full request/response examples are in `encounter/API_NOTES.md`.

## contracts/api.md

1. **Two extra routes.**
   - `GET /api/cases/{case_id}/image`: patient photo (from `.private/` when the case names one) or an SVG placeholder. `patient.image` in the start response points here.
   - `GET /api/encounter/status`: `{llm, voice}`; the main server should fold `encounter.status()` into `/api/status` instead.
2. **`POST /api/encounters`** also accepts `preview: true` (faculty test run of a draft or approved version; otherwise only published versions start, 409 for the rest), `learner` (display name stored in the session) and, on the `{run_id, patient_id}` form, `force: true` (start even if `hold_for_play` returned false; the result then cannot be written back). The response adds `available_requests`, `rapport`, `status`, `preview`, `sim`, and `llm.model`.
3. **Turn / request responses** add `encounter_id`, `turn`, `request_id`, `notes[]` (system lines), `released_artifacts[]`, `result`, and `llm` (provider status). `disclosed[]` items add `category` and `rule`. On `request`, `reply` is `null`.
4. **`GET /api/encounters/{id}`** takes `?view=faculty` for the full ledger and case snapshot. The student view never contains them.
5. **`GET /api/cases`** takes `?all_versions=true`; list items add `versions`, `seed`, `n_facts`, `n_objectives`, `needs_faculty_review`.
6. **`POST /api/cases`** returns the stored draft plus `validation`, `notes[]` and `created_from: {method, template_id, fallback}`. **`PUT`** returns the case plus `validation` and `new_version_created`.
7. **`POST /api/cases/{id}/validate`** accepts an optional body of unsaved top-level keys (validates without saving) and `?version=`. `consistency[]` items are objects `{level, kind, message, paths}`, and `warnings[]` are `{path, message}` like errors.
8. **`POST /api/cases/{id}/approve`** accepts `{reviewer}`. Approve and publish answer 422 with the validation report when the case does not validate.
9. **Feedback** adds `structure`, `communication`, `formative_note`, `quality`, `quality_parts`, `requests_made`, `artifact_interpretations`, `debrief`, `fallback`; objectives add `kind`, `critical`, `rubric_domain`, `basis`; rubric domains add `descriptor` and `triggers_review`; the rubric adds `total`, `max_total`, `n_scored`, `review_recommended`, `rating_scale`, `note`.
10. **`GET /api/clinicians`** returns `{source, fictional, clinicians: [...]}` rather than a bare list, so the page can label where the profiles came from.

## contracts/case.schema.json

The schema has no `additionalProperties: false`, so these already validate; listing them so they can be documented:

- fact: `label` (short name for chart rows and lab artifacts), `ref_range`, `flag`, `patient_answer_auto` (wording was auto-drafted, review it), `needs_review`.
- lab artifact rows: optional `fact_id` tying a row to its fact (used by the artifact-versus-fact consistency check).
- case: `updated` (ISO time, set by the store).
- `review.source_description` (the free text a draft was generated from).

## contracts/interaction.schema.json and contracts/sim_api.md

1. **`decision.orders` format.** `sim.apply_interaction_result` reads orders as free text and looks for words such as `ct`, `xray`, `lab`, `cbc`. The resolver therefore sends plain words with a category tag: `"ct abdomen (imaging)"`, `"troponin (lab)"`, `"ecg (bedside)"`. Examinations and record requests are not sent as orders. Please document the expected format (or an enum) in the schema.
2. **When write-back is possible.** `hold_for_play` succeeds while the patient is still waiting, but `apply_interaction_result` raises unless the patient is `with_provider`. If a student finishes first, `finish` returns `written_back: false` and `feedback.writeback_error`. Suggest stating in `sim_api.md` that the server should start a played encounter only when `pending_interaction(...).status == "in_progress"`, or advance the simulation until it is.
3. **`patient_id` for encounters that do not come from a simulation.** The result schema requires an integer; standalone encounters send `patient_id: 0` and are never written back. A nullable `patient_id`, or a documented sentinel, would be cleaner.
4. **Children.** Resolved in round 2: a patient under 18 stays a minor in the case (paediatric variant for abdominal_pain, respiratory, injury_trauma, infection_fever, other_medical). For the other templates, and for children under 5, `ClinicianEncounterResolver.playable()` returns `{playable: false, reason}` and `start` answers 409. Suggest adding `playable` / `reason` to `pending_interaction` or the patient detail so the UI can hide the Play button.
5. **Condition template keys the simulator reads.** `catalog/conditions/*.yaml` carries, next to the encounter engine's own keys (`kind`, `options`, `ranges`, `include`), mirrored generic keys for `sim/interact.py`: `by_severity: {mild|moderate|severe: {range|options}}`, `values`, `p`, plus `diagnoses[].label` and `diagnoses_ordered_by_severity: true`. With these the simulator's latent-truth values and the instantiated case agree (checked: 23 of 25 facts identical for one real simulated patient; the other two are the history/medicines pair that the encounter engine draws together so they stay consistent, where the simulator reports no value). Worth writing this shape into `contracts/catalog.schema.json`.

## Round 2 additions

- `contracts/api.md`: approve accepts `acknowledge_warnings`; validation report adds `needs_acknowledgement`; turn/request `result` adds `answered_negative_by_default`, `answered_from_persona`, `nothing_more_to_add`, `deflected_off_topic`, `default_normal`. Details in `encounter/API_NOTES.md` ("Round 2 changes").
- `contracts/case.schema.json` (all already valid, no `additionalProperties: false`): case `default_negatives` (bool), `standard_workup` (list of requests); fact `disclosure.also_requests`; `faculty_truth.acceptable_dispositions`, `faculty_truth.triage_acuity`; `review.taken_from_text`, `review.scaffolded`, `review.missing`, `review.warnings_at_approval`, `review.warnings_acknowledged`.
- `contracts/sim_api.md`: the resolver reads `sim.patient_detail(b, id)["acuity"]` (the triage-assigned level the viewer shows) so the triage note matches the hospital view; please keep that key stable.
