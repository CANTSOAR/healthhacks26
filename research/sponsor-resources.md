# Sponsor resources and implementation plan

Reviewed for the October 9-11, 2026 Rutgers HealthHack. Submission remains Sunday, October 11 at noon, America/New_York. This is research and a proposed setup/runbook. Redeemed balances, provider access, and account expirations require verification during setup.

The sponsor PDFs describe offers and suggested setup steps. Account-specific access and redemption still require verification. Access links and promo codes stay in the original participant documents and are omitted from this public research.

## Decision for the virtual patient encounter prototype

Keep the required product path: faculty creates and approves a synthetic case, student interviews the patient beside a progressively revealed chart, then receives evidence-linked feedback. The live unseen-case demonstration must work without code changes.

| Resource | Recommended role | Priority and gate |
|---|---|---|
| AWS Workshop Studio account | Host the prototype and, if available, invoke Bedrock for bounded case drafting/patient dialogue | Primary deployment option after account, region, permissions, and expiry checks; preserve a runnable local build |
| Kiro student offer | Optional development aid for requirements, design, tasks, and implementation | Adopt only if a teammate is already comfortable or setup takes at most 10-15 minutes; it is not an application runtime |
| ElevenLabs | Speak already validated patient replies while retaining visible transcript and typed input | P1 after the full text encounter, chart, and feedback work; TTS first, live speech input only if time remains |
| Anakin.io | Optional ingestion of a small set of public, approved reference pages | P2; the core case must run from pinned references and not depend on live web scraping |

These tools support the chosen challenge. Their availability is not a reason to add a second product, a hospital operations simulator, or infrastructure that does not strengthen the four-minute demo.

## AWS and Kiro: exact evidence and limits

### What the supplied Kiro PDF says

The two-page participant document `AWS_Kiro_Access.pdf` describes Kiro as a development environment that creates requirements, design, tasks, and code from a project description. It advertises Kiro as free for students and says setup should take about 10 minutes. It does **not** give a numerical credit allowance, exact offer duration, subscription renewal treatment, AWS account budget, workshop expiry, enabled regions, Bedrock model entitlements, or service quotas.

Its setup sequence is: visit the student page; sign up with an `@rutgers.edu` address; complete SheerID student verification; download/sign into Kiro; open the project and create a spec. The first two steps appear on page 1 and the remaining steps on page 2. Page 2 recommends dividing tasks and deploying to the HealthHack Workshop Studio account.

Page 1 states that teams should use only synthetic or publicly available de-identified data and no real patient data or PHI; page 2 repeats the no-real-patient-info restriction. For this product, use fully synthetic cases and public reference material. Do not upload patient records or private participant communications into sponsor tools as case data.

### Current official Kiro details

The [official student program](https://kiro.dev/students/) currently lists Rutgers University and provides eligible students 1,000 credits per month for one year. Credits do not roll over, add-on credits are unavailable, and the account returns to the Free tier at the end. Signup uses a university-affiliated email through Google, GitHub, or AWS Builder ID, then SheerID; the organization sign-in option is not supported. This is a separate benefit from AWS Workshop Studio. These numerical terms are verified provider information, not statements contained in the event PDF.

The [student terms](https://kiro.dev/students/terms/) require age 18 or older, current enrollment at a participating university, a valid participating-university email, and proof of enrollment when requested. Benefits are limited to one per participant. Individual eligibility and successful verification remain unconfirmed. The source terms were last updated September 8, 2026.

### AWS Workshop Studio access sequence

The participant-provided workshop instructions describe this sequence: open the organizer join link, submit the email address, receive and enter an emailed one-time passcode, review/accept the terms, then open the AWS Management Console through **Get AWS Account Access** on the workshop page. The account is temporary. This sequence is separate from Kiro/SheerID verification.

Record the displayed account end time, allowed region, account identity, and organizer budget before deployment. The provided materials do not establish AWS expiry. Do not infer it from Kiro's one-year period or any other sponsor's expiry. Export code, approved case JSON, and demo evidence outside the temporary AWS account before it expires.

### Core service mapping

This is the recommended implementation mapping, not evidence that every service is enabled in the workshop account:

| AWS service | Narrow use in the prototype |
|---|---|
| Amazon Bedrock | Draft a case against its schema and produce patient language against the faculty-approved case; optional feedback phrasing over deterministic evidence |
| AWS Lambda | Validate case JSON, enforce approved versions, route turns, update reveal state, and return feedback evidence |
| Amazon API Gateway | Expose faculty and encounter endpoints to the web client |
| Amazon DynamoDB | Store immutable case/version IDs, encounter turns, revealed findings, and objective/evidence references |
| Amazon S3 | Store approved reference excerpts, case exports, demo assets, and optionally static frontend assets |
| Amazon Textract | Optional later ingestion of scanned faculty documents; the supplied PDFs are already extractable, so this is not required for P0 |
| Amazon QuickSight | Optional later cohort analytics; use the app's own debrief display for the hackathon |

The approved case and application rules remain the source of truth. The model must not decide new lab values, hidden findings, objective completion, or clinical trajectory at runtime. An unsupported question should produce the case's defined unknown response rather than an invented patient fact. Faculty approval publishes one immutable case version; any edit creates another version.

The [official Bedrock access guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) explains that model access depends on model/region support and account permissions; third-party setup can require Marketplace permissions, payment configuration, and provider prerequisites. Anthropic normally requires first-use details. A successful early call may precede finalized subscription setup. Therefore the deployment owner should verify repeated invocation through the actual application role, using an organizer-approved model and region. Ask the AWS mentor to resolve restricted-account access instead of assuming personal billing or changing accounts.

Use one provider adapter so a denied model can be replaced with another permitted model without changing the case contract. If workshop access is unresolved after a 20-minute technical gate, continue the text prototype with the team's already authorized provider or an explicitly labeled scripted fallback; do not let cloud setup consume the build window.

## ElevenLabs: event offer, claim flow, implementation

### Exact event offer

Page 1 of the participant guide `RU_HealthHack_ElevenLabs_Participant_Guide.pdf` says every hackathon participant can claim **one free month of Creator**, normally $22/month, including **131,000 credits**.

Claim sequence on page 1:

1. Join the ElevenLabs Discord using the Discord account intended for the hackathon; the invitation is in the original PDF.
2. Find the coupon-codes channel.
3. Choose **Start Redemption**.
4. Select **RU HealthHack**.
5. Enter the exact email address used for hackathon registration; the guide says this verifies eligibility.
6. Receive a unique coupon from the bot and follow the supplied redemption instructions.

Page 2 repeats the troubleshooting sequence and directs unresolved problems to Rutgers HealthHack organizers. It also links a tutorial and hacker guide. Those are help resources, not prerequisites to the case-consistency implementation.

The PDF does not state a coupon redemption deadline, exact credit reset date, whether a card is required, how renewal is handled, concurrency limits, or permitted API scopes. Verify the zero-cost checkout, redeemed plan, actual balance, renewal date, and any usage billing before starting generation.

The event's advertised **131,000** credits differs from the current [public Creator pricing](https://elevenlabs.io/pricing), which displays **121,000**. Preserve the event offer as a document claim and use the redeemed account's displayed balance as the operational limit. Public pricing states that products share one credit pool, subscriptions use billing cycles, cancellation retains access to the end of that cycle, and unused paid credits expire on downgrade/cancellation. These are general terms, not proof of this event coupon's behavior.

### Prizes are separate from build resources

Page 2 lists two awards:

| Award | Advertised prize per team member |
|---|---|
| Overall winning team | Three months of Pro, 600,000 credits/month, approximately $297 total value |
| Best project built with ElevenLabs | Three months of Scale, 1.8 million credits/month, approximately $897 total value |

The guide does not say whether the awards can be combined, how a team must prove technology usage, or whether seats/credits can be pooled. Keep them as potential prizes, not available development credits. The meaningful use here is realistic spoken patient replies that retain the same approved facts and transcript.

### Bounded voice implementation

The voice owner should first prove a single backend request that speaks an approved patient response. The flow is `student question -> case-grounded answer -> schema/fact validation -> displayed transcript -> optional TTS`. The spoken text and the transcript must be identical. TTS should not introduce a second free-form conversational agent that can drift from the approved case.

Use a stock or designed fictional voice; voice cloning is unnecessary for the demo. Keep typed input, captions, replay, mute, and a skip-audio control available. Any provider timeout returns the validated text immediately. Test pronunciation of numbers, medication names, and negations against the visible transcript. Cache repeat demo lines by case version, text, voice, and model so repeat rehearsals do not regenerate audio or mix case versions.

The [official TTS streaming endpoint](https://elevenlabs.io/docs/api-reference/text-to-speech/stream) returns audio for supplied text. Its documented zero-retention setting is Enterprise-only; do not promise zero retention on Creator. The [latency guidance](https://elevenlabs.io/docs/api-reference/reducing-latency) distinguishes model inference latency from total application latency and recommends streaming when text is available upfront. Measure the actual browser-to-audio delay rather than adopting a marketing latency number.

The [official API key guidance](https://elevenlabs.io/docs/overview/administration/workspaces/api-keys) states that keys must stay out of client code and can be scoped, assigned a credit quota, and given an expiry. Store the key on the backend and restrict it to the features used. Do not paste teammates' personal keys into shared chat, source control, or the frontend bundle. Choose an expiry that covers the demo and rehearsal window, then rotate/remove the key at closeout.

Use a provisional **40,000-credit project cap** as a planning limit, leaving the rest of the verified allowance for reserve. This is a team recommendation, not a provider quota. The [credit documentation](https://help.elevenlabs.io/hc/en-us/articles/27562020846481-What-are-credits) describes character/model-dependent TTS rates and warns that some library voices carry multipliers. Inspect the selected model/voice's actual charge before estimating capacity. Speech input, sound effects, and other products consume resources separately; avoid making a full-duplex voice pipeline a condition of submission.

Add live speech input only after the text path and TTS are stable. For a browser STT path, use the provider's supported short-lived client credential flow, retain transcript correction, and measure wrong-word behavior. A recognition error must not silently change the student question used for scoring.

## Anakin.io: limited relevance and missing coupon terms

Page 1 of the credit document `RU hacks X Anakin Credit.pdf` promises **one month of free access**. It directs participants to the pricing page, enter the supplied promo code at checkout, and confirm the free month. If rejected, the document says to check exact uppercase entry with no spaces and contact the Anakin team. Page 2 is blank.

The document does not identify a plan tier, credit quantity, API access, eligible-account type, coupon expiry, payment requirement, or renewal price. The word “credits” in its title does not establish a numeric credit entitlement.

The current [official Anakin.io site](https://anakin.io/) describes web scraping and web data APIs. It is a different product from similarly named Anakin AI; do not plan on using it as an LLM substitute. The [public pricing](https://anakin.io/pricing) lists a free Starter plan with 300 credits and five concurrent requests, and distinguishes non-expiring signup/top-up credits from monthly credits that expire each cycle. The event coupon's tier and quota remain unknown.

A defensible optional use is importing a small set of public reference pages into a reviewed source manifest with URL, title, retrieval date, license/access conditions, excerpt, and supported case facts. A scraped page is not automatically a clinical authority or a reusable licensed dataset. Keep the encounter offline from live source fetching; approval should pin the reference excerpts used by that case version. The existing research and supplied TwinVerse case package may already eliminate this integration's value before Sunday.

## Assignment and schedule changes

Use the five workstreams in [the action plan](action-plan.md). A participant can claim an individually available offer, but the team should agree on one application account/key owner for each used runtime provider and record the actual entitlement. Do not assume five individual plans form a shared quota.

| Owner | Resource-related responsibility |
|---|---|
| Integration and submission owner | Confirm workshop region/access/expiry; own deployment and runnable export; keep noon submission path independent of account setup |
| UI owner | Retain text-first encounter, progressive chart, captions, mute, and replay; support degraded voice behavior |
| Patient state/dialogue owner | Bedrock adapter and approved-case fact enforcement; validate one model integration before optimizing |
| Clinical/source owner | Keep sources public and cases synthetic; approve source snapshots and case versions; evaluate optional Anakin ingestion |
| Evaluation/pitch owner | Voice smoke tests, measured latency, exact transcript/audio correspondence, provider failure demo, final recording |

At the first setup gate, record only confirmed facts: redeemed tier/balance, expiry/renewal, chosen AWS account/region/model, and working application-role invocation. Do not block the team on optional redemptions. Saturday morning still ends with Studio -> encounter -> feedback working in text. Saturday afternoon may add TTS after unseen-case and consistency checks. Freeze provider changes Saturday evening; prepare a local/exported fallback and final screen recording. Complete materials by Sunday 11 a.m. and verify submission by 11:30 a.m.

## Unresolved facts to ask the sponsor mentor or inspect during authorized setup

1. AWS: exact workshop shutdown time, enabled region/services, Bedrock permitted model, deployment permissions, and any shared budget.
2. Kiro: each participant's student verification result and displayed quota; the official benefit is known, individual activation is not.
3. ElevenLabs: coupon expiry, actual 131k/121k balance, API feature access, renewal/payment conditions, and whether both sponsor awards can stack.
4. Anakin: coupon plan and credits, API inclusion, expiry, billing after the free month, and any sponsor-specific proof requirements.

These are narrow setup uncertainties. They do not change the core product or justify delaying approved-case consistency, faculty approval, feedback traceability, or the live unseen-case test.

## Source register

- AWS_Kiro_Access.pdf, pages 1-2: student setup, Workshop Studio suggestion, synthetic/de-identified-data restriction. All pages rendered and reviewed.
- RU_HealthHack_ElevenLabs_Participant_Guide.pdf, pages 1-2: Creator offer and email-based redemption; awards and troubleshooting. All pages rendered and reviewed.
- RU hacks X Anakin Credit.pdf, page 1: one-month coupon and checkout flow; page 2 blank. Both pages rendered and reviewed with promo code masking in local review copies.
- Participant-provided AWS workshop access instructions: email/OTP/terms/console workflow and temporary account description.
- Official Kiro, AWS, ElevenLabs, and Anakin links cited beside the claims above; checked October 9, 2026. No redeemed-account state was independently verified.
