# Common brief for every overnight subagent

You are one of several agents building **HospitalGym** overnight (Rutgers Health Hack 2026,
TwinVerse track). The user is asleep. Nobody answers questions: decide, note the decision in
your final report, keep going. An orchestrator integrates and commits your work.

Read first, in this order:
1. `HANDOFF.md` (the full brief; it wins over README.md) — at least "What we are building",
   "Ground rules", "Machines", the interaction contract, and the section for your workstream.
2. `contracts/README.md` and the contract files named in your task.
3. `README.md` for the product plan.

Rules (from HANDOFF.md, binding):
- Repo root: `/Users/dipalshah/Desktop/healthhacks26`. Work only inside it. Write only inside the
  directories your task names. **Never edit `contracts/`** — if you need a change, write it in
  `<your-dir>/CONTRACT_REQUESTS.md`, proceed with your proposed shape, and say so in your report.
- Several agents share this working tree at the same time. Do not touch other agents' directories,
  do not run `git add/commit/stash/checkout/reset` or any git write (the orchestrator commits),
  do not delete files you did not create.
- Never modify `docs/`, the root `*.zip`, or `research/*` files written by the teammate (add new
  files instead). Organizer material lives in `.private/` (already extracted) and is never copied
  into tracked paths: no sample-patient text, photos, rubric JSON or clinician profiles verbatim in
  tracked files. Code reads them from `.private/` at run time and must work when they are absent.
- No pushing, deploying, account creation, credential hunting, global installs, `brew`, or `sudo`.
  No spending money. Python: `.venv/bin/python` (3.12, torch 2.2.2, numpy<2 — keep those pins);
  install extra packages with `.venv/bin/python -m pip install` and append them to `requirements.txt`.
  Node 22 + pnpm 10 inside `web/` only.
- Remote machine: `ssh deepstack` (24 cores, RTX A5500 16 GB, torch 2.8 CUDA). Our directory there is
  `~/projects/hospitalgym_aryan` (uv env at `.venv`), tmux session `hospitalgym` (make your own
  window). Touch nothing else on that machine. Only use it if your task says so.
- Honesty: never claim something works unless you ran it. Label synthetic and assumed numbers.
  Cite only sources you actually fetched and read; no invented papers, sample sizes, DOIs or URLs.
  No language model ever produces or alters a simulation number.
- No credentials are set tonight: everything runs on the offline path. Online paths must still be
  implemented and tested against faked responses.
- The Mac has 4 cores and other agents are running: keep local test runs short (small batches),
  do not leave servers or watchers running when you finish, and avoid ports 3000 and 8000 unless
  your task assigns them (use the port your task names).
- Use scratch space under your own directory or the system temp dir, not the repo root.

Final report (your last message, under ~400 words): what exists and where; exactly what you ran
and the observed results (test counts, numbers); what is partial, stubbed or broken; decisions
made; contract change requests; what the next agent needs to know. Facts only.
