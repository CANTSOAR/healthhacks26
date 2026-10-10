// End-to-end check of /journey in headless Chromium, with screenshots.
//   node app/journey/e2e.mjs [webUrl] [--api http://localhost:8011] [--out <dir>]
// Needs the web app and a server with the journey routes running. Run the server with ENCOUNTER_PRIVATE_DIR pointing at an
// empty folder: then only this project's seed patients and the built-in fictional clinicians exist, which is what the
// screenshots (overnight/screenshots/journey-*.png, committed to a public repository) must show.
import fs from "node:fs";
import path from "node:path";

const argv = process.argv.slice(2);
const opt = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const web = (argv.find((a, i) => /^https?:/.test(a) && !String(argv[i - 1]).startsWith("--")) ?? "http://localhost:3002").replace(/\/$/, "");
const api = opt("--api", "http://localhost:8011").replace(/\/$/, "");
const here = path.dirname(new URL(import.meta.url).pathname);
const webRoot = path.resolve(here, "../..");
const out = path.resolve(opt("--out", path.resolve(webRoot, "../overnight/screenshots")));
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.resolve(webRoot, ".playwright");
fs.mkdirSync(out, { recursive: true });
const { chromium } = await import("playwright");

const CASE = "breathless-retired-driver";
const SEEDS = ["breathless-retired-driver", "chest-pain-line-cook", "abdominal-pain-grad-student"];
const TRIAGE = ["Hello Mr. Asante, I'm Sam, the triage nurse. What brings you in today?", "Do you have any heart problems?", "Any allergies?", "What medications are you taking?", "Are you taking all of them every day?"];
const TRIAGE_NOTE = "Short of breath for two weeks, worse for three days. Known heart failure. Says he takes all his tablets.";

const problems = [];
const passed = [];
const ok = (cond, what) => {
  (cond ? passed : problems).push(what);
  console.log(cond ? "  ok  " : "  FAIL", what);
};
const call = async (p, body) => {
  const r = await fetch(api + p, body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : undefined);
  return { status: r.status, json: await r.json().catch(() => null) };
};

// the screenshots must only ever show our own seed patients and the built-in stand-in clinicians
const cases = (await call("/api/cases?status=published")).json ?? [];
const clinicians = (await call("/api/clinicians")).json ?? {};
if (clinicians.source !== "builtin" || cases.some((c) => c.origin?.kind === "from_sample_patient")) {
  console.error("Refusing to take screenshots: the server has organizer material loaded. Start it with ENCOUNTER_PRIVATE_DIR set to an empty folder.");
  process.exit(2);
}

// a seed for which the sampled physician neither pulls the pharmacy record nor hears the concealed fact, so the pharmacist stage has something to find
async function pickSeed() {
  for (let seed = 1; seed <= 60; seed++) {
    const j = (await call("/api/journeys", { case_id: CASE, template_id: "heart-failure-admission", seed })).json;
    const base = `/api/journeys/${j.journey_id}/stages`;
    await call(`${base}/triage/start`, { mode: "human" });
    for (const t of TRIAGE) await call(`${base}/triage/turn`, { text: t });
    await call(`${base}/triage/finish`, { acuity: 2, note: TRIAGE_NOTE });
    const s = (await call(`${base}/clinician/start`, { mode: "auto" })).json;
    const e = s.record.entries;
    const found = e.filter((x) => x.fact_id).length;
    if (!e.some((x) => x.fact_id === "f.concealed.stopped_diuretic") && !e.some((x) => x.request === "order:medication_list") && e.some((x) => x.fact_id === "f.lab.bnp") && e.some((x) => x.key === "disposition") && found >= 14) return seed;
  }
  return null;
}
const seed = await pickSeed();
console.log("seed for the story:", seed);
if (seed == null) {
  console.error("no suitable seed found");
  process.exit(2);
}

const browser = await chromium.launch({ channel: "chromium", args: ["--use-fake-ui-for-media-stream"] });
async function newPage(viewport = { width: 1440, height: 900 }) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => problems.push(`pageerror: ${String(e).slice(0, 300)}`));
  page.on("console", (m) => {
    if (m.type() === "error" && !/Failed to load resource|favicon/.test(m.text())) problems.push(`console: ${m.text().slice(0, 300)}`);
  });
  page.setDefaultTimeout(30000);
  return page;
}
const url = (p) => {
  const u = new URL(web + p);
  u.searchParams.set("api", api);
  return u.toString();
};
async function shot(page, name, opts = {}) {
  const file = path.join(out, `${name}.png`);
  await page.screenshot({ path: file, ...opts });
  console.log("  saved", path.relative(process.cwd(), file));
}
async function say(page, text) {
  const before = await page.getByTestId("msg-patient").count();
  await page.getByTestId("chat-input").fill(text);
  await page.getByTestId("chat-send").click();
  await page.waitForFunction((n) => document.querySelectorAll('[data-testid="msg-patient"]').length > n, before);
  await page.waitForSelector('[data-testid="msg-typing"]', { state: "detached" });
  const reply = await page.getByTestId("msg-patient").last().innerText();
  console.log(`    you: ${text}\n    pt:  ${reply.replace(/\s+/g, " ").slice(0, 140)}`);
  return reply;
}
const entries = (page) => page.getByTestId("record-entry").count();
const settle = (page, ms = 500) => page.waitForTimeout(ms);

try {
  // ---------------------------------------------------------------- picker -> setup -> start (through the UI)
  console.log("picker and setup");
  const page = await newPage();
  await page.goto(url("/journey"));
  await page.waitForSelector('[data-testid="journey-case"]');
  const shown = await page.getByTestId("journey-case").evaluateAll((els) => els.map((e) => e.getAttribute("data-case")));
  ok(shown.length === SEEDS.length && SEEDS.every((s) => shown.includes(s)), `picker lists exactly the ${SEEDS.length} seed patients`);
  await shot(page, "journey-picker");
  await page.locator(`[data-testid="journey-case"][data-case="${CASE}"]`).click();
  await page.waitForSelector('[data-testid="journey-setup"]');
  ok((await page.getByTestId("setup-patient").innerText()).includes("Leonard Asante"), "setup shows the chosen patient");
  ok((await page.getByTestId("journey-template").count()) === 2, "two journey templates apply to this patient");
  ok((await page.locator('[data-testid="journey-template"][data-on="true"]').getAttribute("data-template")) === "heart-failure-admission", "the journey written for this patient is preselected");
  await shot(page, "journey-setup");
  await page.getByTestId("journey-start").click();
  await page.waitForSelector('[data-testid="stage-rail"]');
  ok(/journey_id=jrn-/.test(page.url()), "address becomes ?journey_id=... after starting");
  ok((await page.getByTestId("rail-stage").count()) === 4, "stage rail shows four stages");
  ok((await page.getByTestId("stage-start").innerText()).includes("Triage"), "first stage offers to play or sample triage");

  // /journey?case_id=...&template_id=... (the link other pages can use)
  await page.goto(url(`/journey?case_id=chest-pain-line-cook&template_id=ed-to-ward`));
  await page.waitForSelector('[data-testid="journey-setup"]');
  ok((await page.getByTestId("setup-patient").innerText()).includes("Rafael Quintero") && (await page.getByTestId("journey-template").count()) === 1, "/journey?case_id=... opens the setup for that patient with the any-patient template");
  await page.goto(url(`/journey?case_id=no-such-patient`));
  await page.waitForSelector('[data-testid="error-card"]');
  ok(true, "an unknown case_id shows an error card, not a blank page");

  // ---------------------------------------------------------------- the story, on a fixed seed
  console.log("stage 1: triage, played");
  const j = (await call("/api/journeys", { case_id: CASE, template_id: "heart-failure-admission", seed })).json;
  const jurl = url(`/journey?journey_id=${j.journey_id}`);
  await page.goto(jurl);
  await page.waitForSelector('[data-testid="stage-start"]');
  await shot(page, "journey-stage-rail");
  await page.getByTestId("stage-play").click();
  await page.waitForSelector('[data-testid="patient-stage"]');
  ok((await entries(page)) === 3, "starting triage records the vital signs under the triage nurse");
  for (const t of TRIAGE) await say(page, t);
  await settle(page);
  ok((await page.locator('[data-testid="record-entry"][data-kind="patient_report"]').count()) === 1, "the patient's own account of his tablets is recorded as 'patient said'");
  ok((await page.getByTestId("provenance").first().innerText()).includes("Triage nurse"), "entries carry a provenance chip with the role");
  await shot(page, "journey-triage-play");
  await page.getByTestId("stage-finish-open").click();
  await page.getByTestId("acuity-2").click();
  await page.getByTestId("finish-note").fill(TRIAGE_NOTE);
  await page.getByTestId("finish-submit").click();
  await page.waitForSelector('[data-testid="stage-summary"]');
  ok((await page.getByTestId("stage-who").innerText()).includes("You played"), "triage summary says you played it");
  ok((await page.getByTestId("writeback-note").innerText()).includes("no simulator write-back yet"), "triage says it has no simulator write-back yet");
  ok((await page.locator('[data-testid="stage-objective"][data-result="held"]').count()) === 1, "the acuity-match objective is held back until the debrief");

  console.log("stage 2: physician, sampled");
  await page.getByTestId("stage-next").click();
  await page.waitForSelector('[data-testid="stage-start"]');
  await page.getByTestId("stage-auto").click();
  await page.waitForSelector('[data-testid="stage-summary"][data-stage="clinician"]');
  ok((await page.getByTestId("stage-who").innerText()).includes("Dr. Jun Watanabe"), "the sampled stage names the built-in AI colleague who stood in");
  ok((await page.locator('[data-testid="rail-stage"][data-stage="clinician"]').getAttribute("data-played-by")) === "sampled", "rail marks the physician stage as sampled");
  ok((await page.getByTestId("stage-result").innerText()).includes("sampled"), "its interaction result has resolver = sampled");
  await shot(page, "journey-sampled-stage");

  console.log("stage 3: medication reconciliation, played");
  await page.getByTestId("stage-next").click();
  await page.getByTestId("stage-play").click();
  await page.waitForSelector('[data-testid="patient-stage"]');
  const chartText = await page.locator("body").innerText();
  ok(chartText.includes("From the shared record") || (await page.getByTestId("pane-chart").count()) > 0, "the pharmacist's chart opens with what earlier stages recorded");
  await say(page, "Hello Mr. Asante, I'm the pharmacist. I'd like to go through your medicines with you, if that's all right.");
  await say(page, "Are you taking all of them every day?");
  await say(page, "Can I pull up your pharmacy records?");
  await page.waitForSelector('[data-testid="discrepancy"][data-resolved="false"]');
  const disc = await page.getByTestId("discrepancy").first().innerText();
  ok(disc.includes("Triage nurse") && disc.includes("ED pharmacist") && disc.includes("I take my pills every morning"), "the conflict shows both sides with both provenances (triage nurse's entry vs the pharmacist's document)");
  await settle(page, 900);
  await shot(page, "journey-shared-record");
  const reply = await say(page, "I see the pharmacy record shows the furosemide hasn't been refilled in nine weeks. Can you tell me what happened?");
  ok(/stopped the water pill/.test(reply), "raising the record with the patient brings out what he had not said");
  await page.waitForSelector('[data-testid="discrepancy"][data-resolved="true"]');
  ok((await page.locator('[data-testid="discrepancy"][data-resolved="false"]').count()) === 0, "the conflict is marked settled");
  ok((await page.getByTestId("used-in").count()) >= 1, "earlier entries show that a later stage used them");
  await page.getByTestId("stage-finish-open").click();
  await page.getByTestId("finish-med-list").fill("Furosemide 40 mg: prescribed, stopped about three weeks ago\nLisinopril 10 mg: taking\nNaproxen twice a day, over the counter\nWarfarin 5 mg daily");
  await page.getByTestId("finish-open-questions").fill("Can the diuretic be given earlier in the day?");
  await page.getByTestId("finish-submit").click();
  await page.waitForSelector('[data-testid="stage-summary"][data-stage="medrec"]');
  ok((await page.locator('[data-testid="record-entry"][data-status="unsupported"]').count()) === 1, "a medicine nobody recorded is flagged as not supported by the record");

  console.log("stage 4: SBAR handoff");
  await page.getByTestId("stage-next").click();
  await page.getByTestId("stage-play").click();
  await page.waitForSelector('[data-testid="sbar-composer"]');
  ok((await page.getByTestId("colleague-name").innerText()) === "Dr. Helen Brandt", "the receiving colleague is the built-in fictional hospital medicine attending");
  await page.getByTestId("sbar-situation").fill("Leonard Asante, 68, has worsening shortness of breath over two weeks. He sleeps propped on three pillows and both ankles are swollen.");
  await page.getByTestId("sbar-background").fill("Heart failure diagnosed three years ago after a heart attack. He stopped his furosemide about three weeks ago. He is allergic to penicillin.");
  await page.getByTestId("sbar-assessment").fill("BNP is 1,240 and the chest X-ray shows an enlarged heart with small pleural effusions. I think this is fluid overload from stopping the diuretic.");
  await page.getByTestId("sbar-recommendation").fill("");
  await shot(page, "journey-sbar-composer");
  await page.getByTestId("sbar-submit").click();
  await page.waitForSelector('[data-testid="msg-colleague"][data-kind="question"]');
  const q1 = await page.locator('[data-testid="msg-colleague"][data-kind="question"]').last().innerText();
  ok(q1.includes("He is allergic to penicillin") && q1.includes("cannot find that in the shared record"), "the colleague challenges the unsupported statement, quoting it");
  await page.getByTestId("handoff-input").fill("You are right, that was my assumption. He has no known drug allergies.");
  await page.getByTestId("handoff-send").click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="msg-colleague"]').length >= 3);
  await settle(page);
  await shot(page, "journey-sbar-questions");
  for (let i = 0; i < 4 && (await page.getByTestId("handoff-stage").getAttribute("data-phase")) === "questions"; i++) {
    const n = await page.getByTestId("msg-colleague").count();
    await page.getByTestId("handoff-input").fill(i === 0 ? "He is for admission. Please start an intravenous diuretic and daily weights." : "Nothing else that I know of.");
    await page.getByTestId("handoff-send").click();
    await page.waitForFunction((k) => document.querySelectorAll('[data-testid="msg-colleague"]').length > k, n);
  }
  ok((await page.locator('[data-testid="msg-colleague"][data-kind="readback"]').count()) === 1, "after her questions the colleague reads the handoff back");
  await page.getByTestId("handoff-finish").click();
  await page.waitForSelector('[data-testid="sbar-report"]');
  ok((await page.getByTestId("sbar-element").count()) === 4, "the handoff is reported per SBAR element");
  ok((await page.getByTestId("sbar-unsupported").count()) >= 1 && (await page.getByTestId("sbar-unsupported").first().innerText()).includes("penicillin"), "the unsupported statement is quoted in the report");
  ok((await page.getByTestId("sbar-omitted").count()) >= 1, "omitted critical items are listed with their provenance");
  await page.getByTestId("sbar-report").scrollIntoViewIfNeeded();
  await settle(page);
  await shot(page, "journey-sbar-report");

  console.log("care plan and debrief");
  await page.getByTestId("rail-outcome").click();
  await page.waitForSelector('[data-testid="care-plan"]');
  ok((await page.getByTestId("journey-view").getAttribute("data-status")) === "complete", "the journey is complete");
  ok((await page.getByTestId("plan-disposition").innerText()).includes("admit"), "care plan shows the recorded disposition and who decided it");
  ok((await page.getByTestId("plan-source").innerText()).includes("shared record only"), "care plan says it is assembled from the shared record only");
  ok((await page.getByTestId("plan-open").innerText()).includes("Warfarin"), "open questions include the unsupported medicine");
  ok((await page.getByTestId("plan-row").count()) >= 5, "plan rows carry provenance");
  await shot(page, "journey-care-plan");
  await page.getByTestId("plan-contributions").scrollIntoViewIfNeeded();
  await settle(page);
  await shot(page, "journey-care-plan-contributions");
  await page.getByTestId("tab-debrief").click();
  await page.waitForSelector('[data-testid="team-debrief"]');
  ok((await page.getByTestId("stage-debrief").count()) === 4, "debrief has one section per stage");
  ok((await page.getByTestId("role-debrief").innerText()).includes("ED pharmacist"), "debrief rolls objectives up per role");
  ok((await page.locator('[data-testid="stage-objective"][data-result="held"]').count()) === 0, "nothing is held back once the journey is complete");
  await shot(page, "journey-debrief");
  await page.getByTestId("stage-debrief").first().scrollIntoViewIfNeeded();
  await settle(page);
  await shot(page, "journey-debrief-stages");

  // reload resumes the same journey
  await page.reload();
  await page.waitForSelector('[data-testid="outcome"]');
  ok((await page.getByTestId("record-count").innerText()).includes("entries"), "a reload reopens the finished journey with its record");

  // ---------------------------------------------------------------- narrow viewport
  console.log("narrow viewport");
  const phone = await newPage({ width: 390, height: 844 });
  await phone.goto(jurl);
  await phone.waitForSelector('[data-testid="outcome"]');
  ok((await phone.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)), "no horizontal page scroll at 390 px");
  await shot(phone, "journey-narrow");
  await phone.getByTestId("pane-record").click();
  await phone.waitForSelector('[data-testid="record-panel"]');
  ok(await phone.getByTestId("record-panel").isVisible(), "the shared record is one tap away on a phone");
  await shot(phone, "journey-narrow-record");
  await phone.locator('[data-testid="rail-stage"][data-stage="handoff"]').click();
  await phone.getByTestId("pane-stage").click();
  await phone.waitForSelector('[data-testid="stage-summary"]');
  await shot(phone, "journey-narrow-stage");
} catch (e) {
  problems.push(`exception: ${String(e).slice(0, 500)}`);
  console.error(e);
} finally {
  await browser.close();
}
console.log(`\n${passed.length} checks passed, ${problems.length} problems`);
problems.forEach((p) => console.log("  -", p));
process.exit(problems.length ? 1 : 0);
