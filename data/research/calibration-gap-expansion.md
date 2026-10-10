# Timing audit, conditional outcomes and room availability

Three GPT-6 Luna agents researched this pass; the parent inspected selected original sources, corrected extractions and integrated **20 records in 14 additional campaign source catalogs**. Catalogs can repeat studies across campaigns. The workspace now has **169 catalogs and 84,291 normalized record envelopes**, including the large procedure terminology reference. These are not counts of unique hospital facts, RWJ measurements or validated simulation parameters.

## Timing conflicts: what is resolved

| Question | Result | Consequence |
|---|---|---|
| What do Arena LOGN arguments mean? | The Rockwell-authored manual specifies arithmetic mean and SD of the lognormal draw. It is an older manual on a university mirror. | Notation is interpretable; this does not validate any hospital fit. |
| Which Rio triage expression is correct? | Table 7 and Appendix 2 still give different inputs. No correction was found in the bounded search. | Both remain blocked. Do not choose whichever resembles a desired mean. |
| Does Rio contradict itself about all fit p-values passing? | Our earlier claim that its body says all fit-test p-values exceed 0.05 was not substantiated by the English PDF. That extraction claim is withdrawn. | The old records and report are corrected. Ambiguous appendix fit annotations and observed-versus-simulated timing comparisons are separate issues. |
| What does Beirut transport TAT measure? | Its Methods specify cashier order processing to radiographer study initiation. Discussion uses inconsistent shorthand. | Retain the Methods definition with the discrepancy disclosed; this is not total imaging completion or transporter labor time. |

[Timing evidence and source links](calibration-timing.md). Original reported values are preserved; correction links in the earlier records point to this audit. No source correction or author confirmation was obtained for the Rio input conflict.

## What the new data supports

**Conditional case branches.** The selected UK MRI cohort reports 27 occult scaphoid fractures among 208 completed scans. The referral cohort also contains 45 nonattendances and five scans not tolerated among 258 referrals. Those denominators answer different questions. We now retain imaging completion, diagnostic category and subsequent disposition separately. The cohort includes patients aged 12 and older, so it must not be represented as adult-only. Trial outcomes provide separate pathway comparators. [Branch evidence](calibration-branches.md).

**Room timing with explicit endpoints.** We acquired observed daily occupied-room cleaning, ICU terminal-cleaning intervals, and endoscopy timing. The endoscopy cohort distinguishes patient-out to next-patient-in from scope-out to next-scope-in; those intervals must not be added together. Its analyzed cohort excludes long turns, including breaks, which limits use for long-delay simulation. [Room and capacity evidence](calibration-capacity.md).

**Resource capability and schedules.** A UK survey records whether centres offer direct ED MRI for suspected scaphoid injury. HRSA defines staffed beds, and an ACE-unit simulation specifies breaks and huddles. Capability, staffed inventory and model schedules are useful ontology inputs, but none measures the probability that an appropriate room, staff member or scanner is free now. No local available-capacity series was acquired.

**Additional unresolved source problems.** The CT-negative diagnostic abstract reports 15 patients but 16% in a cohort of 100; subgroup percentage wording is also ambiguous. Its quantitative use is blocked. The discharge-nurse abstract reports a relative improvement but gives conflicting turnaround definitions and no absolute duration. That estimate is also blocked. Short primary abstracts remain labeled as abstract-only evidence.

## How these become simulation inputs

All findings have separate [inactive transfer proposals](../knowledge/calibration-transfer-candidates.json). The [adoption contract](../specs/calibration-adoption-contract.json) requires explicit conditioning population, denominator, follow-up window, interval endpoints and resource-capacity basis. External counts are not assigned as local probabilities. No local duration distribution, capacity or probability has been activated.

Next priorities are event-level vacancy-to-ready intervals, actual staff/room/equipment availability over shifts, clinically approved branch selection, and standardized return/follow-up windows. A resolved software convention cannot replace a valid timing fit. Public source research can support an explicitly external scenario, but claiming RWJ calibration still requires representative local evidence and clinical/operational review.

## Human verification

Open [the review interface](../review/index.html) and search **`calibration-`**. Follow each record's source URL or inspected-source URL and precise table/section locator. Compare population, dates, numerator/denominator, units and endpoint before reviewing the proposed scenario use. Export existing decisions before refreshing an already-open interface.

Useful checks:

- `calibration-branches-mri-completion`: compare the original cohort abstract with the 258 referrals and 208 completed scans.
- `calibration-timing-rio-triage-expression-conflict`: compare Table 7 with Appendix 2 in the linked publisher PDF.
- Endoscopy records: compare Table 4 with the Methods' scope/patient endpoint definitions and exclusion criteria.
- `calibration-capacity-terminal-room-turnaround`: compare the Secondary Outcomes definition with the Room Turnaround Time results.

[Parent audit receipt](../workflows/calibration-parent-review.json) describes spot checks; it is not human clinical approval. Rebuild using `build_model_evidence.py`, `build_model_transfers.py` (corrected earlier records), `build_calibration_evidence.py`, `build_calibration_transfers.py`, `build_citations.py` and `build_review_index.py`, then run `bash data/scripts/run-verification.sh`.
