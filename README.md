# HospitalGym

Rutgers Health Hack 2026 · TwinVerse track · 48 hours

A hospital you run like a strategy game, and a reinforcement learning environment where an AI manager learns to run it better than you do.

The hospital is a full simulation: floor plan, beds, staff, patients, money. Every operational input is a knob. You can play it by hand, or train an agent over thousands of simulated days and watch what it builds when you tell it to care about cost, or wait times, or both.

## One hospital, two fidelities

The hospital is a world of entities and the interactions between them: a triage assessment, a doctor seeing a patient, a handoff, a scan, a manager changing the rota.

| | Statistical | Played |
|---|---|---|
| How an interaction resolves | Sampled: a duration from a distribution, an outcome from a probability table | A person plays one side, AI plays the other |
| Used for | Training the manager over thousands of simulated days; running the hospital as a strategy game | Stepping into any one person, e.g. the cardiologist seeing the patient in bay 4, and being graded |
| Result | Duration, information gained, decision, outcome quality | The same four fields, written back into the same simulation |

Every interaction type declares its inputs and outputs once and always has a sampler; any of them can also be given a played version. Each simulated patient carries a hidden truth (condition, severity, the facts a clinician could discover) that the sampler draws from and that the played version turns into an interview case, so the patient you question is the patient in the bed.

The played clinician-patient encounter is what the TwinVerse brief asks for: a faculty-authored patient, a split-screen interview with a progressively revealed chart, and evidence-linked feedback.

## The look

Industrial software that feels like a strategy game: a 3D isometric hospital you can orbit and zoom, people walking between rooms, queues you can see forming, a clock you can speed up, and panels that slide in when you click a room or a person. Built with Next.js and React Three Fiber.

Three modes on the same scene:

- **Play.** You are the manager. Hire, schedule, move rooms, set policies, hit fast-forward.
- **Watch.** A trained agent runs the hospital. Its decisions show up as they happen.
- **Compare.** Same seed, same demand, two managers side by side: you vs the agent, or the cost-tuned agent vs the wait-tuned agent.

## The simulation

A queueing-network model of a hospital, advanced in fixed ticks.

**Entities**

- Patients: arrival time, acuity, condition group, payer, a care pathway (the sequence of resources they need), a patience limit, and a deterioration risk that grows while they wait
- Staff: role, skill, shift, wage, fatigue
- Spaces: type (triage, bay, imaging, OR, ward bed, pharmacy), capacity, position on the floor plan
- Equipment: scanners, monitors, and their downtime

**Dynamics**

- Arrivals follow time-of-day, day-of-week, and seasonal patterns, with random surges (flu wave, mass-casualty event)
- Service times are random and depend on acuity, staff skill, and fatigue
- Walking time between spaces comes from the floor plan, which is how layout matters
- Patients who wait too long leave without being seen or get sicker
- Staff call out sick, burn out under sustained overtime, and quit

**Money**

- Revenue per case by condition group and payer
- Costs: wages, overtime, agency staff premium, supplies, fixed cost per bed and per room, a one-off cost for moving or building anything

## The RL problem

One agent, one long episode, decisions at several timescales.

**Episode.** Up to 1000 simulated days. The environment step is one hour; within a step the simulation runs at finer grain.

**Actions, by cadence**

| Cadence | Decisions |
|---|---|
| Hourly | Who is seen next, where staff are assigned, open or close overflow bays, divert ambulances, call in extra staff |
| Daily | Next-day staffing per role per shift, elective case schedule, admission cap |
| Weekly | Rosters, agency contracts, clinic hours |
| Monthly or quarterly | Hire and fire, buy equipment, add or remove beds, relocate a bay or department |

Slow actions are masked out except at their boundary. Structural changes carry a switching cost and take time to complete, so layout is a real sequential decision rather than a parameter: the agent has to decide whether closing a bay for two weeks is worth what it gets afterwards.

**Observation.** Queue lengths and wait times by area, bed occupancy, staff on shift and fatigue, time of day and calendar position, recent demand, cash position, the current layout, and the reward weights (see below).

**Why one agent for everything.** Splitting it into "optimize the layout offline, then learn a dispatch policy" misses the interaction between them. The best layout depends on how you staff and dispatch, and the reverse. A single agent acting across timescales can learn that a smaller ED with a sharper diversion policy beats a bigger one.

**What makes that hard, and how we handle it**

- *Slow actions get little signal.* A thousand-day episode contains thousands of dispatch decisions and about ten layout decisions. The answer is throughput: the simulator has to be fast enough to run hundreds of episodes in parallel.
- *Long horizons.* A hire pays off over months. We train on a curriculum, starting with 30-day episodes and fixed structure, then unlocking slower actions and longer horizons.
- *Big action space.* Factored action heads (one per decision type) with masking, rather than one flat choice.

## Metrics and reward

Tracked every step:

- Access: mean and 95th percentile wait, left without being seen, ambulance diversion hours
- Flow: length of stay, bed occupancy, boarding time
- Safety: deteriorations while waiting, adverse events, readmissions
- Staff: utilization, overtime, burnout, turnover
- Money: revenue, cost, margin, cost per case

The reward is a weighted combination, and the weights are an input to the agent rather than a fixed design choice.

- **Preset policies.** Train one agent per objective: minimize cost, minimize wait, maximize margin, protect staff, balanced. This is the reliable version and what the demo is built on.
- **Constrained objectives.** "Lowest cost subject to 95th percentile wait under 30 minutes" is closer to how a hospital actually thinks than any weighted sum. The constraint gets a penalty weight that rises whenever it is violated.
- **One agent, a dial.** The weights are part of the observation and are resampled each episode, so a single policy learns the whole trade-off surface. In the demo this is a slider. Stretch.

## The demo

1. Fly over the hospital on a normal Tuesday. Queues are fine.
2. Hand it to the cost-tuned agent and fast-forward a year. It has cut night staff, closed a bay, and waits have tripled. The margin looks great.
3. Same seed, wait-tuned agent. Staffed to the ceiling, nobody waits, and it is losing money.
4. Constrained agent: cheapest hospital that keeps waits under 30 minutes. It moved triage next to imaging and staggers shifts around the evening peak.
5. Throw a flu surge at all three and watch which ones break.
6. Trade-off chart: every trained policy as a point on cost against wait, with the human player's run on the same axes.

The point of steps 2 and 3 is that the agent does exactly what you ask for, which is why the choice of metric is the real decision.

## Grounding in data

The hackathon's Vlada data covers the money and scale side well:

- Hospital Cost Reports (HCRIS): cost by department
- Provider of Services file: bed counts by hospital
- Medicare inpatient and outpatient rates (IPPS, OPPS): revenue per case
- Maryland all-payer rates and volumes: monthly volume per hospital and cost center, which gives seasonality
- HCAHPS and the readmissions program: outcome and experience benchmarks

It does not cover patient flow. Hourly arrival curves, service-time distributions, and walking times will come from published emergency department literature and stated assumptions. So the costs can be anchored to a real hospital, and the flow dynamics are plausible rather than measured. Results show how the trade-offs behave; they are not recommendations for a specific hospital until calibrated on its own flow data.

## Architecture

```
 Next.js + React Three Fiber
 3D hospital · knobs · charts · play / watch / compare
              │  websocket: state snapshots, actions
              ▼
 FastAPI server ── runs one live simulation for the viewer
              │
              ▼
 Simulator core (Python, NumPy, vectorized over many hospitals)
   same code serves the viewer and the trainer
              │
              ▼
 Gymnasium environment ── PPO with masked, factored actions
              │
              ▼
 Saved policies + recorded rollouts for instant replay
```

- The simulator is written once, as array operations over a batch of hospitals, so training runs hundreds of copies at once and the viewer runs a batch of one.
- Rollouts are recorded as state snapshots. The demo can replay a year in a minute without running inference live, which also protects against anything breaking on stage.
- Baselines sit behind the same interface as the agent: fixed staffing with first-come-first-served, and a sensible rule-based manager. An RL result means nothing without them.

## Build order

1. **Simulator core.** One emergency department: arrivals, triage, bays, doctors and nurses, discharge. Metrics out. Verified against known queueing results.
2. **Viewer.** 3D scene driven by simulator snapshots. Clock, speed control, click for detail.
3. **Play mode.** Staffing and policy knobs wired to the live simulation.
4. **Gym wrapper and baselines.** Hourly and daily actions only. Rule-based manager as the bar to clear.
5. **First trained agents.** Cost preset and wait preset on 30-day episodes. Compare mode.
6. **Slow actions.** Weekly and structural decisions with switching costs; longer episodes.
7. **Constrained objective and trade-off chart.**
8. **Money calibrated from Vlada data.**
9. **Stretch:** weight-conditioned single agent with a slider; more departments; the link to the encounter sim.

Steps 1 to 5 are a complete demo. Training starts as early as step 4 and runs in the background while the front end is built.

## Stack

- Frontend: Next.js, React, TypeScript, React Three Fiber (three.js), a charting library
- Backend: Python, FastAPI, websockets
- Simulation: NumPy, exposed as a Gymnasium vector environment
- RL: PPO via CleanRL or Stable-Baselines3 with action masking
- Compute: AWS credits for training runs
