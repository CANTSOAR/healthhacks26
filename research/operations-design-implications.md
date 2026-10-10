# Operations research: design implications for the simulator and RL workstreams

Status: **v3 (2026-10-10, about 01:45).** Record numbers `[E-n]` point at
[operations-evidence.md](operations-evidence.md) (78 records covering about 90 sources, every one fetched and read); machine-readable
ranges are in [operations-parameter-ranges.yaml](operations-parameter-ranges.yaml). Numbers marked *derived*
were computed by the research agent from a published table; they are approximations, not published estimates.
Catalog values already changed are listed at the end.

## The five that matter most

1. **Patience was about five times too short.** Observed LWBS at real waits implies exponential patience means
   near 3,500 / 1,150 / 1,600 / 1,000 minutes for ESI 2-5, and ESI 1 never leaves [E-01]. Baseline LWBS should land
   near 2-3% for a typical ED and 7% for a crowded 95,000-visit ED [E-02][E-03].
2. **Harm comes from boarding, and it has a clock.** Mortality for admitted patients rises linearly from 5 to 12
   hours after arrival, one extra death per 82 patients held past 6-8 hours [E-15]. Crowding lengthens waits and
   boarding but not treatment time [E-21]. An ED model without inpatient beds and discharge timing cannot
   reproduce crowding [E-23][E-34].
3. **RL lost to simple index rules by about 50x on the one realistic hospital benchmark** (PPO variants 2.3e4-2.5e4
   mean queue versus 4.4e2 for c-mu and MaxWeight) [E-35]. What made PPO work elsewhere: never idle a server with
   an eligible patient waiting (mask it out), warm-start from a heuristic, discount near 0.998 with big batches
   [E-35][E-36][E-37]. Keep a strong tuned heuristic and report the comparison honestly.
4. **Learned policies only separate from heuristics under overload.** At normal load DQN dispatch equalled
   acuity-weighted rules; it won only when arrivals rose [E-39][E-41]. Evaluate on surge scenarios and at
   utilisation above about 0.9.
5. **A queueing-formula staffing rule is the baseline to beat**: matching provider hours to the lagged arrival
   curve cut LWBS 21.7% with no extra hours [E-33]; and physicians pick up about 3 new patients in their first hour
   but 1.3 by mid-shift [E-08], so shift start times are a lever in their own right.

## Simulator

**Leaving without being seen (LWBS)**

- Table to reproduce: ESI 2/3/4/5 waited 1.0/1.9/1.3/1.3 hours on average and 1.7%/9.5%/4.7%/7.4% left; ESI 1
  never left [E-01]. The Wave 0 placeholder (240-minute patience for ESI 3) would lose about 38% at that wait.
- Patience is not only a function of own wait. One more person visible in the waiting room adds about 0.5
  percentage points for ESI 3 (worth 15-25 minutes of waiting); a sicker patient arriving adds about 1 point; a
  test ordered at triage removes 1.8 points [E-01]. Suggested hazard:
  `h = (1/patience_acuity) * (1 + 0.05 * waiting_room_census) * (0.3 if ambulance)`, using the 5% per person and
  0.29 ambulance odds ratios from [E-02].
- Shape against wait: odds 1.34 / 1.69 / 1.87 / 1.99 at door-to-provider 30-59 / 60-89 / 90-119 / 120+ minutes
  versus under 30; it flattens after 90 minutes [E-02]. Each boarder adds 2% to the odds [E-02].
- Outcome of leaving: in a US system, leavers had 2.59 times the 30-day mortality odds of discharged patients and
  2.56 times the 72-hour return odds [E-05]; in Ontario no excess harm was found [E-09]. Count LWBS in the safety
  term and let a share return as new arrivals.
- Checks: days with mean door-to-room under 20 minutes should have LWBS under 1% about 88% of the time, and about
  a third of the time above 35 minutes [E-04].

**Harm from waiting and boarding**

- Deterioration: the only measured rate is for admitted patients boarding in the ED: 3.6% escalated to
  intermediate or intensive care within 48 hours (45% of them while still in the ED), median boarding 10-12
  hours, +2.4% relative risk of in-ED deterioration per extra boarding hour, and 28-day mortality 13.0% after a
  deterioration versus 3.9% [E-68]. *Derived* hazard about 0.003 per hour for ESI 2 and 0.001 for ESI 3 (now in
  the catalog); nothing exists for the waiting room or for ESI 1, 4 and 5, which stay assumed. A deterioration
  should multiply that patient's death risk by about 3.
- Deaths per waiting hour, *derived* and confounded: about 0.0015 for ESI 2 (admitted-patient figures: 2.5% to
  4.5% mortality from under 2 to over 12 boarding hours [E-16]; 1 in 82 past 6-8 hours [E-15]), 0.0005 for ESI 3,
  0.00004 for ESI 4-5 (discharged patients: one hour less mean stay avoids 6.5% and 12.7% of 7-day deaths [E-09]).
  ESI 1 stays assumed. Label these "attributable deaths, literature-scaled", never a forecast.
- Boarding lengthens the inpatient stay: +55% from under 2 to over 24 hours unadjusted [E-16]; +20% for an 8-hour
  ED stay [E-20]; rate ratio 1.20 for an overnight ED stay at age 75+ [E-18]; only +0.8% in the adjusted
  multi-hospital analysis [E-19]. Catalog now 1% of stay per boarding hour (range 0.1 to 2.5%).
- Older patients take most of the harm: in-hospital mortality 15.7% vs 11.1% after a night in the ED at 75+
  [E-18]. Scale the boarding hazard up for the 65+ band.
- Error and quality: preventable errors are about twice as common in the top crowding quartile and flat below it
  [E-22]; cardiac arrests rise only past extreme occupancy [E-69]; use a threshold, not a linear penalty.
- Hallway overflow spaces: patients are placed 18 minutes sooner, but those who go home stay about two hours
  longer (+123 minutes); admitted patients are unaffected [E-76]. Model overflow as faster start, slower finish.
- Diversion: 12 or more hours of diversion in a day is associated with +3.2 points 30-day mortality for heart
  attack patients; below 12 hours no difference [E-32]. Diversion barely improves waits [E-31]. Penalise diversion
  hours with a threshold near 12 a day.

**Arrivals**

- Non-homogeneous Poisson with day-level overdispersion: variance-to-mean of daily totals about 1.5 [E-06];
  within an hour, variance is about equal to the mean and there is no leftover autocorrelation [E-07]. Draw a daily
  multiplier (gamma, mean 1, CV about 0.06 at 130 arrivals a day; *derived*) and then Poisson by hour.
- High- and low-acuity patients have different hourly profiles [E-07]; a single shared profile is an
  approximation worth flagging.
- Low-acuity volume is not what crowds the ED: 10 extra low-complexity arrivals per 8 hours add 5.4 minutes to
  everyone else's stay [E-30].

**Service**

- Provider time per patient by ESI: 76 (SD 42) minutes for levels 1+2, 48 (27) for level 3, 27 (15) for level 4,
  18 (11) for level 5; 31 for specialists against 47 overall [E-10]. CV is 0.55 to 0.61 at every level: keep
  lognormal with CV 0.6. The Wave 0 placeholders (initial + re-evaluation = 65/45/30/17/11) already sit close to
  the specialist-scaled figures (50/50/32/18/12).
- Pickup rate by hour of shift (new patients per hour, intercept plus hour effects): 2.97, 1.97, 1.57, 1.36, 1.30,
  1.28, 0.97, 0.41 at one site; first hour 2.2 to 3.0 across sites; each extra arrival adds 0.12 to 0.42 [E-08].
  Residents show the same decline from 2.14 in the first hour [E-73].
- Relative productivity (*derived*, attending = 1 at about 2.0 patients an hour): residents 0.6 (first year 0.45,
  second year 0.85), advanced-practice providers 0.78 [E-73]. Consecutive shifts, including nights, did not
  reduce resident productivity [E-73]: do not carry a speed penalty from one day to the next.
- Labs: order-to-result median 51 minutes (IQR 41-65), central lab 79 (SD 34) in a second ED [E-75]. Cutting
  result time by 51 minutes with point-of-care testing shortened ED stay by only 9 (not significant) [E-75]: if
  faster labs produce big gains in the simulator, something else is too loose.
- Nursing time rises steeply with acuity: about +97 minutes of direct care for triage level 1 and +30 for level 2
  against level 3, -22 and -25 for levels 4 and 5; about 45 nurse-minutes per patient present [E-77].
- Total ED stay: mean (median) 6.3 (4.7), 3.9 (2.8), 2.2 (1.6) hours for high, medium, low complexity [E-30];
  mean-to-median ratios imply a lognormal CV near 0.9-1.0 (*derived*). Use as a shape check on simulated stays.
- Triage error: 32.2% mis-triaged (28.9% over, 3.3% under); a third of patients needing a life-stabilising
  intervention were not ESI 1-2 [E-11]; undertriage costs 18 to 33 minutes on key orders [E-12]; 3% to 45% of
  admitted patients were triaged to levels 4-5 [E-13].
- Imaging: order-to-completion medians, CT 72 (IQR 40-129) and 108 (57-182) minutes at two EDs, radiography 31
  (19-48); completion-to-report 74 (35-127) [E-57][E-58]. Use these as validation targets for the whole imaging
  path (queue + transport + scan), not as the scan duration.
- Bed turnaround on wards: 65-70 minutes when well run, 115-130 when not [E-61][E-62].

**Levers and the effect sizes to reproduce**

| Lever | Effect in the literature | Record |
|---|---|---|
| Fast track for low acuity | wait -51 min, stay -28 min, LWBS -4.06 points, no change in mortality or revisits, census rising | E-24, E-25 |
| Physician at triage | stay -37 min (2 RCTs), time to physician -30 min, LWBS RR 0.82 (RCT) and 0.62 (12 US studies); effect on stay from -82 to +20 min | E-26, E-27 |
| Nurse practitioner or extended-role nurse at triage | shorter stay in 29 of 30 studies, lower LWBS in 8 of 10 | E-28 |
| Vertical split flow / results-waiting chairs for ESI 3 | stay 283 to 251 min with no added staff or space | E-29 |
| Staff to the lagged arrival curve | LWBS -21.7% at constant provider hours | E-33 |
| Earlier inpatient discharges | discharge peak 4 hours earlier removed ED boarding (77 boarding-hours a day to 0-3) in a flow model | E-23 |
| More ED nursing hours | bottom vs top quartile of nurse-hours: +28.2 min stay for discharged patients, +9 LWBS a day | E-51 |
| Scribes | +15.9% patients per doctor-hour, median stay -19 min, no change in door-to-doctor (randomised) | E-74 |
| Point-of-care lab testing | time to results -51 min, stay -9 min (not significant; randomised) | E-75 |
| Hallway overflow spaces | placement -18 min, stay +123 min for discharged patients | E-76 |
| Ward nurse ratio | each extra patient per nurse: +7% mortality odds, +23% burnout odds | E-50 |
| Ambulance diversion | minimal effect on waits; harm past 12 hours a day | E-31, E-32 |
| Smoothing elective surgery, holding unit for boarders | reduce diversion "considerably" in simulation studies | E-31 |

**Staff**

- Ratios: California law is 1:4 in the ED, 1:2 for ED critical care, 1:1 RN for trauma, 1:2 ICU, 1:3 step-down,
  1:4 telemetry, 1:5 medical/surgical, with no averaging over a shift [E-48]. New Jersey has a bill with the same
  ED numbers, not a law [E-49]. Model as a soft constraint with a penalty.
- Turnover 18.5% a year all hospital staff, 17.6% RNs, about 20.7% ED RNs; $60,090 to replace a bedside RN;
  about 78 days to recruit an experienced RN (70 for ER nurses), so a hire decided today arrives in roughly ten
  weeks; travel nurses bill $91.23 an hour against $59.46 loaded staff cost (1.53x loaded, 1.93x base wage)
  [E-55]. Absence: 2.1% of scheduled hours for clinical staff [E-56].
- Fatigue: error multiplier 1.36 (observed, 24-hour shifts) to 3.5 (self-reported) [E-52][E-53]; for nurses the
  trigger is shifts past 12 hours, overtime, and weeks past 40 hours [E-54]. Accumulate fatigue on overtime rather
  than on ordinary busy hours.

**Events**

- Flu: 8.0% of ED visits coded influenza at the peak week of a severe season, above baseline for 10+ weeks
  [E-63]; coded cases understate attributable visits several-fold and LWBS rises among non-flu patients [E-64];
  about a quarter of diversion in flu seasons is attributable to flu [E-65]. Catalog: arrival x1.10, respiratory
  share +0.08.
- Mass casualty: one hospital received 40 patients, median 97 minutes after the blast (IQR 43-139), 25% needing
  emergency surgery, 40% admitted [E-57]; in Las Vegas 2017 hundreds self-transported with no warning or field
  triage [E-66]. Catalog: 40 patients over 180 minutes; make arrival mode mostly walk-in for the shooting variant.

**Validation recipe from published ED simulations**

- Calibrate on one period and validate on a later one; compare series for waiting count, occupancy, stay,
  boarding count and time; report correlation and bias [E-42]. Expect to match averages within 10% and not
  individual patients [E-43].
- Check queueing identities before trusting any policy comparison: Little's law, utilisation under 1 with finite
  beds, blocking actually occurring. A published ED twin turned out to have no capacity blocking and an impossible
  equity score, found only by these checks [E-41].

## Reinforcement learning

- **Baselines to include:** FCFS with urgency override (the status quo in most EDs [E-71]); acuity-weighted
  waiting-time index rule (it matched DQN at normal load [E-39]);
  c-mu and MaxWeight for bed and provider assignment [E-35]; queueing-formula staffing by hour [E-33].
- **Action design:** mask actions that idle a resource while an eligible patient waits [E-35][E-36][E-37]; split
  multi-patient assignments into sequential single-patient choices [E-38]; give capacity actions a delay before
  they take effect [E-40]. A low-risk alternative for the hourly head: let the agent pick which known
  prioritisation rule to apply this hour (an index into a table of sorting rules). An A2C/PPO agent doing exactly
  that on a validated ED simulation cut mean stay 8% and median stay 17% against the hospital's own rule [E-70].
  Imitating an offline optimiser's solutions is another route (stay -5% normal load, -11% heavy) [E-71].
- **Observation:** queue length and patients in service per class, planned discharges per ward, hour of day
  [E-38]; waiting-room census and boarders (they drive LWBS) [E-02]; hospital and ED occupancy together [E-17].
- **Reward:** dense per-step cost. Used successfully: holding cost per waiting patient per epoch plus a one-time
  cost per off-service placement [E-38]; acuity-weighted waiting time (acuity 1 weighted 30x) with a penalty when
  acuity 1-2 exceed a threshold wait [E-39]; distance from a target reserve of free staffed beds [E-40]; a
  per-patient piecewise-linear penalty that steps up past a target time to first assessment (0/15/60/120/240
  minutes for severity 1-5) and past a maximum stay, **clipped per patient** because unbounded penalties
  destabilised training [E-70]. No paper that worked used a sparse end-of-episode reward.
- **Reward gaming seen in practice:** with stay-based reward and no harm-from-delay term, agents learned to hold
  new patients back when the department was saturated; most were seen faster but a minority much later [E-70].
  HospitalGym's LWBS and deterioration terms are what price that behaviour; check the tail of time-to-provider,
  not only the mean.
- **Training settings that worked on queueing networks:** discount 0.998, GAE lambda 0.99, 50 actors x 50,000
  steps per iteration, 3 epochs, whole-rollout policy batch, reward and advantage normalisation, cosine learning
  rate from 9e-4 (policy) and 3e-4 (value) [E-35]; long-run-average formulation with variance reduction [E-37];
  policy trunk shared across hours with a per-hour output layer, linear critic on queueing features, which cut
  data needs 100x [E-38].
- **Warm start:** behaviour-clone a MaxWeight-style policy (servers to queues with probability proportional to
  exp(queue length)), then fine-tune [E-35].
- **Where RL gains are larger:** non-exponential service times (10% vs 21% improvement) [E-35]; heavy traffic
  [E-39][E-41].
- **Presentation:** a cost-versus-wait Pareto frontier per policy family is an established way to show the
  trade-off [E-44].
- **Vectorised simulators:** QGym (batched GPU, Gym interface) [E-35] and a differentiable discrete-event
  simulator with pathwise gradients 50-1000x more sample-efficient than REINFORCE [E-36] are the precedents; SimPy
  wrappers run one hospital per process [E-40].

## Encounter (short)

- Item-level rubric scoring from transcripts reached kappa 0.88 with human graders on one observable item across
  2,027 OSCEs [E-45]; an LLM scorer told weak from adequate but not adequate from good, and prompt wording moved
  score error from 29.8% to 6.1% [E-46]. Keep deterministic evidence-linked checks primary and report agreement
  per rubric item.
- A knowledge-graph-grounded simulated patient answered 94.15% of record questions correctly [E-47]: grounding in
  a fact store works, with a residual error of several percent, so log the fact IDs behind every reply.

## Catalog values changed by this workstream

| File | Attribute | Old | New | Record |
|---|---|---|---|---|
| patient | `lwbs_patience_min` | 600, 480, 240, 150, 120 | 100000, 3500, 1150, 1600, 1000 | E-01 (derived) |
| patient | `death_hazard_per_hour_untreated` | 0.01, 0.0008, 5e-5, 0, 0 | 0.01, 0.0015, 0.0005, 4e-5, 4e-5 | E-09, E-15, E-16 (derived; ESI 1 still assumed) |
| patient | `deterioration_hazard_per_hour_waiting` | 0.02, 0.008, 0.002, 0.0004, 0.0001 | 0.02, 0.003, 0.001, 0.0004, 0.0001 | E-68 (derived; ESI 1, 4, 5 still assumed) |
| patient | `boarding_los_penalty` | 0.02 | 0.01 | E-16, E-18, E-19 |
| staff | `rn_patients_per_nurse_max` | 4 (assumed) | 4 (regulation) | E-48, E-49 |
| staff | `annual_turnover` | 0.18 | 0.185 | E-55 |
| staff | `absence_rate` | 0.035 | 0.021 | E-56 |
| staff | `fatigue_error_multiplier` | 2.0 (assumed) | 2.0 (range 1.36-3.5) | E-52, E-53 |
| staff | `attending.patients_per_hour_by_acuity` | 0.5, 0.9, 1.6, 2.6, 3.2 | 0.8, 1.2, 1.9, 3.3, 5.0 | E-10, E-08 (derived) |
| staff | `resident.productivity` | 0.65 | 0.6 | E-73 (derived) |
| staff | `app.productivity` | 0.8 | 0.78 | E-73 (derived) |
| staff | `agency_premium_multiplier` | 2.0 | 1.93 | E-55 (derived) |
| staff | `benefits_load` | 1.28 | 1.258 | E-55 |
| space | `walk_speed_m_per_min` | 70 | 80 | E-67 |
| space | `ward_unit`, `stepdown_bed`, `icu_bed` `turnaround_min` | 45, 45, 60 | 68, 68, 68 | E-61, E-62 |
| equipment | `ct.result_delay_min` | 40 | 74 | E-57 |
| equipment | `ct.failure_prob_per_hour` | 0.004 | 0.001 | E-60 (derived, one scanner) |
| equipment | `lab_analyzer.procedure_min` (and its `dist`) | 45, cv 0.4 | 54, cv 0.35 | E-75 (derived) |
| event | `flu_wave.arrival_multiplier` | 1.25 | 1.10 | E-63 (derived) |
| event | `flu_wave.respiratory_share_uplift` | 0.12 | 0.08, then replaced by the data workstream's measured 0.0413 | E-63 (superseded) |
| event | `mass_casualty.extra_patients` | 35 | 40 | E-57, E-66 |
| event | `mass_casualty.window_min` | 90 | 180 | E-57 (derived) |

If the simulator was tuned against the old patience values, LWBS will drop sharply after this change; that is
the intended correction, and waits will now need to be long before patients leave.

## Still assumed (no usable source found)

Deterioration hazard in the waiting room and for ESI 1, 4, 5; ESI 1 untreated death hazard; ED bay cleaning
time; stretcher transport speed; failure and repair for MRI, X-ray, ultrasound, monitors, ventilators, analysers;
scan durations; nurse minutes per patient-hour; fatigue effect on speed; hallway quality penalty; mass-casualty
acuity mix; call-in delay; staff absence multiplier during flu.
