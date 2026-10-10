# Specialty gaps: maternity and NICU flow

Snapshot: 2026-10-10. This batch has nine external records from four source studies: one obstetric triage QI project, one NICU relocation QI project, one multi-center NICU handoff audit, and one Dutch NICU staffing/capacity simulation study. All are labeled `external_reference_not_RWJ`. No values are fitted to distributions, assigned to RWJ, or presented as clinical treatment rules.

| Record | Specialty gap | Evidence retained |
|---|---|---|
| `specialty-mn-ob-triage-wait` | Arrival-to-initial-assessment delay | Pakistan tertiary L&D triage audit, n=200 (100 pre/100 post): share meeting five-minute goal 6% vs 65%. |
| `specialty-mn-ob-triage-stay` | Triage dwell before disposition | Same n=200 audit: pre range 30-240 min; post group 75% at 30 min and 25% at 60 min. This is triage LOS, not labor/delivery or postpartum stay. |
| `specialty-mn-ob-triage-workflow` | Triage roles and onward labor/procedure flow | Same service: 400-500 triage visits/month, >6,000 deliveries/year; post-audit acuity mix and reported nurse assessment, handoff, physician assessment, and routing sequence. The paper's local acuity labels are not reusable clinical criteria. |
| `specialty-mn-nicu-transfer-cycle` | NICU transfer task time by broad acuity | Sidra Medicine's two planned relocations: estimated full prep-to-team-return cycles 15-40 min across three qualitative groups; 34 neonates overall, subgroup denominators unstated. Actual patient movement medians were 4 and 6 min, a different endpoint. |
| `specialty-mn-nicu-staffing-and-move` | Transport staffing and support roles | Two teams moved 17 infants in parallel in 225 and 197 min vs 255 min planned; 57/61 staff survey responses and qualitative requests for added nursing/IT/equipment support. |
| `specialty-mn-nicu-family-transfer` | Family notification and accompaniment | 12 parent respondents after each relocation; all reported being informed and satisfied; one noted inability to accompany. Voluntary survey, not a family-preference estimate. |
| `specialty-mn-nicu-shift-handoff-family` | Family role in routine NICU handoff | 946 observed handoffs at 40 centers over 10 months: family present in 5.9%; of those, 48.2% involved active contribution. Primary abstract only was accessible. |
| `specialty-mn-nicu-operational-capacity` | Physical vs staffed operational beds | Nine Dutch NICUs; 2020 self-reported capacity inputs used in a model. Capacity was 80% of maximum in 50% of observations; site-level no-bed rates averaged 53%, but sites were suppressed. |
| `specialty-mn-nicu-staff-pooling-scenario` | Acuity, staffing availability, network transfer | Nine-site discrete-event/optimization model: transport share 21.53% baseline vs 6.31% with five flex nurses per site/all-site sharing, a modeled ~70% reduction. This is not an observed intervention effect. |

## Interpretation and limitations

The maternity source offers a useful operational decomposition: a brief first screen, assigned nursing roles, acuity-prioritized assessment, a handoff, further assessment, and onward routing. The observed timings are single-site quality-improvement results and do not establish RWJ service times. They should not be used to encode clinical triage thresholds.

The NICU sources distinguish preparation and team return from patient movement time, show that staffed capacity can be tighter than physical bed count, and identify transport teams, bedside nurses, technical standby roles, family communication, and handoff as separate workflow participants. The relocation data are from planned work at a quaternary hospital; the flex-staffing results are simulated for the Dutch network. Neither yields RWJ staffing ratios, transfer probabilities, or discharge rules.

The four inspected sources are linked directly in the JSON records, with publication identifiers, denominators, endpoint definitions, access notes, retrieval time, evidence type, and scenario-use limits. NICU discharge and postpartum length-of-stay distributions remain open evidence gaps; the papers inspected here do not support those local values.
