// Checks a static snapshot build: node scripts/check-static.mjs <url> <outDir>
import { chromium } from "playwright";
import path from "node:path";
const here = path.dirname(new URL(import.meta.url).pathname);
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.resolve(here, "../.playwright");
const url = (process.argv[2] ?? "http://localhost:8090/healthhacks26/").replace(/\/?$/, "/");
const out = process.argv[3] ?? ".";
const browser = await chromium.launch({ channel: "chromium", args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const errors = [], failed = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("requestfailed", (r) => failed.push(r.url().slice(0, 140)));
page.on("response", (r) => { if (r.status() >= 400) failed.push(r.status() + " " + r.url().slice(0, 140)); });
for (const mode of ["watch", "compare", "tradeoff", "play"]) {
  await page.goto(`${url}?mode=${mode}`, { waitUntil: "networkidle", timeout: 120000 }).catch((e) => errors.push("goto " + mode + ": " + String(e).slice(0, 120)));
  await page.waitForTimeout(9000);
  await page.screenshot({ path: path.join(out, `static-${mode}.png`) });
  const text = await page.locator("body").innerText();
  console.log(mode, "| fixture banner:", /fixture data/i.test(text), "| snapshot banner:", /Recorded snapshot/.test(text), "| chars:", text.length);
}
for (const p of ["encounter/", "studio/", "journey/"]) {
  await page.goto(url + p, { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(out, `static-${p.replace("/", "")}.png`) });
}
console.log("page errors:", errors.length, errors.slice(0, 5));
console.log("failed requests:", [...new Set(failed)].slice(0, 15));
await browser.close();
