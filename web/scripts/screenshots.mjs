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
async function shot(page, name) {
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
  // scrubbing: a click on the hourly chart jumps the replay to the nearest recorded snapshot
  const clockBefore = await page.locator('[data-testid="clock"]').textContent();
  const tl = await page.locator('[data-testid="timeline"] svg').boundingBox();
  if (tl) {
    await page.mouse.click(tl.x + tl.width * 0.36, tl.y + tl.height * 0.5);
    await page.waitForTimeout(300);
    const clockAfter = await page.locator('[data-testid="clock"]').textContent();
    console.log("scrub:", clockBefore, "->", clockAfter);
    if (clockBefore === clockAfter) problems.push("scrub: clock did not move");
  }
  // selection through search: a bay, with the inspector and its catalog definition open
  await page.fill('[data-testid="search"]', "Bay 4");
  await page.keyboard.press("Enter");
  await page.waitForSelector('[data-testid="inspector"]');
  await page.waitForSelector('[data-testid="catalog"]');
  await page.waitForTimeout(settle);
  await shot(page, "selection-bay-inspector");
  // a patient picked from the list: journey stepper + "Play this encounter"
  await page.click('[data-tab="patients"]');
  await page.locator('[data-row^="patient:"]').nth(3).click();
  await page.waitForSelector('[data-testid="play-encounter"]');
  await page.waitForTimeout(settle);
  await shot(page, "selection-patient-journey");
  // picking in the 3D scene itself: click around the middle of the canvas until something is hit
  await page.keyboard.press("Escape");
  await page.click('[aria-label="Close inspector"]');
  await page.click('[aria-label="Pause"]');
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
  await page.locator('[data-head="rn_night"] button').nth(4).click();
  await page.waitForTimeout(500);
  await shot(page, "live-play");
  await page.click('[data-tab="patients"]');
  await page.locator('[data-row^="patient:"]').nth(5).click();
  await page.waitForSelector('[data-testid="play-encounter"]');
  await page.waitForTimeout(settle);
  await shot(page, "live-patient");
  await page.click('[data-testid="play-stop"]');
  await page.waitForSelector('[data-testid="play-result"]', { timeout: 15000 });
  await page.waitForTimeout(600);
  console.log("live run result:", (await page.locator('[data-testid="play-result"]').textContent())?.replace(/\s+/g, " ").slice(0, 200));
  await shot(page, "live-ended");
  await page.goto(base + "/?mode=tradeoff&api=" + encodeURIComponent(apiUrl));
  await page.waitForSelector('[data-point], [data-testid="tradeoff-empty"]');
  await page.waitForTimeout(1500);
  console.log("human point on trade-off chart:", await page.locator('[data-point="__human"]').count());
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

await step("hospital", async () => {
  // the real-site layout on its own (Play before a run starts)
  const page = await open("/?mode=play", { width: 1600, height: 1000 });
  await shot(page, "hospital-layout");
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
