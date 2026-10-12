"""Writes a static snapshot of the server's GET routes into web/public/snapshot/ for the GitHub Pages build.
Everything in it is recorded simulator output (simulated numbers); nothing is live.

    ./run_server.sh &            # the API must be running
    .venv/bin/python web/scripts/make_snapshot.py [http://localhost:8000]
"""
import json
import shutil
import sys
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
OUT = Path(__file__).resolve().parents[1] / "public" / "snapshot"
# 10 MB each uncompressed, so only the managers the demo story needs
ROLLOUT_MANAGERS = ["fixed", "rule_based", "tuned_min_cost", "tuned_min_wait", "tuned_cost_p95", "ppo_scratch_min_cost"]

c = httpx.Client(base_url=BASE, timeout=120)


def save(path, data):
    f = OUT / (path.lstrip("/") + ".json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, separators=(",", ":")))
    return f.stat().st_size


def grab(path):
    r = c.get(path)
    r.raise_for_status()
    return r.json()


shutil.rmtree(OUT, ignore_errors=True)
status = grab("/api/status")
for svc in status.get("services", {}).values():
    if isinstance(svc, dict):
        svc["live"] = False
status["snapshot"] = True
save("/api/status", status)
for p in ["/api/enums", "/api/metrics", "/api/catalog", "/api/scenarios", "/api/hospitals", "/api/managers", "/api/validation"]:
    save(p, grab(p))
results = grab("/api/results")
results["human_runs"] = []
save("/api/results", results)

catalog = grab("/api/catalog")
n_refs = 0
for et in catalog["entity_types"]:
    name = et["entity_type"]
    try:
        doc = grab(f"/api/catalog/{name}")
    except httpx.HTTPStatusError:
        continue
    save(f"/api/catalog/{name}", doc)
    for variant in (doc.get("variants") or {}) if isinstance(doc.get("variants"), dict) else []:
        try:
            save(f"/api/catalog/ref/{name}/{variant}", grab(f"/api/catalog/ref/{name}/{variant}"))
            n_refs += 1
        except httpx.HTTPStatusError:
            pass
for h in grab("/api/hospitals"):
    layout = grab(f"/api/layout/{h['id']}")
    save(f"/api/layout/{h['id']}", layout)
    try:                                           # marginal value of every resource unit (simulated), when computed
        save(f"/api/attribution/{h['id']}", grab(f"/api/attribution/{h['id']}?view=summary"))
    except httpx.HTTPStatusError:
        pass
    for ref in {r.get("catalog_ref") for r in layout["rooms"] + layout["equipment"] if r.get("catalog_ref")} | {f"hospital/{h['id']}"}:
        try:
            save(f"/api/catalog/ref/{ref}", grab(f"/api/catalog/ref/{ref}"))
            n_refs += 1
        except httpx.HTTPStatusError:
            pass

# Optimize page: the menu, and one finished search as the recorded example (the static site cannot run searches).
# The example is the newest finished job the server has; without one, the contract fixtures (a real job's output).
try:
    menu = grab("/api/optimize/menu")
    menu["running"] = None
    save("/api/optimize/menu", menu)
    example = None
    for j in grab("/api/optimize"):
        if j.get("phase") == "done":
            example = grab(f"/api/optimize/{j['job_id']}")
            break
    if not example or not example.get("result"):
        fx = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
        result = json.loads((fx / "optimize_result.fixture.json").read_text())
        example = dict(spec=dict(goals=[dict(metric=g["metric"], direction=g["direction"], rank=g["rank"]) for g in result["objective"]["goals"]],
                                 guardrails=result["objective"]["guardrails"], created=result.get("generated")),
                       status=json.loads((fx / "optimize_status.fixture.json").read_text()), result=result)
    example["job_id"] = "example"
    save("/api/optimize/example", example)
except httpx.HTTPStatusError:
    pass                                           # a server without the optimiser: the page falls back to its bundled sample

rollouts = [r for r in grab("/api/rollouts") if r["manager"]["id"] in ROLLOUT_MANAGERS]
save("/api/rollouts", rollouts)
total = 0
for r in rollouts:
    total += save(f"/api/rollouts/{r['rollout_id']}", grab(f"/api/rollouts/{r['rollout_id']}"))
print(f"snapshot: {n_refs} catalog refs, {len(rollouts)} rollouts ({total / 1e6:.0f} MB), written to {OUT}")
