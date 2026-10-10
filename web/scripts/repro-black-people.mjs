// Checks that people in the 3D scene are drawn in their colours, not black.
//   node scripts/repro-black-people.mjs [baseUrl] [--case compare-live|compare-recorded|play-switch] [--runs n] [--shot file.png] [--verbose]
// Needs the dev server (the debug hook `window.__sceneDebug` exists only in development, see components/scene/SceneDebug.tsx)
// and, for the live cases, the API on :8000. Uses the machine's GPU (shadows are part of the bug).
// To see the bug: `--case play-switch --query dbgupload=three` (people come out black in about half the runs).
// Per pane it reads back the pixels drawn over standing people and prints PASS when fewer than 20 % of them are near-black.
import path from "node:path";

const argv = process.argv.slice(2);
const opt = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const base = (argv.find((a, i) => /^https?:/.test(a) && !String(argv[i - 1]).startsWith("--")) ?? "http://localhost:3000").replace(/\/$/, "");
const here = path.dirname(new URL(import.meta.url).pathname);
const which = opt("--case", "compare-live");
const runs = +opt("--runs", 3);
const shotFile = opt("--shot", "");
const verbose = argv.includes("--verbose");
const hold = +opt("--hold", 0); // seconds to keep the live run going before judging, reporting when the dark share changes
const extra = opt("--query", ""); // extra query string, e.g. dbgupload=three, which switches the fix off (development only)
const trials = +opt("--trials", 0); // compare-live: extra layout announcements per run
const speed = opt("--speed", "12×");
async function watch(page, panes) {
  let lastState = "";
  for (let t = 0; t < hold; t += 2) {
    await page.waitForTimeout(2000);
    const d = await read(page);
    const amb = await page.evaluate(() => Object.fromEntries(Object.entries(window.__hg.feeds).map(([k, f]) => [k, f.getState().snap?.ambulances?.length ?? 0])));
    const state = panes.map((k) => `${k}:${d[k] && d[k].sampled ? (d[k].dark / d[k].sampled < 0.2 ? "ok" : "BLACK") : "-"} amb ${amb[k]}`).join("  ");
    if (state !== lastState) console.log(`  t+${t}s clock ${await page.locator('[data-testid="clock"]').first().textContent()}  ${state}`);
    lastState = state;
  }
}
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.resolve(here, "../.playwright");
const { chromium } = await import("playwright");
const browser = await chromium.launch({ channel: "chromium", args: argv.includes("--software") ? ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] : ["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"] });

const read = (page) => page.evaluate(() => JSON.parse(JSON.stringify(window.__sceneDebug ?? {})));
/** Wait until every expected pane has at least `min` sampled people, then judge it. */
async function judge(page, panes, label, min = 8, timeout = 90000) {
  const t0 = Date.now();
  let d = {};
  while (Date.now() - t0 < timeout) {
    await page.waitForTimeout(1000);
    d = await read(page);
    if (panes.every((k) => (d[k]?.sampled ?? 0) >= min)) break;
  }
  await page.waitForTimeout(1500);
  d = await read(page);
  let ok = true;
  for (const k of panes) {
    const s = d[k];
    if (!s || s.sampled < min) {
      const why = await page.evaluate((k) => {
        const f = window.__hg.feeds[k].getState();
        return `snapshot ${f.snap ? "present" : "none"}, live compare state "${window.__hg.ui.getState().compareLive}", note ${window.__hg.ui.getState().compareNote}`;
      }, k).catch(() => "");
      console.log(`  ${label} pane ${k}: INCONCLUSIVE (sampled ${s?.sampled ?? 0} people; ${why})`);
      ok = false;
      continue;
    }
    const pass = s.dark / s.sampled < 0.2;
    ok &&= pass;
    const people = s.meshes.filter((m) => m.geo === "CapsuleGeometry" || m.geo === "SphereGeometry");
    console.log(`  ${label} pane ${k}: ${pass ? "PASS" : "FAIL"}  dark ${s.dark}/${s.sampled}  people ${s.people}  ` + people.map((m) => `${m.geo.slice(0, 4)}#${m.id}{count ${m.count}, instanceColor ${m.hasInstanceColor}, prog ${m.program}, progInstColor ${m.programInstancingColor}, attrLoc ${m.colorAttrLocation}, rgb ${m.colors.slice(0, 3)}, vao ${JSON.stringify(m.vao)}}`).join(" "));
    if (verbose) console.log(JSON.stringify(s, null, 1));
    if (!pass && argv.includes("--vao")) {
      // look at the GL state only now, so the probe cannot have changed how the failure came about
      await page.evaluate(() => (window.__sceneDebugProbe = true));
      await page.waitForTimeout(2500);
      const after = (await read(page))[k];
      console.log(`    probed: dark now ${after.dark}/${after.sampled}  ` + after.meshes.filter((m) => m.vao).map((m) => `${m.geo.slice(0, 4)}#${m.id} cast ${m.cast} recv ${m.receive} prog ${m.program} ${JSON.stringify(m.vao)}`).join(" | "));
      await page.evaluate(() => (window.__sceneDebugProbe = false));
    }
  }
  return ok;
}

async function open(url) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await page.addInitScript((v) => {
    window.__sceneDebugOn = v;
  }, argv.includes("--vao") ? "vao" : true);
  page.on("pageerror", (e) => console.log("  pageerror:", String(e).slice(0, 200)));
  if (extra) url += (url.includes("?") ? "&" : "?") + extra;
  await page.goto(base + url, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas", { timeout: 60000 });
  await page.waitForTimeout(3000);
  return page;
}

const cases = {
  "compare-live": async () => {
    const page = await open("/?mode=compare");
    await page.click('[data-testid="compare-live-tab"]');
    await page.click('[data-testid="compare-live-start"]');
    await page.waitForSelector('[data-testid="compare-live-stop"]', { timeout: 20000 });
    await page.click(`[aria-label="Simulation speed"] button:has-text("${speed}")`);
    await page.waitForTimeout(12000);
    await watch(page, ["a", "b"]);
    let ok = await judge(page, ["a", "b"], "live compare");
    // More draws of the same lottery in one page: drop the current snapshot and announce a "new" layout on both feeds,
    // which is what a websocket header does. Whether people then come back black depends on which animation frame the
    // next snapshot lands on (see Lights in components/scene/HospitalScene.tsx).
    for (let t = 1; t <= trials; t++) {
      await page.evaluate(() => {
        for (const k of ["a", "b"]) window.__hg.feeds[k].setState((s) => ({ snap: null, layoutRev: s.layoutRev + 1 }));
      });
      await page.waitForTimeout(2500);
      ok = (await judge(page, ["a", "b"], `live compare, re-layout ${t}`, 8, 15000)) && ok;
    }
    if (shotFile) await page.screenshot({ path: shotFile, timeout: 120000 });
    if (await page.locator('[data-testid="compare-live-stop"]').count()) await page.click('[data-testid="compare-live-stop"]');
    await page.waitForTimeout(1200);
    await page.close();
    return ok;
  },
  "compare-recorded": async () => {
    const page = await open("/?mode=compare");
    await page.waitForTimeout(3000);
    const ok = await judge(page, ["a", "b"], "recorded compare");
    if (shotFile) await page.screenshot({ path: shotFile, timeout: 120000 });
    await page.close();
    return ok;
  },
  // single scene: a live run, then another hospital (a different layout, so the building is rebuilt) and a second run
  "play-switch": async () => {
    const page = await open("/?mode=play");
    page.on("dialog", (d) => d.accept());
    const run = async (label) => {
      await page.click('[data-testid="play-start"]');
      await page.waitForTimeout(1500);
      await page.click(`[aria-label="Simulation speed"] button:has-text("${speed}")`);
      await page.waitForTimeout(8000);
      const keys = Object.keys(await read(page));
      return judge(page, keys.length ? keys : ["a"], label);
    };
    let ok = await run("play live, first hospital");
    const options = await page.locator('[data-testid="hospital"] option').count();
    for (let i = 1; i < Math.min(options, 3); i++) {
      await page.selectOption('[data-testid="hospital"]', { index: i });
      await page.waitForTimeout(4000);
      ok = (await run(`play live, hospital option ${i}`)) && ok;
    }
    if (options < 2) console.log("  only one hospital offered: switch not exercised");
    if (shotFile) await page.screenshot({ path: shotFile, timeout: 120000 });
    if (await page.locator('[data-testid="play-stop"]').count()) await page.click('[data-testid="play-stop"]');
    await page.waitForTimeout(1500);
    await page.close();
    return ok;
  },
};

let passed = 0;
for (let i = 1; i <= runs; i++) {
  console.log(`${which} run ${i}/${runs}`);
  try {
    if (await cases[which]()) passed++;
  } catch (e) {
    console.log("  run aborted (not a colour verdict):", String(e).split("\n")[0]);
    for (const c of browser.contexts()) await c.close().catch(() => {});
  }
}
console.log(`${which}: ${passed}/${runs} runs PASS`);
await browser.close();
process.exit(passed === runs ? 0 : 1);
