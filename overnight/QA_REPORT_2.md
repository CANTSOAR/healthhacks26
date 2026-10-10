# HospitalGym QA report 2 (re-run after the fix round)

Independent re-test, 2026-10-10, about 09:55 to 10:45 EDT, branch `aryan` at `3e83a89` plus whatever the scene-fix agent had in the working tree (`web/components/scene/HospitalScene.tsx` modified, `SceneDebug.tsx` untracked).
Driven with Playwright (project Chromium, Metal GPU, 1440x900 unless stated) against the servers the orchestrator had started: API :8000, `next dev` :3000. I started and stopped neither.
Language model: offline for the whole session (`/api/status` llm.provider = offline). Every patient reply, colleague reply and grade below is the offline path.
Scripts, raw output (`*.out`), `errors.log` and about 150 screenshots are in `overnight/qa_scratch/r2/` (gitignored).
Organizer sample patients and clinicians are referred to by number only.

Tester, not builder: no code was changed. Defect numbers D1 to D37 are the first report's; new defects are N1 onward.

## 1. Verdict per demo promise

| # | Promise | First report | Now | Why |
|---|---|---|---|---|
| 1 | Two commands, open a browser, watch a 3D hospital run | Works with caveats | Works with caveats | Servers were already up, so the cold start was not re-timed. Watch plays, stops at the end of each recorded window, and says so when you click outside one. Still only 5 one-day windows out of 30 days are recorded (labelled "Day 2 · Tue 00:00–00:00"). Under Fixed staffing most of the bed list is red with "Awaiting results" for 5 to 13 hours (D21, not fixed). |
| 2 | Take it over by hand | Works with caveats | Works with caveats | All four injects are acknowledged and appear in the feed; the run survives a reload and Play → Watch → Play; changing scenario mid-run asks first. Toasts still show raw ids ("Scenario event started: flu_wave"). Knob boundaries and structural changes were not re-walked. |
| 3 | Hand it to a trained manager | Works with caveats | Works with caveats | Hand-over to `ppo_min_cost`, `ppo_scratch_min_cost`, `tuned_min_wait` and take-back all work, kind chip correct. In Play nothing says what the learned manager is or how it did (N9). `ppo_scratch_min_cost` is presented as "beats" its heuristic while it runs an 11-hour mean wait (N8). |
| 4 | Compare managers tuned for different objectives on the same seed | Works with caveats | Works with caveats | Managers now differ a lot (mean wait 114 vs 12 min in the default pair). Recorded default pair is the weight-conditioned PPO at min_cost weights vs at min_wait weights, not `tuned_min_cost` vs `tuned_min_wait`; both pane titles truncate to the same text (N12). "Run live" still defaults to Fixed vs Rule-based. People rendered in colour in pane B in every circumstance I tried (section 4, D-black). |
| 5 | Click any entity, see every data point and where it came from | Works with caveats | Works with caveats | Layout provenance links are fixed; wards showed 24 of 24 or fewer. Clicking a person in 3D now works about 7 times in 10 when aimed (D17). `space/corridor` still has no catalog entry (404). |
| 6 | Click a patient and play the encounter | Broken on the default path | Works with caveats | The one-tab path now works end to end: find or pick a patient, play, finish, write-back card (applied, or queued then applied), "Return to hospital" lands in Play on the same run with the patient selected and flagged "played encounter". Leaving an encounter without finishing strands the patient in their bay with no way back from the hospital view (N4). |
| 7 | Patient Studio, structured path | Works with caveats | Not re-walked | Only the editor reached through the description path was exercised. Validation now warns on thin cases and the UI makes the author tick an acknowledgement before approving. |
| 8 | Patient Studio, free-text description | Broken | Broken for 4 of 5 realistic descriptions | It no longer builds a different patient: nothing from another illness appears, and the taken / scaffolded / missing notes are shown. But it silently drops stated content, and the published patient then denies their own described illness (N1), a concealed item that does not match one built-in pattern can never be elicited (N2), and the first report's description is the only one of five that came out playable as described. |
| 9 | Trade-off chart | Works | Works | 20 values (5 manager/scenario rows x staffing cost, total cost, wait, LWBS) match `GET /api/results` / `RESULTS.md` to the displayed precision. Both x-axes and both scenarios work. Overlapping marks hide tuned heuristics under learned ones and the table truncates names (N12). |
| 10 | Offline / fixture mode | Works with caveats | Works | With `?api=` pointing at a dead port: a banner in every mode ("API unreachable — showing fixture data (not a simulator run)"), status "Offline · fixture", 0 "SIMULATED" chips, managers tagged "[fixture]". Auto-recovery was not tested. |
| 11 | Narrow viewport 390x844 | Works with caveats | Works with caveats | No horizontal page scroll on any of the four pages; other pages are under "More". Off-screen with no hint: the trade-off "Flu surge" toggle, and studio tabs Objectives / Sources / Raw JSON. Footer disclaimer still cut to two lines, ending "Not affiliated with or endorsed by…". |
| new | Care journey (`/journey`) | not tested | Works with caveats | A seed case and a Studio case both run through four stages to a care plan and debrief. Provenance chips, discrepancy flag and the colleague's challenge of an unsupported statement work. Unsupported-statement detection is partial, the care plan contains junk rows, ordered tests show a result in the stage and "result not back" in the plan, and the "fictional" receiving colleague carries an organizer sample clinician's name (N3, N5, N6). |

## 2. Re-test of D1 to D21

| ID | First finding | Status | What I saw |
|---|---|---|---|
| D1 | Return to hospital does not return to the run | Fixed | 3 same-tab round trips. Link is `/?run_id=…&patient_id=…`; lands in Play on the same run, toast "Rejoined your run where it was paused.", patient selected, journey stepper shows Provider → Disposition "admit" → Ward, Flags "admit decision · played encounter". The hospital is paused during the encounter (`t` did not move). Note: the run resumes at the speed it had; at 48x the patient is on the ward before the page has settled. |
| D2 | "Play this encounter" offered for everyone, fails for most | Fixed | Button only on playable patients; others get a reason ("past the clinician encounter (in ward)", "already been played", "An encounter is already open"). Playable patients are tagged "playable" and listed first (3 to 9 at a time out of about 160). "Find a patient to play" paused the clock and selected a playable patient in 4 of 5 tries; the fifth selected nobody and showed no message. No error card in 6 starts. |
| D3 | Write-back fails for early-state patients, raw Python error | Fixed | Patient picked in triage: card "Queued for the simulation … This card updates when that happens", `data-write-back=queued`, no error. After returning and letting the clock run: state in_ward, flags admitted + played, interactions `triage:sampled, clinician_encounter:played, disposition:sampled`; reopening the encounter URL shows "Applied". Only one early-state patient was caught (the others had moved on before my script paused), so waiting-room and waiting-for-bay were not separately exercised. |
| D4 | Description path builds the wrong patient | Partly fixed | The first report's description now yields the described patient (name, age, job, complaint, 192/110, concealed item with a pharmacy-record evidence path; confronted after ordering the record, she admits it). The notes panel is shown. Four other descriptions lose content silently and produce patients who contradict the text: N1, N2. |
| D5 | Build or second dev server breaks the running one | Not re-tested (by instruction) | Documented in `web/README.md` and the morning report. No `distDir` separation that I could see; the hazard is still there for anyone who runs `pnpm build` during the demo. |
| D6 | Recordings hold 24 h of 30 days | Partly fixed | 5 windows of one day each (days 2, 3, 4, 8, 30). Playback stops with "End of this recorded window. Next recorded window / Replay"; a click at 55% of the timeline says "No 3D recording for Day 16, 20:00: the chart shows that hour, the scene stays where it was." Window chips read "00:00–00:00". 25 of 30 days still have no scene. |
| D7 | Managers barely differ | Mostly fixed | Normal week: tuned min_cost 130.6 min / $56.2k staffing, tuned min_wait 12.2 min / $91.5k. The chart defaults to staffing cost. Total cost still spans only $525k to $591k. Flu surge still does not break the wait-tuned or balanced managers (12.5 and 13.0 min). |
| D8 | Learned managers indistinguishable, unexplained | Fixed, with a new honesty gap | Labels say "Learned (PPO, cloned from tuned heuristic then fine-tuned)" / "(PPO from scratch)" / "(weight-conditioned)"; Watch, Compare, Trade-off and Tour show the training note and the held-out verdict ("matches (difference not significant)" where that is the result). Cloned agents still sit on top of their heuristics, and the screen now says why. See N8, N9. |
| D9 | Top bar overflows at 1440 | Fixed | Two rows. Status pill at x 1349 to 1415 at 1440 px and 1189 to 1255 at 1280 px; Tour button fully visible; no horizontal scroll. |
| D10 | Layout provenance links broken | Fixed | Bay 4, CT 1, Ambulance bay, Results waiting: `href` is the bare URL; the prose is shown as text. |
| D11 | Ward shows more patients than beds | Cannot reproduce | Day 1 afternoon, human run: units A, B, C 24 of 24, D 23 of 24, ICU 18 of 24. "Results waiting" still reads "0 of 16" (catalog capacity not re-checked). |
| D12 | Played case contradicts the hospital patient | Mostly fixed | 5 patients compared: age inside the hospital's band and complaint group consistent in all 5; the triage note (read on one) now quotes the run ("Hospital triage record: ESI 4; other medical; arrived by walk in; age 91"). Remaining: the header says "this patient is occupying a bed in the running simulation" for a patient at Triage 1; the case for an ESI 2 child brought by ambulance "was written for 'discharge'" and the learner is marked down for admitting. |
| D13 | Offline replies wrong or robotic | Partly fixed | 72 replies on the three seed cases with a new 24-question set: 0 canned "I'm not sure", 0 leaks, 2 prompt injections deflected in character; 11 wrong or contradictory, 3 robotic. Detail and the default-"no" findings: N1, N7. |
| D14 | Fixture fallback silent, charts tagged SIMULATED | Fixed | See verdict row 10. |
| D15 | Run discarded on reload / mode switch; scenario menu lies | Fixed | Reload: clock carried on (Day 11 23:50 → Day 12 17:30 at 48x), no Start button. Play → Watch → Play: rejoined the same run. Scenario change mid-run: confirm "A run is in progress. End it, save its result, and switch to Flu surge?"; cancelling leaves the menu on Normal week. Expiry not reached: the server now keeps a disconnected run about 10 minutes (about 30 with an open encounter). |
| D16 | Most orderable tests "not available" | Mostly fixed | The menu is now the 13 to 17 requests relevant to the template; undefined ones return "result added to the chart (default normal result, synthetic)". Side effects: N5 (care plan says "result not back" for the same tests) and, for description-made cases, a default "Pharmacy dispensing record: No dispensing record found" for a patient who has just listed prescriptions. A calf-swelling case cannot order a D-dimer or leg ultrasound because it inherited the respiratory menu. |
| D17 | People nearly unclickable in 3D | Partly fixed | 8 patients selected from the list (camera flies to them), inspector closed, then 3 clicks each 30, 40 and 50 px below the selection pill: 17 of 24 selected that patient, 3 a neighbouring patient, 4 the room. First report: 1 of 81. A blind grid over the building was not re-run, so the rate for a person you have not already located is unknown. |
| D18 | Validation approves thin cases | Mostly fixed | Thin cases now get "attention" warnings (no chief complaint, fewer than 5 history facts, no diagnosis, no expected disposition) and the UI blocks approval behind "I have read these and want to approve the case as it is" (button disabled until ticked). A lab value of "abc" now gives a validation error and approval is refused (422). But `POST /api/cases/{id}/approve` with no body approved four warning-laden cases (needs_acknowledgement: true) without any acknowledgement, and a case with no chief complaint at all can be published. |
| D19 | Feedback contradicts the transcript | Partly fixed | Gone: "disposition not observed" above the quoted disposition; "request X" after X was requested; raw `exam:`/`order:` ids in suggestions. New or remaining: N10 (a confidentiality reassurance scored as judgmental, dropping Rapport to "1 Unsafe or absent" beside "Acknowledged the patient's feelings" under Strengths); a concealed item listed as "Not asked" after it was asked directly twice (N2); "disposition 'admit' differs from the case's expected disposition" on sim patients (D12). |
| D20 | Organizer sample patients shown by default | Not fixed (decision pending) and wider | The `/encounter` picker (group "Organizers' sample patients") and the `/journey` picker (8 of them) list organizer sample patients; `/studio` was not re-checked. New: the generic journey's handoff colleague is an organizer sample clinician by name, labelled "fictional" (N3). |
| D21 | Bays "Awaiting results" for 5 to 9 hours | Not fixed | Watch, Fixed staffing, Day 2 13:40: Bay 6 "Awaiting results 12 h 45 m", Bay 9 5 h 10 m, Bay 10 3 h 05 m, beside "Door to provider 13 min". Under a cost-tuned manager every bay is red at 6 to 19 hours. |

## 3. New defects

Owner key as before: web scene, web UI, server, sim, rl, encounter engine, encounter pages, journey.

### P0: breaks a judged demonstration

**N1. A patient made from a description denies the illness in their own description.** Owner: encounter engine (description extraction + default-"no" policy).
Repro: Studio → New patient → From a description → paste each text below → Create → Validate → Approve (tick the acknowledgement) → Publish → start the encounter (or `POST /api/cases {"from_description": …}` then `/api/encounters`).
1. "45M, crushing chest pain 1 hour, smoker." Draft: name "Unnamed patient", age 40 (placeholder; "45M" not read), sex unspecified, title "Chest pain", no chief-complaint fact, one fact "Smoker". Played: "What brings you in?" → "I'm not sure. I can't really tell you anything about that."; "Do you have chest pain?" → "No, no chest pain."; "Do you smoke?" → "It's the smoker."
2. A 6-year-old with "a barking cough and noisy breathing since last night", runny nose, three vitals, immunisations, an anxious mother, and a swallowed toy he does not want to mention. Draft: title "Shortness of breath in a 6-year-old man" (neither phrase is in the text), three vitals, nothing else. Played: "Do you have a cough?" → "No, I'm not coughing."; "Did you swallow anything?" → "No, I haven't noticed that."; "Is your mum here with you?" → "Nothing that I know of in my family."
3. A 74-year-old with black tarry stools on "warfarin 5 mg daily for atrial fibrillation, metoprolol 25 mg twice a day, omeprazole 20 mg, and atorvastatin 40 mg", two allergies, "has been taking ibuprofen for a week … but has not told her doctor", "Hemoglobin 8.1, INR 4.6". Draft: medication fact cut at "metoprolol 25 mg twice"; omeprazole, atorvastatin, ibuprofen, haemoglobin and INR are gone and are not in the "missing" list. Played: "Do you take omeprazole or atorvastatin?" → "No, nothing like that."; "Have you been taking any painkillers like ibuprofen?" → "No, nothing like that."; opening line "I've had black tarry stools and feeling lightheaded when she stands for two days."
4. A 52-year-old truck driver with calf pain, hiding that he "has been coughing up blood since yesterday". Draft is otherwise faithful. Played: see N2.
Saw: all four validate as "Can be approved", pass the acknowledgement step and publish in under a minute. The notes panel is honest where it noticed a gap (cases 1 and 2 list "presenting complaint (none could be read from the text…)") and silent where it dropped content (case 3).
Expected: text the extractor could not place is listed under "missing" verbatim; a draft with no chief complaint cannot be published; the default "no" is never used for a symptom, medicine or event that appears in `review.source_description`.
Evidence: `r2/studio_api.out`, `r2/studio_enc.out`.

**N2. A concealed item from a description can never be elicited unless it matches the built-in adherence pattern.** Owner: encounter engine (description extraction, offline matcher).
Repro: description 4 above through the Studio UI (timed: editor open at 14 s, validated 46 s, acknowledged and published 51 s, scripted). Start the encounter. Ask "Have you been coughing up any blood?" → "No, I'm not coughing." Build rapport to 5 of 5 (three empathic statements; the rule needs 3). Ask "Have you been coughing up blood?", "Have you coughed up any blood since yesterday?", "Any blood when you cough?" → "No, I'm not coughing." / "No, no cough." / "No, I'm not coughing." "Is there something you are afraid to tell me?" → "Sorry, I don't follow. Can we get back to what's wrong with me?"
Saw: the concealed fact's only topic is the first 60 characters of the sentence, so no question matches it; the authored cover answer ("I'd rather not get into that.") is never used; the patient flatly lies instead, at any rapport. Feedback then lists the item under "Findings you did not reach" as "Not asked · To reach it: build rapport first (needs 3), then ask". The notes panel does say there is no evidence path, but not that the item is unreachable.
Expected: topics derived from the concealed sentence's content words; cover answer before the threshold; disclosure after it.
Contrast: the first report's blood-pressure-pills description works (denied twice, admitted when confronted with the pharmacy record, objective "met").

### P1: visible wrongness a judge would notice

**N3. The "fictional" AI colleague in the care journey carries an organizer sample clinician's name.** Owner: journey (colleague selection) + journey pages. Also a public-repo risk for any screenshot of this stage.
Repro: `/journey` → any patient → "Emergency department to ward" → reach stage 4 (Handoff).
Saw: "with Dr. <organizer sample clinician #1>, MD, Admitting physician (AI colleague)" and under the name "AI colleague receiving the handoff · fictional". The name comes from `/api/clinicians` (`source: organizer_private`); his listed role there is a different specialty from the one shown. Record entries are titled "ANSWER TO DR. <same name>, MD". The heart-failure journey uses built-in invented names instead.
Expected: built-in invented names on every template, or the organizer profile shown as what it is and never labelled fictional.

**N4. Leaving an encounter without finishing strands the patient, with no way back from the hospital.** Owner: web UI (Inspector) + server (hold release).
Repro: Play → Find a patient to play → Play this encounter → ask two questions → browser Back.
Saw: the run is rejoined and the clock runs, but the patient stays held: P-002384 "In treatment 14 h 45 m" in Resuscitation 1 with MD-17, inspector "Encounter not playable now. An encounter is already open for this patient." There is no "resume" or "release" control. The encounter is still open at its `/encounter?encounter_id=…` URL (transcript kept) but nothing links to it; `DELETE /api/runs/{run}/patients/{id}/hold` releases the patient (200) but nothing in the UI calls it. The run's expiry also stretches to about 30 minutes.
Expected: "Resume encounter" and "Give back to the simulation" on that patient.

**N5. Care plan and shared record contradict the stage that produced them.** Owner: journey (care plan assembly, provenance).
Repro: journey on `chest-pain-line-cook` and on a Studio case; play the physician stage (order BMP and CBC, write a note), let the sampler do triage and reconciliation, play the handoff.
Saw:
- BMP and CBC returned "result added to the chart (default normal result, synthetic)" during the stage; the care plan lists "Result not back: bmp (lab) · ordered, no result in the record" and the debrief counts them as lost at handoff.
- "Plan and orders" contains my reply to the colleague, "I don't know.", as a plan row (provenance "ED nurse · you · Handoff · colleague").
- "Problems" contains the pharmacist's note "41-year-old male." and the whole triage note as problems.
- A patient statement ("It was about a seven at its worst…", after "Tell me more about that.") is recorded as FINDING with provenance "chart artifact".
- Recommendation objective: "Nothing was said under Recommendation; it came out only when the colleague asked." when the colleague was never answered; the quoted evidence is the Situation sentence.
Expected: default results counted as results; only plan entries under plan; provenance kind matching the source.

**N6. Unsupported-statement checking at handoff catches about half of what is false.** Owner: journey (SBAR checker).
Repro: in the handoff give Background "He is allergic to latex and is on warfarin." and Assessment "Troponin was 900 and the CT showed a large bleed."; on the Studio case "She is allergic to latex and takes omeprazole and insulin."; in the physician stage note write "Patient has a pacemaker and had a stroke last year."
Saw: flagged: latex (both), "Troponin was 900" (both), insulin. Not flagged: "is on warfarin" (no medicine of that name in that record), "the CT showed a large bleed" (no CT in either record), "takes omeprazole", and the pacemaker/stroke note, which goes into the record as "clinician's inference" and then appears in the care plan as a problem with an action attached. The colleague challenged only the latex statement, then accepted "Please admit and monitor." as the answer to "any allergies I should know about?" and "I don't know." as the answer to "Is anything still pending?", after which "Uncertainty named" was marked yes.
Expected: the on-screen claim is "checked against what the team actually learned"; either check stage notes and imaging/medicine claims too or narrow the claim.

**N7. Offline patient: the default "no" contradicts the case, and off-topic questions unlock graded facts.** Owner: encounter engine (offline matcher). Continues D13.
72 replies on the three seed cases (24 questions each, none from the first report's set): 11 wrong or contradictory, 3 robotic, 0 leaks, 0 canned lines.
- "Do you have pain anywhere?" → "No, nothing like that." in the abdominal-pain case (pain 7/10), the chest-pain case, and the breathless case (who takes naproxen for knee pain). Logged as `answered_negative_by_default`.
- "Who do you think will win the election?" → "I don't smoke. A glass of wine on weekends. No drugs." / "I quit smoking twelve years ago…" / "A few beers after a shift…", in all three cases, and it discloses the social-history fact, which then counts as elicited in the grade. On a Studio case "Who will win the world cup?" → "No, I'm not much of a drinker."
- "Which pills are you on regularly?" → "Like I said: I went yesterday and it was normal. No diarrhea, no blood. Just my birth control pill…" (bowel answer glued on).
- "Has it been getting worse since it began?" → the aggravating-factors answer, or "Like I said:" plus an unrelated earlier answer.
- "Do you drink alcohol?" → "Like I said: …" the first time it is asked (because of the election misfire).
- Studio case: "Tell me more about the leg." → "I think that's all, really."; "wat abuot ur brething" → "Mm-hm."; "Is there anything worrying you that you haven't mentioned?" → "I'm not sure what that has to do with why I'm here."
- In a journey, the first thing the patient says to a new clinician is "Like I said: …" (three times in one stage), because an earlier sampled stage asked.
Handled well: typo question about medicines, both prompt injections ("Sorry, I don't understand what you mean…", "I'm the patient here. I was hoping you could tell me."), repeats, feelings on seed cases, concealment on seed cases. No faculty truth, cover answer or expected disposition in any learner payload I inspected.
Default-"no" as policy: it reads naturally for travel, surgery, numbness, blood in stool. It is clinically misleading wherever the case text implies the opposite but no fact carries a matching topic: pain "anywhere", and everything in N1.

**N8. A learned manager is described as beating its heuristic with no mention of what it gave up.** Owner: rl (verdict text) + web UI.
Repro: Watch → "Learned (PPO from scratch): lowest cost" (seen there; the same note text is what Compare and the Tour print for other learned managers; the Trade-off side panel was not read for this one).
Saw: the note ends "On held-out seeds it beats "Tuned heuristic: lowest cost"." directly above Mean wait 658 min, 95th pct 1,435 min, LWBS 31%, median ED stay 1,330 min. `RESULTS.md` has it at 694.7 min mean wait, 31.45% LWBS and 93.8 deaths per 10k (tuned min_cost: 130.6, 8.65%, 16.2); it "beats" on labour cost only (+0.0756 on the min_cost score). The same sentence is used for `ppo_min_cost`, whose margin is +0.0007 ± 0.0005. The text is consistent with `RESULTS.md`; it is the unqualified "beats" that misleads.
Expected: "beats … on its own objective (labour cost); waits 5x longer" or the score and margin beside the word.

**N9. In Play, a learned manager in charge shows no note and no verdict.** Owner: web UI (PlayPanel).
Repro: Play → Start → "Hand over: Learned (PPO from scratch): min_cost".
Saw: "IN CHARGE · Learned · Learned (PPO from scratch): min_…" and "Read-only while a trained manager is in charge." The training note and held-out verdict that Watch, Compare and Trade-off show are absent, and the name is truncated before the objective. Within two simulated days every bay is red.

**N10. Grader scores a confidentiality reassurance as judgmental.** Owner: encounter engine (offline grader). Continues D19.
Repro: any case; say only "I can see this is worrying you. That sounds frightening. Whatever you tell me is only used to look after you."; finish.
Saw: Rapport, respect and empathy = 1 ("Unsafe or absent"): "1 empathic or normalising statement(s) detected, 1 judgmental phrase(s)"; Professionalism also drops with "judgmental wording detected". The same turn is quoted under Strengths as "Acknowledged the patient's feelings". Other empathic lines without that last sentence ("Thank you for telling me. I understand how hard this is."; "That sounds frightening, I'm sorry.") scored 3, so the trigger appears to be the reassurance.

**N11. Description-made patients speak in the author's third person.** Owner: encounter engine. "I've had black tarry stools and feeling lightheaded when she stands for two days."; "I've had sudden pain and swelling in his right calf after a 14 hour drive since this morning."; "It's the smoker." These are the opening lines of the judged free-text demo. The validator flags them only as "auto-drafted; review the wording".

**N12. Names that differ only at the end are truncated to identical text.** Owner: web UI.
Compare default: both pane titles read "Learned (PPO, weight-conditioned) at …"; only the side-panel selects ("…at min_cc" / "…at min_wa") tell A from B. With the tour's pair both titles read "Learned (PPO, cloned from tuned heuri…". Trade-off table at 1440: ten rows begin "Learned (PPO, cloned fro…" or "Learned (PPO, weight-co…" with nothing else to tell them apart. On the chart the label "Tuned heuristic: lowest cost" sits beside a blue Learned mark because the learned mark is drawn over the heuristic's.

### P2

- N13. Tour: the card covers pane B's title in steps 3 and 5 and the "Flu surge" toggle and legend in step 6; in step 2 the building is a thumbnail behind the card and two toasts. Captions are accurate about kinds; `web/README.md` says captions contain no numbers; step 2 and step 4 include "3,310,720 PPO environment steps" from the manager note.
- N14. Recorded-window chips read "Day 2 · Tue 00:00–00:00" for a full day.
- N15. Simulated payer ignores age: a 9-year-old on Medicare; a 91-year-old and an 85-year-old on Medicaid.
- N16. `POST /api/cases/{id}/approve` with no body skips the warnings acknowledgement the UI enforces (D18).
- N17. Live Compare: pane B's stats wrap to a second line where pane A's fit on one; the camera pill overlaps pane B's left edge.
- N18. After "Return to hospital" the encounter header for a finished, applied encounter reads "this patient is in the running simulation, not yet in a bed".
- N19. Browser Back from the hospital to a finished encounter gave a blank lilac page once (15 s wait, `Q1-card-revisit.png`); a direct load of the same URL and a second Back attempt rendered. Could not reproduce.
- N20. Write-back card "Decision" row for the sampled side prints "Xray / Lab" with no label; "Sampled: Not captured before the encounter started" for early-state patients (D34 unchanged).
- Still present from the first report's P2 list, seen in passing: D23 raw ids in toasts and manager names ("cost_s.t._p95_wait", "min_cost" in Play and live Compare selects, while Watch and Trade-off say "lowest cost"); D29 "Read-only while a trained manager is in charge" for tuned heuristics; D30 `space/corridor` 404; D37 studio tabs off-screen at 390 px.

## 4. Things checked that were not in the first report

- **Journey, seed case** (`chest-pain-line-cook`, generic template; triage and reconciliation sampled, physician and handoff played): 46 record entries, each with role, who (you / sampled / AI), stage, turn and source kind. One discrepancy raised (patient's "I don't do drugs" against the previous-visit document) and marked settled after the sampled pharmacist's stage. Debrief reveals the diagnosis only at the end. No hidden-case text in the care plan ("Assembled from 46 entries of the shared record only").
- **Journey, Studio case** (the 74-year-old from N1): works mechanically; the colleague asked three questions and read back. Inherits N1's losses, so "The team found every critical fact" for a case whose INR and haemoglobin never existed.
- **Trade-off side panel for learned managers**: not read (my row-click selector missed); the chart, table and both toggles were.
- **Demo tour**: six steps, each lands in the stated mode with the stated managers (Fixed in Watch; `ppo_min_cost` live in Play; `ppo_min_cost` vs `ppo_min_wait` recorded Compare; `ppo_cost_p95` in Watch; the same pair under flu surge; Trade-off). Kinds are stated correctly in every caption.
- **Watch with learned managers**: `ppo_min_cost` and `ppo_scratch_min_cost` load, play, show decisions ("Providers, day shift: 8 → 4", diversion on/off) and stop at window ends.
- **Compare "Run live", people rendering black (D-black)**: not reproduced. Pane B people were coloured by acuity and role in: default pair on a fresh load; `tuned_min_cost` vs `tuned_min_wait`; after Watch → Compare; after switching hospital in Play and back; a second start in the same page; the tour's Compare step; 1440x900 at 1x and 1600x1000 at 2x, zoomed in five steps, at about 10 s and 25 s into the run (`r2/X-live-*.png`, `r2/K-*.png`). `&gfx=low` was captured only at default zoom. The scene-fix agent was editing `HospitalScene.tsx` during this, so this may be the fix rather than absence of the bug. Not tried: after a structural change redraws the building.
- **Inject**: flu surge, mass casualty, CT outage, nurse call-outs each acknowledged by toast and listed in the Decisions feed at the next hour.
- **Hand-over and back**: see verdict row 3. Saved result after a mixed run: "Run ended … Saved to the server".

## 5. Honesty audit

- Kinds: every manager is labelled Fixed / Rule-based / Random / Tuned heuristic / Learned consistently in Play, Watch, Compare, Trade-off and the Tour. Tuned heuristics carry "a tuned heuristic, not a learned agent" in the API note.
- Learned-agent verdicts on screen match `rl/results/RESULTS.md` for the six I compared (`ppo_min_cost` beats, `ppo_min_wait` matches, `ppo_cost_p95` beats on normal week, `ppo_scratch_min_cost` beats, `ppo_cond_min_cost` beats, `ppo_cond_min_wait` matches). Not checked: whether the verdict shown changes with the scenario (`ppo_cost_p95` beats on normal week and loses under flu surge in `RESULTS.md`). See N8 for the unqualified "beats".
- "SIMULATED" chips on every live or recorded number panel; none in fixture mode. Encounter: "Synthetic patient — for education; needs faculty review", "Offline patient", "Grader: offline heuristics", "Formative coaching … not a validated measure". Write-back card: "All values are simulated. No language model produced or changed any of these numbers." Default results are labelled "(default normal result, synthetic)".
- Hospital disclaimer present on all four hospital modes: "A model built from public information. Not affiliated with or endorsed by Robert Wood Johnson University Hospital … Staff are fictional. All numbers are simulated." Absent from `/encounter`, `/studio`, `/journey` (which name "RWJUH model" in the encounter header when a sim patient is played). Truncated on a phone (verdict row 11).
- Not honest: N3 ("fictional" on a real-profile name); N8; the care plan's "nothing here comes from the hidden case" sits above rows the sampled stages copied from the case verbatim, including the concealed cocaine use recorded as a plain "patient statement" by the sampled pharmacist with no confrontation shown.

## 6. Console and network errors

- No page errors (`pageerror`) in any run.
- `404 GET /api/catalog/ref/space/corridor` x2 (D30).
- `409 POST /api/cases/{id}/approve` x1: the UI's first approve attempt before the acknowledgement; expected.
- `net::ERR_CONNECTION_REFUSED` to `127.0.0.1:8999`: mine, the offline test.
- `net::ERR_ABORTED` on `…&_rsc=` x7: Next.js prefetch cancelled on navigation.
- Warnings on every 3D page: "THREE.Clock: This module has been deprecated", "THREE.WebGLShadowMap: PCFSoftShadowMap has been removed"; on encounter/studio "Skipping auto-scroll behavior due to position: sticky".
- No HTTP 500 and no dev-server breakage during the session, including while the scene files were being hot-reloaded.

## 7. Not tested

- Any language-model path, voice in, speech out: no credentials.
- Cold start timing, `pnpm build` / `pnpm start`, a second dev server (forbidden this round).
- Run expiry (now about 10 minutes); two tabs on one run; fixture auto-recovery when the API comes back.
- Studio structured path end to end; knob boundary logic; structural changes; the hospital switcher beyond one switch and back.
- Write-back for patients picked in the waiting room or waiting for a bay (only one in-triage patient was caught paused); the "rejected" write-back state.
- D17 on people not already selected (blind clicks across the building).
- Journey: the heart-failure template (the builders' own e2e covers it), triage and reconciliation played by hand, narrow layout of a journey in progress.
- Compare at `&gfx=low` zoomed in; Safari and Firefox; a real display's frame rate.
- All timings are scripted, not a human's.

## 8. State left behind

No delete route exists for cases, encounters or journeys, so these remain in `data/encounters/` (gitignored) and are visible in the pickers. Remove before recording:

- Cases created by me: `draft-ruth-calloway-caf16f` (draft), `draft-ruth-calloway-caf16f-8a3ccc`, `draft-mateo-alvarez-a694d4`, `draft-gloria-petrakis-756812`, `draft-chest-pain-bc7ab2`, `draft-samuel-okafor-8d2ac8` (all published), `qa-thin-case-9e9009` (draft), plus `sim-*` cases instantiated from hospital patients.
- Already there before I started, not mine: `draft-infection-fever-s147694-moderate`, `draft-tomas-varga-95b035`.
- Journeys: `jrn-7ca3e31fd7ae`, `jrn-bcf7abebf924`.
- About 25 encounters, one of them unfinished (`enc-eed8497293bb`, the N4 repro; its run will expire on its own).
- The stored human run on the trade-off chart is my last short QA run ("You · not comparable").
- Live runs I started were ended or left to expire; nothing of mine is still running. Both servers were left as found.
