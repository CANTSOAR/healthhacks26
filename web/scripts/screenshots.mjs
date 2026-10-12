// Drives the app in headless Chromium and saves screenshots of every mode.
//   node scripts/screenshots.mjs [baseUrl] [--gpu] [--dpr n] [--out <dir>] [--only <step>] [--api <serverUrl>] [--offline]
// --offline points the app at an unreachable server, so the fixture fallback is what gets photographed (files web-*.png).
// --api <url> uses that server; files are then named web-live-*.png and the live-only checks run as well.
// Default rendering is software GL (SwiftShader), which works on machines with no GPU but renders the 3D scene at
// about one frame a second; pass --gpu to use the machine's GPU through ANGLE/Metal (much faster on a Mac).
// Needs the browser installed in the project:  PLAYWRIGHT_BROWSERS_PATH=.playwright pnpm exec playwright install chromium
import fs from "node:fs";
import path from "node:path";

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const base = (argv.find((a, i) => /^https?:/.test(a) && !String(argv[i - 1]).startsWith("--")) ?? "http://localhost:3000").replace(/\/$/, "");
const here = path.dirname(new URL(import.meta.url).pathname);
const out = path.resolve(opt("--out", path.resolve(here, "../../overnight/screenshots")));
const only = opt("--only", "");
const offline = flag("--offline");
const apiUrl = offline ? "http://127.0.0.1:9" : opt("--api", "");
const liveRun = !offline && !!apiUrl;
const gpu = flag("--gpu");
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.resolve(here, "../.playwright");
fs.mkdirSync(out, { recursive: true });
const { chromium } = await import("playwright"); // after the browsers path is set

const args = gpu
  ? ["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"]
  : ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"];
// channel "chromium" = the full browser in new-headless mode; the bare headless shell never fires animation frames here
const browser = await chromium.launch({ channel: "chromium", args });
const settle = gpu ? 2600 : 9000;
const problems = [];

async function open(url, viewport = { width: 1440, height: 900 }) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: +opt("--dpr", gpu ? 2 : 1) });
  page.on("pageerror", (e) => problems.push(`${url}: ${String(e).slice(0, 300)}`));
  page.on("console", (m) => {
    if (m.type() === "error" && !/ERR_CONNECTION_REFUSED|Failed to load resource|WebSocket connection/.test(m.text())) problems.push(`${url}: console ${m.text().slice(0, 300)}`);
  });
  const u = new URL(base + url);
  if (apiUrl) u.searchParams.set("api", apiUrl);
  await page.goto(u.toString(), { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas", { timeout: 60000 });
  await page.waitForTimeout(settle);
  return page;
}
// overnight/screenshots is kept small: a curated set against the live server, and four fixture views.
// Every step still runs its checks; `--all` saves every view.
const KEEP_LIVE = new Set(["watch", "selection-bay-inspector", "play", "live-inject", "live-handover", "play-ended", "live-structural", "compare", "live-compare-two-managers", "tradeoff", "live-demo-tour", "narrow-watch", "narrow-inspector", "narrow-tradeoff", "hospital-layout", "live-tradeoff-human", "live-rejoin", "topbar-1280", "watch-window-end"]);
const KEEP_OFFLINE = new Set(["watch", "play", "compare", "tradeoff"]);
async function shot(page, name) {
  if (!flag("--all") && !(liveRun ? KEEP_LIVE : KEEP_OFFLINE).has(name)) return;
  const file = path.join(out, `web-${liveRun && !name.startsWith("live-") ? "live-" : ""}${name}.png`);
  await page.screenshot({ path: file, timeout: 120000 });
  console.log("saved", path.relative(process.cwd(), file));
}
const want = (name) => !only || name.includes(only);
const step = async (name, fn) => {
  if (!want(name)) return;
  try {
    await fn();
  } catch (e) {
    problems.push(`${name}: ${String(e).split("\n")[0]}`);
    console.log("FAILED", name, String(e).split("\n")[0]);
  }
};

await step("watch", async () => {
  const page = await open("/?mode=watch");
  await shot(page, "watch");
  // The timeline shows the whole episode; the 3D scene exists only for recorded windows.
  const clockOf = () => page.locator('[data-testid="clock"]').textContent();
  const windows = await page.locator("[data-window]").count();
  console.log("recorded windows offered:", windows, "| fixture banner:", await page.locator('[data-testid="fixture-banner-global"]').count(), "| SIMULATED tags:", await page.locator(".sim-tag", { hasText: /^simulated$/i }).count());
  if (offline && !(await page.locator('[data-testid="fixture-banner-global"]').count())) problems.push("offline: no global fixture banner");
  if (offline && (await page.locator(".sim-tag", { hasText: /^simulated$/i }).count())) problems.push("offline: charts still tagged SIMULATED");
  const tl = await page.locator('[data-testid="timeline"] svg').boundingBox();
  if (tl && windows > 0) {
    const c0 = await clockOf();
    if (windows > 1) {
      await page.locator("[data-window]").nth(1).click();
      await page.waitForTimeout(500);
      console.log("jump to second window:", c0, "->", await clockOf());
      if ((await clockOf()) === c0) problems.push("windows: jumping to the second window did not move the clock");
    }
    if (await page.locator('[data-testid="chart-zoom"]').count()) {
      // a long recording: a click far from every window moves only the chart cursor and says so
      const c1 = await clockOf();
      await page.mouse.click(tl.x + tl.width * 0.62, tl.y + tl.height * 0.5);
      await page.waitForTimeout(400);
      const note = await page.locator('[data-testid="no-recording"]').count();
      console.log("click outside the windows: note shown =", note, "| clock", c1, "->", await clockOf());
      if (!note) problems.push("timeline: clicking outside a recorded window gave no notice");
    }
    // run to the end of the window: playback must stop and offer what next, not loop
    await page.locator("[data-window]").first().click();
    await page.click('[aria-label="Simulation speed"] button:has-text("Max")');
    await page.waitForSelector('[data-testid="window-end"]', { timeout: 60000 }).catch(() => problems.push("windows: playback did not stop at the end of a window"));
    const cEnd = await clockOf();
    await page.waitForTimeout(1500);
    console.log("end of window:", (await page.locator('[data-testid="window-end"]').innerText().catch(() => "")).replace(/\s+/g, " "), "| clock stays", cEnd, "->", await clockOf());
    await shot(page, "watch-window-end");
    await page.locator('[data-testid="replay-window"]').click().catch(() => {});
    await page.click('[aria-label="Simulation speed"] button:has-text("4×")');
    await page.waitForTimeout(800);
  }
  // selection through search: a bay, with the inspector and its catalog definition open
  await page.fill('[data-testid="search"]', "Bay 4");
  await page.keyboard.press("Enter");
  await page.waitForSelector('[data-testid="inspector"]');
  await page.waitForSelector('[data-testid="catalog"]');
  await page.waitForTimeout(settle);
  // the variant's own attributes come first; shared ones sit in a collapsed group
  const own = await page.locator('[data-testid="catalog-own"] > div').count();
  const hasShared = await page.locator('[data-testid="catalog-shared-toggle"]').count();
  console.log("catalog: own attributes", own, "shared group", hasShared ? await page.locator('[data-testid="catalog-shared-toggle"]').textContent() : "none");
  const rows = await page.locator('[data-testid="inspector"]').innerText();
  const status = /Status\s*\n?\s*(.+)/.exec(rows)?.[1];
  const occ = /(Occupancy|In the room now)\s*\n?\s*(\d+) of (\d+)/.exec(rows);
  console.log("bay status:", status, "|", occ?.[1], occ?.[2], "of", occ?.[3]);
  if (occ && /^Occupied/.test(status ?? "") && occ[2] === "0") problems.push("inspector: status Occupied with occupancy 0");
  const hrefs = await page.locator('[data-testid="provenance-link"]').evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  console.log("provenance links:", JSON.stringify(hrefs));
  if (hrefs.some((h) => /%20|\s|\(/.test(h ?? ""))) problems.push("provenance: a link still has prose glued to the URL");
  await shot(page, "selection-bay-inspector");
  // a patient picked from the list: journey stepper
  await page.click('[data-tab="patients"]');
  await page.locator('[data-row^="patient:"]').nth(3).click();
  await page.waitForSelector('[data-testid="inspector"]');
  await page.waitForTimeout(settle);
  await shot(page, "selection-patient-journey");
  // picking in the 3D scene itself: click around the middle of the canvas until something is hit
  await page.keyboard.press("Escape");
  await page.click('[aria-label="Close inspector"]');
  // people in 3D: click where 20 of them are on screen, at the default zoom and again zoomed in
  const clickPeople = async (label) => {
    // ids spread over the hospital; each one is located on screen just before its click, because selecting someone
    // moves the camera
    const ids = await page.evaluate(() => {
      const p = window.__hg.feeds.a.getState().snap.patients;
      // interleave so the 20 tries are spread over wards, bays and waiting areas
      return p.id.filter((_, i) => i % 3 === 0).concat(p.id.filter((_, i) => i % 3 === 1));
    });
    let ok = 0, tried = 0, rooms = 0, wrong = 0, none = 0;
    for (const id of ids) {
      if (tried >= 20) break;
      const xy = await page.evaluate((pid) => { const q = window.__hg.project?.a?.("patient:" + pid); return q && document.elementFromPoint(q[0], q[1])?.tagName === "CANVAS" ? q : null; }, id);
      if (!xy) continue; // off screen or under a panel
      tried++;
      await page.mouse.click(xy[0], xy[1]);
      await page.waitForTimeout(gpu ? 150 : 900);
      const sel = await page.evaluate(() => window.__hg.ui.getState().selection);
      if (sel?.kind === "patient" && sel.id === id) ok++;
      else if (sel?.kind === "patient" || sel?.kind === "staff") wrong++;
      else if (sel) rooms++;
      else none++;
      await page.evaluate(() => window.__hg.ui.getState().select(null));
      await page.waitForTimeout(gpu ? 900 : 2500); // let the camera settle before the next one
    }
    console.log(`3D people clicks (${label}): ${ok} of ${tried} selected that person, ${wrong} a neighbouring person, ${rooms} a room or machine, ${none} nothing`);
    if (tried && (ok + wrong) / tried < 0.9) problems.push(`3D picking (${label}): only ${ok + wrong} of ${tried} clicks on people selected a person`);
  };
  await page.click('[aria-label="Pause"]');
  await page.waitForTimeout(600);
  await clickPeople("default zoom");
  await page.click('[aria-label="Zoom in"]');
  await page.click('[aria-label="Zoom in"]');
  await page.waitForTimeout(gpu ? 1800 : 6000);
  await clickPeople("zoomed in");
  await page.click('[aria-label="Reset view"]');
  await page.waitForTimeout(gpu ? 1500 : 5000);
  await page.click('[aria-label="Close inspector"]').catch(() => {});
  const vp = page.viewportSize();
  let hit = null;
  outer: for (const dy of [0, -40, 40, -80, 80, -120]) {
    for (const dx of [0, -60, 60, -120, 120, -180, 180]) {
      await page.mouse.click(vp.width / 2 + dx, vp.height / 2 - 40 + dy);
      await page.waitForTimeout(gpu ? 250 : 1500);
      if (await page.locator('[data-testid="inspector"]').count()) {
        hit = await page.locator('[data-testid="inspector"] .text-\\[17px\\]').first().textContent();
        break outer;
      }
    }
  }
  console.log("3D click picked:", hit ?? "nothing");
  if (!hit) problems.push("3D picking: no click on the canvas selected anything");
  await page.waitForTimeout(settle);
  await shot(page, "selection-3d-click");
  await page.click('[data-testid="status"]');
  await page.waitForSelector('[data-testid="status-pop"]');
  await shot(page, "status-indicator");
  await page.close();
});

await step("play", async () => {
  const page = await open("/?mode=play");
  await shot(page, "play-idle");
  await page.click('[data-testid="play-start"]');
  await page.waitForSelector('[data-cadence="hourly"]', { timeout: 20000 });
  await page.waitForTimeout(settle);
  await page.locator('[data-head="rn_night"] button').nth(3).click().catch(() => {});
  await page.waitForTimeout(600);
  await shot(page, "play");
  await page.click('[data-testid="play-stop"]');
  await page.waitForSelector('[data-testid="play-result"]', { timeout: 15000 });
  await page.waitForTimeout(600); // panels read the feed at most four times a second
  await shot(page, "play-ended");
  await page.close();
});

await step("compare", async () => {
  const page = await open("/?mode=compare");
  await page.waitForSelector('[data-testid="diff-table"]');
  await page.waitForTimeout(settle);
  await shot(page, "compare");
  await page.close();
});

await step("tradeoff", async () => {
  const page = await open("/?mode=tradeoff");
  await page.waitForSelector('[data-point], [data-testid="tradeoff-empty"]');
  await page.waitForTimeout(1500);
  await shot(page, "tradeoff");
  const npts = await page.locator("[data-point]").count();
  console.log("trade-off points:", npts, "validation card:", await page.locator('[data-testid="validation"]').count());
  if (npts > 0) {
    await page.locator("[data-point] circle").nth(Math.min(1, npts - 1)).click({ force: true });
    await page.waitForSelector('[data-testid="tradeoff-watch"]');
    await shot(page, "tradeoff-selected");
  }
  const toggles = page.locator("[data-scenario]");
  if ((await toggles.count()) > 1) {
    await toggles.nth(1).click();
    await page.waitForTimeout(400);
    await shot(page, "tradeoff-surge");
  }
  await page.close();
});

await step("narrow", async () => {
  const vp = { width: 390, height: 844 };
  let page = await open("/?mode=watch", vp);
  await shot(page, "narrow-watch");
  await page.mouse.click(195, 500);
  await page.click('[data-drawer="list"]');
  await page.waitForSelector('[data-testid="entity-list"]');
  await shot(page, "narrow-list");
  await page.locator("[data-row]").nth(2).click();
  await page.waitForSelector('[data-testid="inspector"]');
  await page.waitForTimeout(settle / 2);
  await shot(page, "narrow-inspector");
  await page.click('[data-drawer="controls"]');
  await page.waitForTimeout(500);
  await shot(page, "narrow-controls");
  await page.close();
  page = await open("/?mode=tradeoff", vp);
  await page.waitForSelector('[data-point], [data-testid="tradeoff-empty"]');
  await shot(page, "narrow-tradeoff");
  await page.close();
  page = await open("/?mode=compare", vp);
  await shot(page, "narrow-compare");
  await page.close();
});

await step("live", async () => {
  // Only with --api: the live websocket path against a running server (the real one, or scripts/mock-server.mjs).
  if (!liveRun) return;
  const page = await open("/?mode=play");
  await page.click('[data-testid="play-start"]');
  await page.waitForSelector('[data-cadence="hourly"]', { timeout: 20000 });
  await page.waitForTimeout(settle + 3000);
  const stats = await page.evaluate(
    () =>
      new Promise((res) => {
        let n = 0;
        const t0 = performance.now();
        const f = () => (++n, performance.now() - t0 > 3000 ? res({ fps: Math.round(n / 3), people: document.querySelector('[data-tab="patients"]')?.textContent, staff: document.querySelector('[data-tab="staff"]')?.textContent }) : requestAnimationFrame(f));
        requestAnimationFrame(f);
      }),
  );
  console.log("live run:", JSON.stringify(stats));
  const tick = () => page.evaluate(() => window.__hg.feeds.a.getState().snap?.t ?? -1);

  // 48x: the clock should advance at roughly 48 ticks a second (the server skips snapshots above 30 a second)
  await page.click('[aria-label="Simulation speed"] button:has-text("48×")');
  await page.waitForTimeout(1500);
  const t1 = await tick();
  await page.waitForTimeout(4000);
  const t2 = await tick();
  console.log("48x: ticks per second over 4 s =", ((t2 - t1) / 4).toFixed(1));
  if (t2 - t1 < 40) problems.push("48x: the clock barely advanced");

  // inject: all four events; each should be acknowledged, start at the next hour and reach the feed
  for (const id of ["flu_surge", "mass_casualty", "ct_outage", "rn_callouts"]) {
    await page.click(`[data-inject="${id}"]`);
    await page.waitForTimeout(700);
  }
  await page.click('[data-testid="play-panel"] .seg button:has-text("Decisions")');
  await page.waitForTimeout(gpu ? 5000 : 12000);
  const feed = await page.locator('[data-testid="decision-feed"]').innerText();
  const started = (feed.match(/Scenario event started|(?:Flu wave|Mass-casualty incident|Equipment outage|Staff callouts) started/g) ?? []).length;
  console.log("inject: scenario events in the feed =", started, "| toasts on screen =", await page.locator('[data-testid="toasts"] > div').count());
  if (started < 4) problems.push(`inject: only ${started} of 4 injected events reached the feed`);
  await shot(page, "live-inject");

  // hand-over to a manager and back
  await page.click('[aria-label="Simulation speed"] button:has-text("12×")');
  const options = await page.locator('[data-testid="manager-select"] option:not([disabled])').evaluateAll((os) => os.map((o) => o.value));
  const target = options.find((v) => /min_cost/.test(v)) ?? options.find((v) => v === "rule_based") ?? options.find((v) => v !== "human");
  if (target) {
    await page.selectOption('[data-testid="manager-select"]', target);
    await page.waitForSelector('[data-testid="take-back"]', { timeout: 10000 });
    await page.waitForTimeout(gpu ? 9000 : 15000);
    console.log("hand-over:", (await page.locator('[data-testid="in-charge"]').innerText()).replace(/\s+/g, " "), "| header manager:", await page.evaluate(() => window.__hg.feeds.a.getState().header.manager.id));
    const fed = await page.locator('[data-testid="decision-feed"]').innerText();
    console.log("hand-over: manager decisions in the feed =", (fed.match(/hourly|daily/g) ?? []).length);
    await shot(page, "live-handover");
    await page.click('[data-testid="take-back"]');
    await page.waitForTimeout(1500);
    const back = (await page.locator('[data-testid="in-charge"]').innerText()).replace(/\s+/g, " ");
    console.log("take-back:", back, "| header manager:", await page.evaluate(() => window.__hg.feeds.a.getState().header.manager.id));
    if (!/You/.test(back)) problems.push("take-back: the panel does not show the human in charge");
  } else problems.push("hand-over: no manager available to hand over to");

  await page.click('[data-testid="play-panel"] .seg button:has-text("Controls")');
  const picked = await page.evaluate(() => window.__hg.feeds.a.getState().snap?.patients.id[0]);

  // rejoin: reload, a mode switch, and a /?run_id=..&patient_id=.. link must all land back in the same run
  const runId = await page.evaluate(() => window.__hg.feeds.a.getState().header.id);
  const tBefore = await tick();
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas");
  await page.waitForTimeout(settle + 2500);
  const afterReload = await page.evaluate(() => ({ mode: window.__hg.ui.getState().mode, state: window.__hg.ui.getState().play.state, run: window.__hg.feeds.a.getState().header?.id, t: window.__hg.feeds.a.getState().snap?.t, note: window.__hg.ui.getState().play.note }));
  console.log("reload mid-run:", JSON.stringify(afterReload), "| same run:", afterReload.run === runId, "| tick before", tBefore);
  const attachWorks = afterReload.run === runId && afterReload.state === "live";
  if (!attachWorks) problems.push(`rejoin after reload did not attach (${afterReload.note ?? afterReload.state})`);
  if (attachWorks) {
    await page.click('[data-mode="watch"]');
    await page.waitForTimeout(settle);
    await page.click('[data-mode="play"]');
    await page.waitForTimeout(settle + 2000);
    const back = await page.evaluate(() => ({ state: window.__hg.ui.getState().play.state, run: window.__hg.feeds.a.getState().header?.id, t: window.__hg.feeds.a.getState().snap?.t }));
    console.log("Play -> Watch -> Play:", JSON.stringify(back), "| same run:", back.run === runId);
    if (back.run !== runId) problems.push("mode switch did not rejoin the run");
    await page.goto(`${base}/?run_id=${encodeURIComponent(runId)}&patient_id=${picked}&api=${encodeURIComponent(apiUrl)}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("canvas");
    await page.waitForTimeout(settle + 3000);
    const ret = await page.evaluate(() => ({ mode: window.__hg.ui.getState().mode, run: window.__hg.feeds.a.getState().header?.id, sel: window.__hg.ui.getState().selection, url: location.search }));
    console.log("return by run link:", JSON.stringify(ret));
    if (ret.run !== runId || ret.mode !== "play") problems.push("return link did not land in Play on the same run");
    await shot(page, "live-rejoin");
    // changing scenario mid-run asks first; declining keeps both the run and the menu as they were
    page.once("dialog", (d) => d.dismiss());
    const scBefore = await page.locator('[data-testid="scenario"]').inputValue();
    await page.selectOption('[data-testid="scenario"]', { index: 1 });
    await page.waitForTimeout(500);
    console.log("scenario change mid-run declined: menu", scBefore, "->", await page.locator('[data-testid="scenario"]').inputValue(), "| run still", await page.evaluate(() => window.__hg.ui.getState().play.state));
  }
  await page.click('[data-testid="play-stop"]');
  await page.waitForSelector('[data-testid="play-result"]', { timeout: 15000 });
  await page.waitForTimeout(600);
  console.log("live run result:", (await page.locator('[data-testid="play-result"]').textContent())?.replace(/\s+/g, " ").slice(0, 200));
  await shot(page, "live-ended");
  await page.goto(base + "/?mode=tradeoff&api=" + encodeURIComponent(apiUrl));
  await page.waitForSelector('[data-point], [data-testid="tradeoff-empty"]');
  await page.waitForTimeout(1500);
  if (await page.locator('[data-testid="xaxis-toggle"]').count()) await page.click('[data-testid="xaxis-toggle"] button:has-text("Total cost")');
  await page.waitForTimeout(500);
  console.log("human point on trade-off chart (total cost axis):", await page.locator('[data-point="__human"]').count(), "| x-axis toggle:", await page.locator('[data-testid="xaxis-toggle"]').count());
  if (await page.locator('[data-point="__human"]').count()) {
    await page.locator('[data-point="__human"] circle').first().click({ force: true });
    await page.waitForTimeout(400);
    console.log("human caveat:", (await page.locator('[data-testid="human-caveat"]').count()) ? (await page.locator('[data-testid="human-caveat"]').innerText()).slice(0, 90) : "none");
  }
  await shot(page, "live-tradeoff-human");
  await page.close();
  // live Compare: two sockets, same scenario and seed, two managers
  const cmp = await open("/?mode=compare");
  await cmp.click('[data-testid="compare-live-tab"]');
  await cmp.click('[data-testid="compare-live-start"]');
  await cmp.waitForSelector('[data-testid="compare-live-stop"]', { timeout: 20000 });
  await cmp.click('[aria-label="Simulation speed"] button:has-text("12×")');
  await cmp.waitForTimeout(gpu ? 22000 : 40000);
  const clocks = await cmp.evaluate(() => document.querySelector('[data-testid="clock"]')?.textContent);
  console.log("live compare clock:", clocks);
  await shot(cmp, "live-compare-two-managers");
  await cmp.click('[data-testid="compare-live-stop"]');
  await cmp.waitForTimeout(1500);
  await cmp.close();
});

await step("structural", async () => {
  // A structural change end to end (slow: the build delay is weeks of simulated time). Human sets "add bays" and
  // "add ward beds"; they apply at the next monthly boundary, and a `layout` message follows when the work completes.
  if (!liveRun) return;
  const page = await open("/?mode=play");
  await page.click('[data-testid="play-start"]');
  await page.waitForSelector('[data-cadence="monthly"]', { timeout: 20000 });
  await page.click('[data-cadence="monthly"] > button');
  await page.locator('[data-head="bays_delta"] button').last().click();
  await page.locator('[data-head="ward_beds_delta"] button').last().click();
  await page.waitForTimeout(800);
  console.log("structural: queued =", (await page.locator('[data-head="bays_delta"]').innerText()).split("\n").slice(0, 2).join(" | "));
  const state = () => page.evaluate(() => { const f = window.__hg.feeds.a.getState(); return { rev: f.layoutRev, v: f.layout?.version, beds: document.querySelector('[data-tab="beds"]')?.textContent, day: f.snap ? f.snap.clock.day + 1 : 0, phys: f.layout?.rooms.filter((r) => r.physical !== false).length }; });
  const before = await state();
  await page.click('[aria-label="Simulation speed"] button:has-text("Max")');
  let now = before;
  let changes = 0;
  const t0 = Date.now();
  while (Date.now() - t0 < 9 * 60000) {
    await page.waitForTimeout(5000);
    const s = await state();
    if (s.rev !== now.rev) {
      changes++;
      console.log(`structural: layout message on day ${s.day}: version ${now.v} -> ${s.v}, rooms built ${now.phys} -> ${s.phys}, ${now.beds} -> ${s.beds}`);
      now = s;
      if (s.phys !== before.phys) break;
    }
  }
  if (!changes) problems.push("structural: no layout message arrived within 9 minutes");
  else if (now.phys === before.phys) problems.push("structural: layout messages arrived but the number of built rooms did not change");
  await page.click('[aria-label="Simulation speed"] button:has-text("4×")');
  await page.waitForTimeout(settle + 1500);
  await shot(page, "live-structural");
  await page.click('[data-testid="play-stop"]');
  await page.waitForTimeout(1500);
  await page.close();
});

await step("tour", async () => {
  const page = await open("/?mode=watch");
  await page.click('[data-testid="tour-button"]');
  await page.waitForSelector('[data-testid="tour-card"]', { timeout: 30000 });
  const seen = [];
  for (let i = 0; i < 7; i++) {
    await page.waitForFunction(() => !/Loading/.test(document.querySelector('[data-testid="tour-next"]')?.textContent ?? "Loading"), null, { timeout: 60000 });
    await page.waitForTimeout(i === 1 ? settle + 4000 : settle);
    const card = (await page.locator('[data-testid="tour-card"]').innerText()).split("\n");
    seen.push(`${card[0].replace(/.*step /, "step ")}: ${card[1]} [${await page.evaluate(() => new URLSearchParams(location.search).get("mode"))}]`);
    if (i === 1) await shot(page, "live-demo-tour");
    const label = await page.locator('[data-testid="tour-next"]').textContent();
    if (/Finish/.test(label ?? "")) break;
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(600);
  }
  console.log("tour:", seen.join(" -> "));
  await page.keyboard.press("ArrowLeft");
  await page.waitForTimeout(1500);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  if (await page.locator('[data-testid="tour-card"]').count()) problems.push("tour: Escape did not close the tour");
  await page.close();
});

await step("hospital", async () => {
  // the real-site layout on its own (Play before a run starts)
  const page = await open("/?mode=play", { width: 1600, height: 1000 });
  await shot(page, "hospital-layout");
  // the top bar must fit from 1280 px: status pill, tour button and hospital menu all inside the viewport
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(700);
  const fit = await page.evaluate(() => ["status", "tour-button", "hospital", "scenario", "search", "clock"].map((id) => { const r = document.querySelector(`[data-testid="${id}"]`)?.getBoundingClientRect(); return [id, r ? Math.round(r.left) : null, r ? Math.round(r.right) : null]; }));
  console.log("top bar at 1280:", JSON.stringify(fit));
  if (fit.some(([, l, r]) => l == null || l < 0 || r > 1280)) problems.push("top bar: something is off-screen at 1280 px");
  await shot(page, "topbar-1280");
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.waitForTimeout(500);
  // a different layout redraws the building: the bed count in the list follows the layout
  const before = await page.locator('[data-tab="beds"]').textContent();
  const options = await page.locator('[data-testid="hospital"] option').count();
  if (options > 1) {
    await page.selectOption('[data-testid="hospital"]', { index: 1 });
    await page.waitForTimeout(settle);
    const after = await page.locator('[data-tab="beds"]').textContent();
    console.log("layout switch:", before, "->", after);
    if (before === after) problems.push("layout switch: bed count did not change");
    await shot(page, "hospital-layout-switched");
  }
  await page.close();
});

await browser.close();
if (problems.length) {
  console.log("\nProblems:");
  for (const p of problems) console.log(" -", p);
}
console.log(problems.length ? `done with ${problems.length} problem(s)` : "done, no page errors");
