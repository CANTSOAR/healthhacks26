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
  await page.context().close();
}

/*STUDIO*/

/*SIM*/

await browser.close();
console.log(`\n${passed.length} checks passed, ${problems.length} problem(s)`);
problems.forEach((p) => console.log(" -", p));
process.exit(problems.length ? 1 : 0);
