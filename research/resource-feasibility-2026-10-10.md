# Resource access and execution assessment

Observed October 10, 2026, shortly after midnight EDT. This assessment compares `action-plan.md` with the visible ChatGPT conversation **Hospital Simulation Action Plan**, including its encounter, operations, and hospital-world releases. It distinguishes a listed capability, observed account access, successful execution, and delivered software. Recommendations below are engineering judgments, not sponsor requirements or measured completion probabilities.

## Decision

The resources support building the complete text-based Challenge 1 prototype: generic faculty case creation/review/approval, an encounter with progressive chart and attachments, and evidence-linked formative feedback. Completion still depends on implementation, reviewed cases, and a working application provider route. A small illustrative ER map or 3-D room is a reasonable extension after the core passes. The resources do not yet support an accurate RWJUH operational digital twin or full interior reconstruction.

The checked local repository contains research documents and private preparation material, with no application implementation visible. The checked workshop services likewise contain no project API or S3 bucket. This does not establish what other teammates have built elsewhere.

## Observed resources

| Resource | Evidence observed | Execution implication / remaining gate |
|---|---|---|
| AWS Workshop Studio | Active event dashboard under the participant's signed-in session; console opens as `WSParticipantRole/Participant` | Actual console access is established. Project deployment and service creation permissions were not exercised. |
| Regions and lifetime | Dashboard lists `us-west-2` and `us-east-1`; start October 9 at 6:43 PM, duration 72 hours; countdown approximately 2 days 18 hours at inspection | Display implies an event end on October 12 at 6:43 PM in the dashboard's timezone. Confirm exact timezone and resource teardown/persistence with AWS mentor; export before expiry. This is separate from the Sunday submission cutoff. |
| Bedrock models | Playground's Amazon provider groups Nova Pro 1.0, Nova 2 Lite, Nova Lite 1.0, Nova Micro 1.0, and Sonic variants under “Models with access” | Supports an Amazon-model integration candidate. Listed access is not proof of a successful application invocation or model suitability. |
| Bedrock quota | Nova Micro Geo cross-region row shows 8M TPM and 4K RPM | Listed capacity is ample for a small demo. Budget, IAM/SCP restrictions, inference-profile routing, actual throughput and application latency remain unverified. Candidate profile is `us.amazon.nova-micro-v1:0`; underlying model is `amazon.nova-micro-v1:0`. |
| Bedrock execution check | Nova Micro playground opened; test prompt entry failed in the rich editor, with a browser-wide alert also observed during investigation | No prompt response was obtained; no model invocation is claimed. Verify one synthetic test through the application's actual role before committing the runtime route. |
| Lambda | Function inventory successfully lists five existing functions, associated with code-editor/workshop infrastructure | Read access exists; no project backend is deployed here. Existing workshop functions are infrastructure, not starter patient-simulation logic. |
| API Gateway | API inventory returns zero APIs | Read access exists; app API still needs implementation/deployment. |
| S3 | Loaded general-purpose bucket inventory says “No buckets” | Read access exists; storage must be provisioned. Creation, upload, and frontend hosting permissions are unverified. |
| DynamoDB | Service console and create-table entry are reachable | Table inventory and creation/write permissions were not successfully established. |
| Workshop editor | Dashboard exposes an existing CloudFront-hosted code-editor output | Editor entry is provisioned; editor session, installed dependencies, instance capacity and app hosting were not tested. Access-bearing URL is intentionally omitted. |
| Local development | Mac reports 24 GiB memory, 14 CPU cores; Node, Python, AWS CLI and Docker executables exist | Suitable candidate for web development and a modest numerical prototype. Executable presence does not prove usable packages/daemon state. No Blender executable found on PATH. |
| Local storage | Data volume reports approximately 8 GiB available and 100% displayed utilization | Avoid large datasets, container images, generated asset libraries and local training downloads. No cleanup was performed. |

The retired Bedrock Model access page says first invocation now controls serverless enablement, with separate Anthropic/Marketplace prerequisites and IAM/SCP controls. Do not activate additional subscriptions, submit first-use agreements, create keys, or widen permissions merely to inspect access.

## Hackathon offers versus activated accounts

The prior [sponsor review](sponsor-resources.md) and [data-source review](data-sources-and-hospital-context.md) preserve the supplied-guide evidence. Those documents' setup instructions are reference material; they do not independently authorize signup, redemption, agreements or credential sharing. This assessment did not redeem offers or change subscriptions.

| Offer / source | Available evidence | Useful role |
|---|---|---|
| Kiro | [Current student page](https://kiro.dev/students/) lists Rutgers and 1,000 credits/month for one year. Individual verification/balance was not inspected. | Development assistance. It does not supply a deployed application runtime or prove access to the plan's Luna/Astra API route. |
| ElevenLabs | Event guide advertises one month Creator with 131,000 credits. [Current public pricing](https://elevenlabs.io/pricing) lists Creator at 121,000 credits. Redeemed balance and renewal were not inspected. | Optional TTS of approved replies. Keep text working and check actual account allowance before estimating usage. |
| Anakin.io | Event guide promises one free month without specifying tier/quota. [Public pricing](https://anakin.io/pricing) lists Starter at 300 credits and five concurrent requests. | Optional small reference-page import. No need for this integration to complete the encounter. |
| Vlada | Participant guide advertises event access until Monday October 12, 9 AM ET, with no card; [public access page](https://www.vladahealth.com/data-access) documents OAuth MCP/API access and a separate generic starter offer. Event entitlement/query success was not verified. | Aggregate cost/access/quality context, possibly one cited debrief card. The supplied catalog does not provide patient charts, live shifts or patient-level hospital flows. |
| TwinVerse materials | Local package includes two challenge documents and two architecture videos. Challenge 1 explicitly promises personas, VHS prompts, case materials, objectives and documentation templates. Those actual case files are absent from the reviewed archive. | Architecture and requirements are available; obtain the promised teaching bundle and named mentor review. |
| RWJUH public sources | Prior research locates public campus/partial admissions maps and provider references | Hospital context and an illustrative scene. Complete current ED geometry, rooms/equipment, staffing and calibrated process parameters remain missing. |

Luna/Astra are named in the plan and available as development-side model options in this environment, but neither a team-owned application API entitlement nor a successful exact-model route was established. The workshop's general model catalog is not sufficient proof. Keep research/authoring tools separate from the app's server-side runtime provider. Subsequent official documentation review identifies a candidate Luna route through Bedrock in us-east-1; see the [workflow pack](luna-data-workflows.md) for exact endpoint/model identifiers. This changes the routing options, not the unverified account entitlement or execution status.

## How much of the plan can be executed?

| Planned capability | Assessment with current evidence | Scope that fits |
|---|---|---|
| Faculty Studio, versioned approval, reusable new-case flow | Technically feasible; implementation and mentor-reviewed content remain | Generic schema, editable form, validation, approve/publish, start encounter without code edits |
| Text patient interview, progressive chart, attachments | Technically feasible; exact provider integration unproved | Backend controls approved facts and reveal events; authored replies and deterministic fallback |
| Objective-linked debrief | Feasible as formative feedback | Deterministic elicited/missed facts plus transcript evidence; tentative communication coaching |
| Spoken patient | Conditional extension | ElevenLabs TTS after redemption, or separately tested Bedrock speech; avoid making full-duplex voice a submission dependency |
| Small ER world / one 3-D room or floor | Feasible as an illustrative visualization | Original geometry and fictional personnel, with room/resource IDs linked to state |
| ED queues, beds and staffing what-if scenario | Feasible as a later illustrative prototype; high weekend scope risk | One reproducible numerical scenario with explicit synthetic assumptions and resource constraints |
| Whole-hospital realistic operations | Blocked for hospital-specific claims | Needs local arrivals, routing, service durations, staffing calendars, downstream constraints and held-out validation data |
| Accurate RWJUH interior in 3-D | Blocked | Needs authorized dimensioned plans/BIM, current room/connectivity data and facilities review |
| Predictive physiology/treatment outcomes | Unsupported by supplied resources | Needs a separate reviewed clinical model and evaluation |
| Educational effectiveness and institutional production release | Not established by software or credits | Requires faculty pilot/evaluation, durable hosting, access controls and institution-approved deployment |

A percentage would obscure the distinction: most of the encounter feature list is buildable, while the hospital-specific fidelity and validation promises have missing inputs. “Buildable” does not mean implemented or guaranteed before judging.

## Recommended execution order

1. Assign the five existing workstreams; establish what teammates already have working. Preserve the plan's Sunday October 11 noon EDT working cutoff, 11 AM materials target and 11:30 AM submission-verification target.
2. In a 20–30 minute gate, obtain the promised personas/prompts/objectives/templates and a mentor review slot. Prove one synthetic Bedrock response through the actual app role and record budget/expiry. Do not assume the listed quota is a spending allowance.
3. Build one local vertical slice: create a genuinely new case → validate → approve an immutable version → start encounter → elicit one approved fact → reveal chart/asset → debrief with that event as evidence.
4. Finish two reviewed cases and one held-out newly authored case. Test unknown questions, leading questions, hidden-fact leakage, reload/reset, retry duplication and provider failure before adding voice.
5. Deploy the smallest portable app. Lambda/API Gateway/DynamoDB/S3 remain a candidate after creation/IAM permission proof; use the same provider adapter and preserve a local export if workshop provisioning blocks progress.
6. If the core passes, add either approved-answer TTS or a small original ER scene. A second simulation engine is a larger extension and should not displace the required new-case demo.
7. Record the four-minute pitch/demo and export code, cases, events, assets and infrastructure configuration outside the expiring account. Confirm access from a teammate's device.

No subscriptions, cloud resources, credentials, patient data, external messages, publication or submission were created by this assessment. Only source inspection and local documentation were completed.
