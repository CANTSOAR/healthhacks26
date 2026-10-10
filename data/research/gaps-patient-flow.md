# Patient-flow evidence gaps: admission, cleaning, transfers, and discharge

Snapshot: 2026-10-10. This is an external-source acquisition batch, not a description of RWJUH operations. All nine records carry `applicability_label: external_reference_not_RWJ`; no local patient-flow durations or policies are asserted.

## Coverage and use

The batch contains nine records across five sources: four original studies and one official UK government hospital-discharge guide. It adds observed timing anchors for ED admission-to-bed flow, isolation-room turnover, task/staff time during internal transfers, and discharge delays. The guidance supplies a qualitative transition map for social work, care coordination, rehabilitation, and community/care-home placement.

Observed measures retain their denominators, setting, dates or stated date limitations, and endpoint. Means remain means and medians remain medians; no fitted or invented distributions are implied. Staff labor minutes are distinct from patient elapsed time. Percentages of discharge-delay reasons can overlap. The source-specific results are candidate external scenario references and require local workflow confirmation and calibration.

## Records

| Record | Gap covered | Evidence |
|---|---|---|
| `gap-flow-admission-cycle` | Admission, bed assignment, ward arrival | KFSHRC adult ED admissions: median EHR admission-order-to-bed-arrival cycle 390 min at baseline vs 175 min post-bundle; n=217 and n=218. Single-center pre/post QI association; component effects cannot be separated. |
| `gap-flow-admission-delay-causes` | Bed readiness and receiving-unit acceptance | In the same study, the baseline Pareto counts were 31, 31, and 24 monthly delay events. Receiving-unit delay and bed-not-ready together accounted for 77–81% in Jan–Feb and about 71% in March; event counts are not patient counts or time shares. |
| `gap-flow-room-turnover-isolation` | Environmental cleaning / bed turnover | Cincinnati Children's isolation-room median discharge-to-UV-completion turnover fell 130 to 65 min (ranges 93–294 and 48–95); the accessible abstract does not report the manual-observation denominator. This is an isolation-plus-UV endpoint. |
| `gap-flow-room-cleaning-duration` | Active EVS task vs post-clean waiting | The same study reports median cleaning and curtain-changing task time 57 to 37 min; it separately reports cleaning-complete-to-UV-start waits of 36 to 8 min. Do not equate active cleaning with total bed unavailability. |
| `gap-flow-intrahospital-transfer-staff-time` | Inter-unit transfer labor and handoff | Direct observation of 50 transfers at a 718-bed Level I trauma hospital: mean 77 staff-minutes per transfer, including 53 RN-minutes. Multiple workers overlap, so these are labor sums rather than elapsed patient journey times. |
| `gap-flow-intrahospital-transport-segments` | Patient movement, room setup, elevator effects | Table 3 reports patient movement mean 9.3 (SD 6.4) min, n=50. Regression results report 50 vs 89 all-staff minutes without/with elevator use and 27 vs 65 RN-minutes. Elevator subgroup denominators are unstated in the cited passage. |
| `gap-flow-tbi-discharge-delay-duration` | Discharge readiness to actual discharge | Four-center adult TBI cohort (n=1,543; 2015–2018): 210 patients (14%) had a delay of at least 24h after case-management readiness; median delay among delayed patients was 3 days. Conditional TBI/trauma-center result, not a general discharge distribution. |
| `gap-flow-tbi-discharge-blockers` | Authorization, placement bed, family/social coordination | Among delayed TBI patients, insurance processing/authorization was reported for 52%, no accepting bed for 41%, and patient-related barriers for 34%; reasons may overlap and must not be normalized to 100%. |
| `gap-flow-discharge-to-rehabilitation-pathways` | Social work, care coordination, rehab and placement transitions | Official England guidance describes early planning from admission, needs assessment, multidisciplinary/care-transfer-hub coordination, vacancy checks, and four discharge-to-assess pathways spanning home, home with support, bed-based intermediate rehabilitation, and new residential/nursing placement. It is a workflow reference, not a local policy or timing study. |

## Source notes and limitations

1. **KFSHRC admission-cycle QI study.** [Primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC13310080/). Adult ED-to-inpatient admissions, Jan–Aug 2023. The reported cycle was measured in EHR timestamps from admission order to arrival in inpatient bed. Its improvement package included upstream bed decisions, handoffs and COVID testing changes. This is a single-center pre/post project, not a causal estimate or RWJ benchmark.
2. **Isolation-room turnaround QI study.** [PubMed record and full abstract](https://pubmed.ncbi.nlm.nih.gov/31345277/), DOI [10.1017/ice.2019.199](https://doi.org/10.1017/ice.2019.199). Quaternary pediatric referral facility; 60-day before/after improvement work. The accessible abstract includes medians and ranges but not the observation counts or exact calendar dates. Full publisher text was not accessed in this batch.
3. **Intrahospital transfer observation study.** [Primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12715022/). Fifty complete transfers observed at a 718-bed Level I trauma hospital; five observations excluded and seven pilot observations excluded. Observation ended when the origin nurse returned. It measures work across multiple staff, not simply patient trip duration. Observation calendar window is not stated in the inspected full text.
4. **TBI discharge-delay multicenter study.** [Primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC6945617/), DOI [10.1186/s12873-019-0233-7](https://doi.org/10.1186/s12873-019-0233-7). Four Level I trauma centers; adults with TBI and ISS ≥9, Jan 2015–Mar 2018. Delay was discharge ≥24h after case management noted readiness. Results apply to that cohort and regional post-acute setting.
5. **Hospital discharge and community support guidance.** [Official GOV.UK source](https://www.gov.uk/government/publications/hospital-discharge-and-community-support-guidance/hospital-discharge-and-community-support-guidance). Sections 5–6 and Annexes A–C describe roles, early planning, discharge-to-assess pathways, multidisciplinary coordination, social work and bed availability. It applies in England and provides no observed time values.

## Remaining acquisition gaps

- No source in this batch estimates a general adult med/surg routine-cleaning distribution or a target-hospital EVS queue by shift. Isolation-room values include specialized disinfection and cannot fill that gap.
- The admission QI source records a bed-assignment sequence and overall cycle endpoint, but does not provide defensible generalizable distributions for request-to-assignment, assignment-to-EVS-start, EVS completion-to-ready, or ward acceptance individually.
- The transfer observation study covers internal room/unit moves but its observation window and elevator subgroup denominators are not available in the inspected passage; transport labor cannot stand in for elapsed transport response time.
- Discharge studies provide selected cohort delay durations and reasons, not task-level social-work minutes, referral acceptance distributions, rehab-bed wait distributions, or current New Jersey placement capacity.
- All local staffing, shift coverage, handoff, transport, EVS, bed-control, authorization, rehab-placement, and discharge workflows remain unknown pending direct local evidence and human review.
