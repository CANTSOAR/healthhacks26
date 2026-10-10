// Builds the offline fixture set in web/public/fixtures/ from contracts/ and catalog/.
// Everything written here is FIXTURE data: placeholder numbers, not simulator or evaluation output.
// Usage: node scripts/make-fixtures.mjs
import fs from "node:fs";
import path from "node:path";
import { parse } from "yaml";

const here = path.dirname(new URL(import.meta.url).pathname);
const root = path.resolve(here, "../..");
const out = path.resolve(here, "../public/fixtures");
fs.mkdirSync(out, { recursive: true });
const readYaml = (p) => parse(fs.readFileSync(path.join(root, p), "utf8"));
const readJson = (p) => JSON.parse(fs.readFileSync(path.join(root, p), "utf8"));
const write = (name, data) => {
  fs.writeFileSync(path.join(out, name), JSON.stringify(data));
  console.log("wrote", name, (fs.statSync(path.join(out, name)).size / 1024).toFixed(1) + " kB");
};

// ---- straight copies of the contract fixtures
for (const f of ["layout.fixture.json", "rollout.fixture.json", "snapshot.fixture.json"]) {
  fs.copyFileSync(path.join(root, "contracts/fixtures", f), path.join(out, f));
  console.log("copied", f);
}
const enums = readYaml("contracts/enums.yaml");
const metrics = readYaml("contracts/metrics.yaml");
write("enums.json", enums);
write("metrics.json", metrics);

// ---- catalog: /api/catalog and /api/catalog/ref/*
const catalogFiles = ["patient", "staff", "space", "equipment", "event"];
const entityTypes = [];
const refs = {};
const sharedKeys = {};
const totals = { n_variants: 0, n_attributes: 0, by_source: { measured: 0, literature: 0, assumed: 0 } };
const addCatalog = (file) => {
  let doc;
  try {
    doc = readYaml(file);
  } catch {
    return;
  }
  if (!doc || !doc.variants) return;
  const by = { measured: 0, literature: 0, assumed: 0 };
  let nAttr = 0;
  const count = (attrs) => {
    for (const a of Object.values(attrs || {})) {
      if (a && typeof a === "object" && a.source) {
        by[a.source] = (by[a.source] || 0) + 1;
        nAttr++;
      }
    }
  };
  count(doc.shared);
  sharedKeys[doc.entity_type] = Object.keys(doc.shared || {});
  for (const [variant, v] of Object.entries(doc.variants)) {
    count(v.attributes);
    refs[`${doc.entity_type}/${variant}`] = {
      entity_type: doc.entity_type,
      variant,
      label: v.label,
      attributes: { ...(doc.shared || {}), ...(v.attributes || {}) },
      fixture: true,
    };
  }
  const n = Object.keys(doc.variants).length;
  entityTypes.push({ entity_type: doc.entity_type, description: doc.description, n_variants: n, n_attributes: nAttr, by_source: by });
  totals.n_variants += n;
  totals.n_attributes += nAttr;
  for (const k of Object.keys(by)) totals.by_source[k] += by[k];
};
for (const f of catalogFiles) addCatalog(`catalog/${f}.yaml`);
for (const dir of ["catalog/hospitals", "catalog/conditions"]) {
  const abs = path.join(root, dir);
  if (!fs.existsSync(abs)) continue;
  for (const f of fs.readdirSync(abs)) if (f.endsWith(".yaml")) addCatalog(`${dir}/${f}`);
}
write("catalog.json", { entity_types: entityTypes, totals, fixture: true });
write("catalog-refs.json", refs);
write("catalog-shared.json", sharedKeys);

// ---- a second rollout derived from the fixture so Compare has two managers on the same seed.
// It is a mechanical edit of the fixture (fewer people in waiting states, scaled hourly series), NOT a simulator run.
const base = readJson("contracts/fixtures/rollout.fixture.json");
const variant = JSON.parse(JSON.stringify(base));
variant.header.rollout_id = "fixture_b";
variant.header.manager = {
  id: "fixture_variant",
  kind: "rule_based",
  label: "Fixture variant (derived, not a simulator run)",
  objective: "none",
};
const scale = { wait_mean_min: 0.62, wait_p95_min: 0.7, door_to_provider_sum_min: 0.62, waiting_count: 0.6, lwbs: 0.5, lwbs_rate: 0.5, cost_total: 1.18, cost_labor: 1.25, margin: 0.8, ed_census: 0.88, rn_utilization: 0.85, md_utilization: 0.88, staff_on_shift: 1.2 };
for (const [k, s] of Object.entries(scale)) if (variant.hourly[k]) variant.hourly[k] = variant.hourly[k].map((v) => +(v * s).toFixed(3));
const WAITING = new Set([0, 2]);
for (const seg of variant.segments) {
  for (const snap of seg.snapshots) {
    const p = snap.patients;
    const keep = p.id.map((id, i) => !(WAITING.has(p.state[i]) && id % 3 !== 0));
    for (const col of Object.keys(p)) p[col] = p[col].filter((_, i) => keep[i]);
    const k = snap.kpis;
    if (typeof k.wait_mean_min === "number") k.wait_mean_min = +(k.wait_mean_min * 0.62).toFixed(1);
    if (typeof k.wait_p95_min === "number") k.wait_p95_min = Math.round(k.wait_p95_min * 0.7);
    if (typeof k.waiting_count === "number") k.waiting_count = p.state.filter((s) => s <= 3).length;
    if (typeof k.ed_census === "number") k.ed_census = p.state.filter((s) => s < 9).length;
    if (typeof k.lwbs_rate === "number") k.lwbs_rate = +(k.lwbs_rate * 0.5).toFixed(3);
    k.settings = { ...k.settings, rn_day: 3, rn_evening: 3, triage_nurses: 2 };
  }
}
variant.decisions = [
  { t: 96, head: "triage_nurses", value: 2, prev: 1, cadence: "daily", label: "Triage stations staffed: one -> two" },
  { t: 132, head: "call_in", value: 1, prev: 0, cadence: "hourly", label: "Call in: none -> one_rn" },
  { t: 180, head: "fast_track", value: 1, prev: 0, cadence: "hourly", label: "Fast track: closed -> open" },
  ...variant.decisions,
];
for (const seg of variant.segments) for (const snap of seg.snapshots) snap.decisions = variant.decisions.filter((d) => d.t === snap.t);
const s = variant.header.summary;
variant.header.summary = { ...s, wait_mean_min: +(s.wait_mean_min * 0.62).toFixed(2), wait_p95_min: +(s.wait_p95_min * 0.7).toFixed(1), cost_per_day: Math.round(s.cost_per_day * 1.18), margin_per_day: Math.round(s.margin_per_day * 0.8) };
write("rollout.fixture_b.json", variant);

// ---- list endpoints
const sm = (r) => ({ rollout_id: r.header.rollout_id, manager: r.header.manager, scenario: r.header.scenario, seed: r.header.seed, days: r.header.days, summary: r.header.summary, has_segments: r.segments.length > 0 });
write("rollouts.json", [sm(base), sm(variant)]);

write("status.json", {
  services: {
    sim: { live: false },
    llm: { live: false, provider: "offline", model: null },
    voice: { live: false, provider: "browser" },
    data: { live: false, provider: "public_extracts" },
  },
  torch: null,
  device: null,
  version: "fixture",
  fixture: true,
});
write("scenarios.json", [
  { id: "normal_week", label: "Normal week", description: "Fixture scenario list (server offline). Typical demand.", hospital_id: "rwjuh_nb", days_default: 7 },
  { id: "flu_surge", label: "Flu surge", description: "Fixture scenario list (server offline). Respiratory demand wave.", hospital_id: "rwjuh_nb", days_default: 14 },
]);
const layout = readJson("contracts/fixtures/layout.fixture.json");
// the real-site layout built by the catalog workstream (if present) is the default hospital offline
const hospitals = [];
const real = path.join(root, "catalog/hospitals/rwjuh_nb.layout.json");
if (fs.existsSync(real)) {
  fs.copyFileSync(real, path.join(out, "rwjuh_nb.layout.json"));
  const l = JSON.parse(fs.readFileSync(real, "utf8"));
  hospitals.push({ id: l.hospital_id, name: l.name, disclaimer: l.disclaimer });
  console.log("copied rwjuh_nb.layout.json");
}
hospitals.push({ id: layout.hospital_id, name: layout.name, disclaimer: layout.disclaimer });
write("hospitals.json", hospitals);

const W = (cost, wait, lwbs, safety) => ({ cost, wait, lwbs, safety, boarding: 0.2, staff: 0.1, revenue: 0 });
const managers = [
  { id: "fixture_fixed", kind: "fixed", label: "Fixed staffing, FCFS", objective: "none", reward_weights: null, available: true, rollout_id: "fixture" },
  { id: "fixture_variant", kind: "rule_based", label: "Rule-based manager", objective: "none", reward_weights: null, available: true, rollout_id: "fixture_b" },
  { id: "fx_random", kind: "random", label: "Random actions", objective: "none", reward_weights: null, available: false },
  { id: "fx_tuned_cost", kind: "tuned_heuristic", label: "Tuned heuristic (cost)", objective: "min_cost", reward_weights: W(1, 0.1, 0.2, 0.5), available: false },
  { id: "fx_tuned_wait", kind: "tuned_heuristic", label: "Tuned heuristic (wait)", objective: "min_wait", reward_weights: W(0.1, 1, 0.5, 0.5), available: false },
  { id: "fx_ppo_cost", kind: "learned", label: "PPO, cost-tuned", objective: "min_cost", reward_weights: W(1, 0.1, 0.2, 0.5), available: false },
  { id: "fx_ppo_wait", kind: "learned", label: "PPO, wait-tuned", objective: "min_wait", reward_weights: W(0.1, 1, 0.5, 0.5), available: false },
  { id: "fx_ppo_bal", kind: "learned", label: "PPO, balanced", objective: "balanced", reward_weights: W(0.5, 0.5, 0.5, 0.5), available: false },
].map((m) => ({ ...m, label: m.label + " [fixture]" }));
write("managers.json", managers);

// Placeholder points for the trade-off chart. Hand-typed so the chart has a shape to draw; NOT evaluation results.
const pts = {
  fixture_fixed: [70560, 44.2, 0.04],
  fixture_variant: [83260, 27.4, 0.02],
  fx_random: [96500, 71.0, 0.09],
  fx_tuned_cost: [61800, 52.5, 0.05],
  fx_tuned_wait: [98200, 16.8, 0.01],
  fx_ppo_cost: [57900, 63.1, 0.07],
  fx_ppo_wait: [104300, 12.6, 0.008],
  fx_ppo_bal: [72400, 24.9, 0.018],
};
const stat = (mean, rel) => ({ mean: +mean.toFixed(3), std: +(mean * rel).toFixed(3), ci95: +(mean * rel * 0.88).toFixed(3) });
const rows = [];
for (const scenario of ["normal_week", "flu_surge"]) {
  const surge = scenario === "flu_surge";
  for (const m of managers) {
    const [c, w, l] = pts[m.id];
    const brittle = m.id.includes("cost") || m.kind === "fixed" ? 2.3 : 1.45;
    rows.push({
      manager_id: m.id, kind: m.kind, label: m.label, objective: m.objective, scenario, n_seeds: 5, rollout_id: m.rollout_id,
      metrics: {
        cost_per_day: stat(c * (surge ? 1.07 : 1), 0.05),
        wait_mean_min: stat(w * (surge ? brittle : 1), 0.14),
        wait_p95_min: stat(w * (surge ? brittle : 1) * 2.6, 0.16),
        lwbs_rate: stat(l * (surge ? brittle : 1), 0.2),
        margin_per_day: stat(115000 - c * (surge ? 1.07 : 1), 0.1),
      },
    });
  }
}
write("results.json", {
  generated: "fixture",
  fixture: true,
  note: "Placeholder points typed by hand for layout work. Not evaluation results.",
  protocol: { seeds: [1, 2, 3, 4, 5], days: 14, scenarios: ["normal_week", "flu_surge"] },
  rows,
  human_runs: [],
});
