// End-to-end check of /encounter and /studio in headless Chromium, with screenshots.
//   node app/encounter/e2e.mjs [webUrl] [--api http://localhost:8000] [--only picker,encounter,narrow,studio,sim] [--out <dir>]
// Needs the web app (pnpm dev or pnpm start) and the server (./run_server.sh) running.
// Screenshots go to overnight/screenshots/ (encounter-*.png, studio-*.png). They are committed to a public repository,
// so every view is filtered to this project's own seed cases or to the patient this script creates; the organizers'
// sample patients (loaded at run time from .private/) are never on screen when a picture is taken.
import fs from "node:fs";
import path from "node:path";

const argv = process.argv.slice(2);
const opt = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const web = (argv.find((a, i) => /^https?:/.test(a) && !String(argv[i - 1]).startsWith("--")) ?? "http://localhost:3000").replace(/\/$/, "");
const api = opt("--api", "http://localhost:8000").replace(/\/$/, "");
const only = opt("--only", "").split(",").filter(Boolean);
const here = path.dirname(new URL(import.meta.url).pathname);
const webRoot = path.resolve(here, "../..");
const out = path.resolve(opt("--out", path.resolve(webRoot, "../overnight/screenshots")));
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.resolve(webRoot, ".playwright");
fs.mkdirSync(out, { recursive: true });
const { chromium } = await import("playwright");

const browser = await chromium.launch({ channel: "chromium", args: ["--use-fake-ui-for-media-stream"] });
const problems = [];
const passed = [];
const want = (n) => !only.length || only.includes(n);
const ok = (cond, what) => {
  if (cond) passed.push(what);
  else problems.push(what);
  console.log(cond ? "  ok  " : "  FAIL", what);
};

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
  if (api !== "http://localhost:8000") u.searchParams.set("api", api);
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
  console.log(`    you: ${text}\n    pt:  ${reply.replace(/\s+/g, " ").slice(0, 150)}`);
  return reply;
}
async function request(page, group, req) {
  const before = await page.getByTestId("msg-system").count();
  await page.getByTestId(`quick-${group}`).click();
  await page.locator(`[data-testid="request-option"][data-request="${req}"]`).click();
  await page.waitForFunction((n) => document.querySelectorAll('[data-testid="msg-system"]').length > n, before);
  console.log(`    request ${req}: ${(await page.getByTestId("msg-system").last().innerText()).slice(0, 140)}`);
}
async function finish(page, { disposition, summary, order }) {
  await page.getByTestId("finish-open").click();
  await page.getByTestId(`disposition-${disposition}`).click();
  if (order) await page.getByTestId("finish-add-order").selectOption(order).catch(() => {});
  await page.getByTestId("finish-summary").fill(summary);
  return page;
}
const j = async (p, body, method) => {
  const r = await fetch(api + p, body !== undefined ? { method: method ?? "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : { method: method ?? "GET" });
  return { status: r.status, data: await r.json().catch(() => null) };
};

// ------------------------------------------------------------------ case picker
if (want("picker")) {
  console.log("picker");
  const page = await newPage();
  await page.goto(url("/encounter"));
  await page.waitForSelector('[data-testid="case-card"]');
  ok((await page.getByTestId("case-card").count()) >= 3, "picker lists at least the three seed cases");
  ok(await page.getByTestId("synthetic-label").first().isVisible(), "picker shows the synthetic-patient label");
  ok((await page.getByTestId("provider-chip").innerText()).length > 0, "picker shows the provider status chip");
  // keep the picture to this project's own emergency department cases
  await page.getByLabel("Search cases").fill("emergency medicine resident");
  await page.waitForTimeout(400);
  await shot(page, "encounter-01-picker");
  await page.context().close();
}

// ------------------------------------------------------------------ a seed case, start to feedback
if (want("encounter")) {
  console.log("encounter (seed case chest-pain-line-cook)");
  const page = await newPage();
  await page.goto(url("/encounter"));
  await page.locator('[data-testid="case-card"][data-case-id="chest-pain-line-cook"]').click();
  await page.waitForSelector('[data-testid="encounter"]');
  await page.waitForURL(/encounter_id=/);
  ok((await page.getByTestId("vital-tile").count()) >= 2, "vital signs are visible from the start");
  ok(await page.locator('[data-section-id="triage"]').isVisible(), "triage note is visible from the start");
  ok(await page.getByTestId("hidden-sections").isVisible(), "locked sections are announced, not shown");
  await shot(page, "encounter-02-start");

  await say(page, "Hello Mr Quintero, my name is Dr Shah, I'm the resident looking after you today. What brought you in?");
  await say(page, "When did the pain start, and what were you doing?");
  await say(page, "What does the pain feel like? Does it go anywhere else?");
  const denial = await say(page, "Have you used any drugs like cocaine recently?");
  ok(/no\b|don't/i.test(denial), "concealed fact: the patient gives the authored cover answer first");
  const factsBefore = await page.locator('[data-fact-id="f.concealed.cocaine_use"]').count();
  ok(factsBefore === 0, "concealed fact is not in the chart after the denial");
  await say(page, "That sounds frightening, and I'm sorry you're going through this. I'm not here to judge you. Everything you tell me stays between us and helps me treat you safely.");
  await say(page, "Do you smoke? Any high blood pressure or heart disease in the family?");
  await request(page, "order", "order:troponin");
  ok((await page.getByTestId("lab-row").count()) >= 3, "requested lab renders as a table with rows");
  ok((await page.getByTestId("new-tag").count()) >= 1, "newly released chart items are highlighted");
  await shot(page, "encounter-03-lab-released");
  await request(page, "order", "order:tox_screen");
  const truth = await say(page, "Your urine drug screen has come back positive for cocaine. I'm not judging, but it changes which medicines are safe for your heart. Did you take anything last night?");
  ok(/coke|cocaine/i.test(truth) && !/don't do drugs/i.test(truth), "concealed fact: disclosed after being confronted with the evidence");
  ok((await page.locator('[data-fact-id="f.concealed.cocaine_use"]').count()) === 1, "concealed fact appears in the chart once disclosed");
  await shot(page, "encounter-04-concealed-disclosed");
  await say(page, "Thank you for telling me. What worries you most about all of this?");
  await request(page, "exam", "exam:cardiac");

  await page.getByTestId("tab-ledger").click();
  await page.waitForSelector('[data-testid="ledger-row"]');
  const rules = await page.$$eval('[data-testid="ledger-unlock"]', (els) => els.map((e) => e.getAttribute("data-rule")));
  ok(rules.includes("denied_until_confronted"), "ledger names the rule that released the concealed fact");
  ok(rules.includes("on_request") && rules.includes("if_asked"), "ledger shows on-request and if-asked releases");
  await shot(page, "encounter-05-ledger");
  await page.getByTestId("tab-chart").click();

  await finish(page, { disposition: "admit", order: "order:ecg", summary: "41-year-old man with central chest pressure at rest radiating to the jaw, cocaine use overnight, raised first troponin. Admit for serial troponins and monitoring; avoid beta blockers." });
  await shot(page, "encounter-06-finish-form");
  await page.getByTestId("finish-submit").click();
  await page.waitForSelector('[data-testid="feedback"]');
  const labels = await page.$$eval('[data-testid="objective-label"]', (els) => els.map((e) => e.textContent));
  ok(labels.length >= 5 && labels.every((l) => ["Met", "Partly demonstrated", "Not observed", "Not assessable"].includes(l)), `objectives use the four labels (${labels.join(", ")})`);
  ok((await page.getByTestId("evidence").count()) >= 5, "feedback quotes transcript evidence");
  ok((await page.getByTestId("rubric-domain").count()) >= 5, "rubric domains are shown");
  ok(/offline heuristics|language model/.test(await page.getByTestId("grader-kind").innerText()), "grader kind is stated");
  ok((await page.getByTestId("elicited-item").count()) > 0 && (await page.getByTestId("missed-item").count()) > 0, "elicited and missed findings are listed");
  ok((await page.getByTestId("writeback-card").count()) === 0, "no write-back card for a stand-alone case");
  await shot(page, "encounter-07-feedback", { fullPage: true });
  await shot(page, "encounter-07-feedback-top");
  // a reload shows the same finished session
  await page.reload();
  await page.waitForSelector('[data-testid="feedback"]');
  ok(true, "reloading a finished encounter shows its feedback again");
  await page.context().close();
}

// ------------------------------------------------------------------ narrow viewport
if (want("narrow")) {
  console.log("narrow viewport (seed case abdominal-pain-grad-student)");
  const page = await newPage({ width: 390, height: 844 });
  await page.goto(url("/encounter?case_id=abdominal-pain-grad-student"));
  await page.waitForSelector('[data-testid="encounter"]');
  ok(await page.getByTestId("pane-talk").isVisible(), "narrow: pane switch is shown");
  ok(!(await page.getByTestId("chart-pane").isVisible()), "narrow: chart is hidden while the conversation is open");
  await say(page, "Hi Hannah, I'm one of the doctors. What's been going on?");
  await shot(page, "encounter-08-narrow-conversation");
  await page.getByTestId("pane-chart").click();
  ok(await page.getByTestId("chart-pane").isVisible(), "narrow: chart opens from the tab switch");
  await shot(page, "encounter-09-narrow-chart");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  ok(overflow <= 1, `narrow: no horizontal overflow (${overflow}px)`);
  await page.goto(url("/studio?case=chest-pain-line-cook"));
  await page.waitForSelector('[data-testid="case-editor"]');
  await page.getByTestId("tab-facts").click();
  await page.getByTestId("fact-toggle").nth(1).click();
  const o2 = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  ok(o2 <= 1, `narrow: studio editor has no horizontal overflow (${o2}px)`);
  await shot(page, "studio-10-narrow-editor");
  await page.context().close();
}

// ------------------------------------------------------------------ Patient Studio: create -> edit -> validate -> approve -> publish -> encounter
if (want("studio")) {
  console.log("studio (new patient from a template)");
  const NAME = "Priya Raman"; // made up for this run
  const page = await newPage();
  await page.goto(url("/studio"));
  await page.waitForSelector('[data-testid="studio-row"]');
  ok((await page.locator('[data-testid="studio-row"][data-status="published"]').count()) >= 3, "studio lists the cases with status chips");
  await shot(page, "studio-01-list");

  await page.getByTestId("new-patient-btn").click();
  await page.waitForSelector('[data-testid="template-card"]');
  ok((await page.getByTestId("template-card").count()) >= 3, "condition templates are offered");
  await page.locator('[data-testid="template-card"][data-template-id="infection_fever"]').click();
  await page.getByTestId("tpl-severity").selectOption("moderate");
  await page.getByTestId("tpl-name").fill(NAME);
  await page.getByTestId("tpl-age").fill("34");
  await page.getByTestId("tpl-sex").selectOption("female");
  await shot(page, "studio-02-new-from-template");
  // the other two creation paths are present
  await page.getByTestId("new-path-description").click();
  ok(await page.getByTestId("desc-text").isVisible(), "free-text description path is present");
  await page.getByTestId("new-path-form").click();
  ok(await page.getByTestId("form-complaint").isVisible(), "structured form path is present");
  await page.getByTestId("new-path-template").click();
  await page.getByTestId("new-create").click();
  await page.waitForSelector('[data-testid="case-editor"]');
  const caseId = await page.getByTestId("case-editor").getAttribute("data-case-id");
  console.log("    created", caseId);
  ok((await page.getByTestId("case-editor").getAttribute("data-status")) === "draft", "a new patient starts as a draft");
  ok((await page.getByTestId("editor-title").innerText()).includes(NAME), "the editor opens on the new patient");
  ok(await page.getByTestId("creation-notes").isVisible(), "the editor says how the draft was made");
  await shot(page, "studio-03-editor-overview");

  // facts: edit the wording of one, and guard another behind rapport
  await page.getByTestId("tab-facts").click();
  await page.waitForSelector('[data-testid="fact-row"]');
  const nFacts = await page.getByTestId("fact-row").count();
  ok(nFacts >= 10, `facts table shows the template's facts (${nFacts})`);
  const first = page.locator('[data-testid="fact-row"]').filter({ has: page.locator('[data-category="chief_complaint"]') }).first();
  await first.getByTestId("fact-toggle").click();
  await first.getByTestId("fact-answer").fill("I've been burning up since yesterday and it stings every time I pee.");
  await first.getByTestId("fact-toggle").click();
  const second = page.locator('[data-testid="fact-row"]').filter({ has: page.locator('[data-category="social"]') }).first();
  await second.getByTestId("fact-toggle").click();
  const secondId = await second.getAttribute("data-fact-id");
  await second.getByTestId("fact-rule").selectOption("after_rapport");
  await second.getByTestId("fact-rapport").fill("");
  await page.getByTestId("btn-validate").click();
  await second.locator('[data-testid="issue"][data-level="error"]').first().waitFor({ timeout: 10000 }).catch(() => {});
  const inlineErr = await second.locator('[data-testid="issue"][data-level="error"]').count();
  ok(inlineErr >= 1, "validate shows an error inline, next to the offending field (rapport points missing)");
  ok((await page.getByTestId("validation-summary").getAttribute("data-ok")) === "false", "validation summary says the case cannot be approved yet");
  await shot(page, "studio-04-validate-summary");
  await second.scrollIntoViewIfNeeded();
  await page.mouse.wheel(0, 260);
  await page.waitForTimeout(300);
  await shot(page, "studio-04-validate-inline-error");
  // approving now is refused with the same findings
  await page.getByTestId("btn-approve").click();
  await page.waitForSelector('[data-testid="editor-error"]');
  ok((await page.getByTestId("case-editor").getAttribute("data-status")) === "draft", "approve is refused while there are errors");
  await second.getByTestId("fact-rapport").fill("3");
  await second.getByTestId("fact-cover").fill("Oh, nothing worth mentioning.");
  console.log("    guarded fact:", secondId);

  // an objective
  await page.getByTestId("tab-objectives").click();
  const obj = page.getByTestId("objective-editor").first();
  await obj.getByTestId("objective-criterion").fill("Characterises the urinary symptoms and the fever: onset, severity and associated symptoms");
  await obj.getByTestId("objective-missed").fill("Ask when it started, how bad it is, and what else has come with it.");
  await shot(page, "studio-05-objectives");

  // a lab report with rows, released on request
  await page.getByTestId("tab-chart").click();
  const before = await page.getByTestId("artifact-editor").count();
  await page.getByTestId("add-lab").click();
  const lab = page.getByTestId("artifact-editor").nth(before);
  await lab.getByTestId("artifact-title").fill("Renal function (added in the Studio)");
  await lab.getByTestId("artifact-request").fill("order:bmp");
  const row = lab.getByTestId("lab-edit-row").first();
  await row.getByTestId("lab-test").fill("Creatinine");
  await row.getByTestId("lab-value").fill("1.4");
  await row.getByTestId("lab-unit").fill("mg/dL");
  await row.getByTestId("lab-ref").fill("0.6-1.1");
  await row.getByTestId("lab-flag").selectOption("H");
  await lab.scrollIntoViewIfNeeded();
  await shot(page, "studio-06-chart-lab-report");

  // a source
  await page.getByTestId("tab-sources").click();
  ok(await page.getByTestId("sources-panel").isVisible(), "knowledge sources tab is present");
  await page.getByTestId("tab-json").click();
  ok((await page.getByTestId("json-text").inputValue()).includes('"facts"'), "raw JSON tab shows the whole case");

  // validate -> approve -> publish
  await page.getByTestId("tab-facts").click();
  await page.getByTestId("btn-validate").click();
  await page.waitForFunction(() => document.querySelector('[data-testid="validation-summary"]')?.getAttribute("data-ok") === "true", null, { timeout: 15000 }).catch(() => {});
  const okNow = (await page.getByTestId("validation-summary").getAttribute("data-ok")) === "true";
  if (!okNow) console.log("    findings:", await page.$$eval('[data-testid="issue"]', (els) => els.map((e) => `${e.getAttribute("data-path")}: ${e.textContent}`)));
  ok(okNow, "after the fixes the case validates");
  await shot(page, "studio-07-validated");
  await page.getByTestId("btn-approve").click();
  await page.waitForFunction(() => document.querySelector('[data-testid="case-editor"]')?.getAttribute("data-status") === "approved");
  ok(true, "approve: draft -> approved");
  await page.getByTestId("btn-publish").click();
  await page.waitForSelector('[data-testid="start-encounter"]');
  ok((await page.getByTestId("case-editor").getAttribute("data-status")) === "published", "publish: approved -> published");
  await shot(page, "studio-08-published");

  // editing a published version starts a new draft version and leaves v1 alone
  await page.getByTestId("tab-overview").click();
  const title = await page.getByTestId("f-title").inputValue();
  await page.getByTestId("f-title").fill(title + " (edited)");
  ok(await page.getByTestId("new-version-warning").isVisible(), "editing a published case explains that a new draft version will be created");
  await page.getByTestId("f-title").fill(title);

  // start the encounter with the new patient
  await page.getByTestId("start-encounter").click();
  await page.waitForSelector('[data-testid="encounter"]');
  ok((await page.getByTestId("chart-patient-name").innerText()).includes(NAME), "the encounter opens with the patient that was just published");
  const reply = await say(page, "Hello, I'm the resident on today. What brought you in?");
  ok(reply.includes("burning up since yesterday"), "the patient uses the wording edited in the Studio");
  await request(page, "order", "order:bmp");
  ok((await page.locator('[data-testid="lab-row"]').filter({ hasText: "Creatinine" }).count()) === 1, "the lab report added in the Studio is released on its request, with its row");
  await shot(page, "studio-09-encounter-with-new-patient");
  await page.getByTestId("finish-open").click();
  await page.getByTestId("disposition-discharge").click();
  await page.getByTestId("finish-summary").fill("Likely urinary infection; short encounter for the Studio check.");
  await page.getByTestId("finish-submit").click();
  await page.waitForSelector('[data-testid="feedback"]');
  ok((await page.getByTestId("objective").count()) >= 1, "feedback is produced for the new patient");
  const crit = await page.getByTestId("objective").first().innerText();
  ok(crit.includes("Characterises the urinary symptoms"), "feedback uses the objective edited in the Studio");

  // preview of a draft, and the description path
  const d = await j("/api/cases", { from_description: "A 52-year-old electrician named Tomas Varga with crushing chest pain for an hour. He is hiding that he used cocaine last night." });
  if (d.status === 201) {
    await page.goto(url(`/studio?case=${encodeURIComponent(d.data.case_id)}`));
    await page.waitForSelector('[data-testid="case-editor"]');
    ok((await page.getByTestId("editor-title").innerText()).includes("Tomas Varga"), "a draft made from a description opens in the editor");
    const [popup] = await Promise.all([page.context().waitForEvent("page"), page.getByTestId("btn-preview").click()]);
    await popup.waitForSelector('[data-testid="encounter"]', { timeout: 30000 });
    ok(/preview/i.test(await popup.locator("header").innerText()), "preview starts an encounter against the draft and labels it as a preview");
    await popup.close();
  } else problems.push(`POST /api/cases from_description -> ${d.status}`);
  await page.context().close();
}


// ------------------------------------------------------------------ a simulated patient from a running hospital
if (want("sim")) {
  console.log("sim patient (ws run, played encounter, write-back)");
  const ws = new WebSocket(api.replace(/^http/, "ws") + "/ws/sim");
  const got = await new Promise((resolve, reject) => {
    let run = null, enums = null, n = 0;
    const timer = setTimeout(() => reject(new Error("no playable patient within 90 s")), 90000);
    ws.onopen = () => ws.send(JSON.stringify({ type: "start", scenario: "normal_week", seed: 7, manager: "fixed", speed: 30 }));
    ws.onerror = () => reject(new Error("websocket error"));
    ws.onmessage = (m) => {
      const d = JSON.parse(m.data);
      if (d.type === "header") { run = d.run_id; enums = d.enums; }
      if (d.type === "snapshot" && run && ++n > 30) {
        const P = d.snapshot.patients, st = enums.patient_state;
        const c = P.id.map((id, i) => ({ id, state: st[P.state[i]] })).filter((p) => p.state === "with_provider" || p.state === "waiting_provider");
        c.sort((a, b) => (a.state === "with_provider" ? 0 : 1) - (b.state === "with_provider" ? 0 : 1));
        if (c.length) { clearTimeout(timer); ws.send(JSON.stringify({ type: "pause" })); ws.onmessage = null; resolve({ run, candidates: c, t: d.snapshot.t }); }
      }
    };
  }).catch((e) => { problems.push(`sim: ${e.message}`); return null; });
  if (got) {
    console.log(`    run ${got.run} at tick ${got.t}; candidates ${got.candidates.slice(0, 4).map((c) => `${c.id}:${c.state}`).join(", ")}`);
    const page = await newPage();
    let opened = false;
    for (const c of got.candidates.slice(0, 5)) {
      await page.goto(url(`/encounter?run_id=${got.run}&patient_id=${c.id}`));
      const which = await Promise.race([page.waitForSelector('[data-testid="encounter"]').then(() => "ok"), page.waitForSelector('[data-testid="error-card"]').then(() => "err")]);
      if (which === "ok") { opened = true; console.log(`    playing patient ${c.id} (${c.state})`); break; }
      console.log(`    patient ${c.id}: ${(await page.getByTestId("error-card").innerText()).replace(/\s+/g, " ").slice(0, 160)}`);
    }
    ok(opened, "a simulated patient opens as an encounter");
    if (opened) {
      const ctx = await page.getByTestId("sim-context").innerText();
      console.log("    header:", ctx);
      ok(/Bay \d+/.test(ctx) && /Day \d+ \d\d:\d\d/.test(ctx) && /occupying a bed/.test(ctx), "header shows bay, hospital model, simulated time and the occupying-a-bed line");
      await say(page, "Hello, I'm Dr Shah, the resident. What brought you in today?");
      await say(page, "When did it start?");
      await say(page, "I'm sorry, that sounds really uncomfortable. Do you take any medicines, and do you have any allergies?");
      await request(page, "order", "order:cbc");
      await shot(page, "encounter-10-sim-patient");
      await page.getByTestId("finish-open").click();
      await page.getByTestId("disposition-admit").click();
      await page.getByTestId("finish-summary").fill("Played from the running hospital for the write-back check.");
      await page.getByTestId("finish-submit").click();
      await page.waitForSelector('[data-testid="writeback-card"]');
      const flag = await page.getByTestId("written-back-flag").innerText();
      ok(/^(Applied|Queued)$/.test(flag.trim()), `write-back card shows ${flag.trim()}`);
      await page.waitForSelector('[data-testid="wb-confirmed"]', { timeout: 8000 }).catch(() => {});
      ok((await page.getByTestId("wb-confirmed").count()) === 1, "the run's own record of the patient lists the played interaction");
      ok((await page.getByTestId("contract-row").count()) === 4, "the four contract outputs are shown, sampled next to played");
      ok(await page.getByTestId("return-hospital").isVisible(), "a Return to hospital link is offered");
      await page.getByTestId("writeback-card").scrollIntoViewIfNeeded();
      await shot(page, "encounter-11-sim-writeback");
      await shot(page, "encounter-11-sim-writeback-card", { clip: await page.getByTestId("writeback-card").boundingBox() });
    }
    await page.context().close();
  }
  try { ws.send(JSON.stringify({ type: "stop" })); ws.close(); } catch {}
}


await browser.close();
console.log(`\n${passed.length} checks passed, ${problems.length} problem(s)`);
problems.forEach((p) => console.log(" -", p));
process.exit(problems.length ? 1 : 0);
