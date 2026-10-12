"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { dirWord, EMPTY_PICKS, epLabel, exampleJob, goalsOf, lowerFirst, METRIC_PARTS, signedPct, splitLabel, OptHttpError, optApi, picksFrom, store, type Headline, type JobListItem, type OptJob, type OptMenu, type OptSource, type Picks } from "@/lib/optimize";
import { useUI } from "@/lib/ui";
import { GoalPicker } from "../optimize/GoalPicker";
import { PlanResult, RunsList } from "../optimize/PlanResult";
import { SearchProgress } from "../optimize/SearchProgress";

type View = "pick" | "run" | "result";
const running = (j: OptJob | null) => !!j && j.status.phase !== "done" && j.status.phase !== "failed";

function Steps({ view, canRun, canResult, go }: { view: View; canRun: boolean; canResult: boolean; go: (v: View) => void }) {
  const steps: [View, string, boolean][] = [
    ["pick", "What do you want?", true],
    ["run", "Searching", canRun],
    ["result", "Result", canResult],
  ];
  const at = steps.findIndex((s) => s[0] === view);
  return (
    <ol className="flex min-w-0 items-center gap-1" aria-label="Steps" data-testid="opt-steps">
      {steps.map(([id, label, enabled], i) => (
        <li key={id} className="flex min-w-0 items-center gap-1">
          {i > 0 && <span className="mx-0.5 h-px w-4 shrink-0 bg-[#141a33]/[0.16] min-[700px]:w-8" aria-hidden />}
          <button
            type="button"
            disabled={!enabled || id === view}
            aria-current={id === view ? "step" : undefined}
            onClick={() => go(id)}
            data-step={id}
            className={`flex h-9 min-w-0 items-center gap-2 rounded-full pl-1.5 pr-3 text-[12.5px] font-semibold transition-colors ${id === view ? "bg-white text-accent-dark shadow-[0_1px_3px_rgba(47,65,140,0.18)]" : enabled ? "text-ink-2 hover:bg-white/70" : "text-ink-4"}`}
          >
            <span className={`tnum flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11.5px] font-bold ${id === view ? "bg-accent text-white" : i < at ? "bg-accent-soft text-accent-dark" : "bg-[#141a33]/[0.07] text-ink-3"}`}>{i + 1}</span>
            <span className={`truncate ${id === view ? "" : "max-[560px]:hidden"}`}>{label}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

/** Shown when searches cannot be run here: a real search recorded earlier, in view without hunting for it. */
function ExampleCard({ job, onOpen }: { job: OptJob; onOpen: () => void }) {
  const r = job.result;
  if (!r) return null;
  const goals = r.objective.goals.slice().sort((a, b) => a.rank - b.rank);
  const sc = r.scenarios.normal_week ?? Object.values(r.scenarios)[0];
  const rows = goals.flatMap((g) => Object.keys(METRIC_PARTS[g.metric] ?? {}).slice(0, 1)).filter((k, i, a) => a.indexOf(k) === i && sc?.metrics[k]?.pct != null);
  return (
    <section className="glass-solid flex flex-wrap items-center gap-x-6 gap-y-3 p-5" data-testid="opt-example-card">
      <div className="min-w-0 flex-1 basis-[320px]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow">Recorded example</span>
          <span className="sim-tag">simulated</span>
        </div>
        <h2 className="mt-1 text-[16px] font-semibold tracking-[-0.01em] text-ink">{goals.map((g, i) => `${i ? dirWord(g.direction).toLowerCase() : dirWord(g.direction)} ${lowerFirst(splitLabel(g.label)[0])}`).join(", then ")}</h2>
        <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">A real search, run earlier and saved with the app. New searches need the server, so this one shows what a result looks like: the plan, what it moved, and what it cost elsewhere.</p>
      </div>
      <div className="tnum flex flex-wrap items-center gap-x-5 gap-y-1 text-[12.5px] text-ink-2">
        {rows.slice(0, 3).map((k) => (
          <span key={k}>
            {epLabel(k)} <b className="font-semibold text-ink">{signedPct(sc.metrics[k].pct as number)}</b>
          </span>
        ))}
      </div>
      <button type="button" className="btn-primary !h-10 !px-4 !text-[13px]" onClick={onOpen} data-testid="opt-example-open">
        Open the recorded example
      </button>
    </section>
  );
}

export function OptimizeView({ narrow, top }: { narrow: boolean; top: React.ReactNode }) {
  const online = useUI((s) => s.online);
  const hospitalId = useUI((s) => s.hospitalId);
  const toast = useUI((s) => s.toast);
  const [menu, setMenu] = useState<OptMenu | null>(null);
  const [source, setSource] = useState<OptSource | null>(null);
  const [why, setWhy] = useState<string | null>(null);
  const [picks, setPicksState] = useState<Picks>(EMPTY_PICKS);
  const [view, setView] = useState<View>("pick");
  const [job, setJob] = useState<OptJob | null>(null);
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [headline, setHeadline] = useState<Headline | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lost, setLost] = useState(false);
  const [sample, setSample] = useState<OptJob | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const restored = useRef(false);

  const setPicks = useCallback((p: Picks) => {
    setPicksState(p);
    setError(null);
    store.savePicks(p);
  }, []);
  const go = useCallback((v: View) => {
    setView(v);
    scroller.current?.scrollTo({ top: 0 });
  }, []);
  const refreshJobs = useCallback(() => {
    optApi.jobs().then(setJobs, () => undefined);
  }, []);

  /** Show a job: the progress page while it runs, the result once it is done. */
  const show = useCallback(
    (j: OptJob) => {
      setJob(j);
      setLost(false);
      go(j.status.phase === "done" && j.result ? "result" : "run");
    },
    [go],
  );
  const open = useCallback(
    async (id: string, quiet = false) => {
      try {
        const j = await optApi.job(id);
        store.saveJob(id);
        show(j);
      } catch (e) {
        if (e instanceof OptHttpError && e.status === 404) store.saveJob(null);
        if (!quiet) toast(e instanceof OptHttpError && e.status === 404 ? "The server no longer has that search." : "Could not load that search.", "warn");
      }
    },
    [show, toast],
  );

  // the menu, the saved selection and (after a reload during a search) the job that was running
  useEffect(() => {
    let dead = false;
    if (!restored.current) {
      restored.current = true;
      const saved = store.picks();
      if (saved) setPicksState(saved);
    }
    void optApi.menu().then((m) => {
      if (dead) return;
      setMenu(m.menu);
      setSource(m.source);
      setWhy(m.why);
      // keep only choices the menu still offers
      setPicksState((p) => {
        const ok = new Set(m.menu.metrics.map((x) => x.id));
        const order = p.order.filter((id) => ok.has(id) && p.dir[id]);
        return order.length === p.order.length ? p : { ...p, order, dir: Object.fromEntries(order.map((id) => [id, p.dir[id]])) };
      });
      if (m.source !== "live") {
        // no server to search with: have the recorded example ready on the first screen
        void exampleJob().then((j) => !dead && setSample(j), () => undefined);
        return;
      }
      setSample(null);
      refreshJobs();
      void optApi.headline(hospitalId).then((h) => !dead && setHeadline(h));
      // a search this browser started is picked up again; someone else's is offered on the first step, not jumped to
      const id = store.job();
      if (id) void open(id, true);
    });
    return () => {
      dead = true;
    };
    // `online` flips when the API comes back: ask again then
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online === false, hospitalId]);

  // poll a running job every two seconds
  const jobId = job?.job_id ?? null;
  const isRunning = running(job) && source === "live";
  useEffect(() => {
    if (!jobId || !isRunning) return;
    let dead = false;
    const t = setInterval(() => {
      optApi.job(jobId).then(
        (j) => {
          if (dead) return;
          setLost(false);
          setJob(j);
          if (j.status.phase === "done" && j.result) {
            setView((v) => (v === "run" ? "result" : v));
            scroller.current?.scrollTo({ top: 0 });
            refreshJobs();
          }
        },
        (e) => {
          if (dead) return;
          if (e instanceof OptHttpError && e.status === 404) {
            store.saveJob(null);
            setJob(null);
            setView("pick");
            toast("The server no longer has that search. It may have been restarted.", "warn");
          } else setLost(true);
        },
      );
    }, 2000);
    return () => {
      dead = true;
      clearInterval(t);
    };
  }, [jobId, isRunning, refreshJobs, toast]);

  const run = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await optApi.start(goalsOf(picks), picks.guardrails);
      await open(r.job_id);
      refreshJobs();
    } catch (e) {
      if (e instanceof OptHttpError && e.status === 409) {
        // one search at a time: join the one that is running
        const id = (e.detail as { job_id?: string } | null)?.job_id;
        if (id) {
          toast("A search is already running. Showing that one; yours can start when it finishes.", "info");
          await open(id);
        } else setError("A search is already running. Try again in a few minutes.");
      } else if (e instanceof OptHttpError && e.status === 422) setError(typeof e.detail === "string" ? e.detail.charAt(0).toUpperCase() + e.detail.slice(1) + "." : "Choose at least one measure first.");
      else setError("Could not reach the server to start the search.");
    } finally {
      setBusy(false);
    }
  }, [picks, open, refreshJobs, toast]);

  const openExample = useCallback(() => {
    exampleJob().then(show, () => toast("The recorded example is missing from this copy of the app.", "warn"));
  }, [show, toast]);

  const again = useCallback(() => {
    // keep the selections; if the picker is empty (a reopened earlier search), fill it from that search
    if (!picks.order.length && job) setPicks(picksFrom(job.spec.goals, job.spec.guardrails));
    if (!running(job)) store.saveJob(null);
    go("pick");
  }, [picks, job, setPicks, go]);

  const labels = useMemo(() => Object.fromEntries((menu?.metrics ?? []).map((m) => [m.id, m.label])), [menu]);
  const example = job?.job_id === "example";
  const attachId = menu?.running && menu.running !== job?.job_id ? menu.running : running(job) ? job!.job_id : null;

  return (
    <div className="fixed inset-0 flex flex-col gap-3 p-2 min-[901px]:p-3" data-testid="optimize">
      {top}
      <div ref={scroller} className="scroll-thin min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable]">
        <div className="mx-auto flex w-full max-w-[1240px] flex-col gap-4 pb-10">
          <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 px-1 pt-2">
            <div className="min-w-0 max-w-[720px]">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-ink">Find a better plan</h1>
                <span className="sim-tag">simulated</span>
                {source === "fixture" && (
                  <span className="sim-tag" style={{ background: "#FDEFD8", color: "#8A5A00" }} title="Bundled sample of a real search, not a search run just now">
                    recorded sample
                  </span>
                )}
              </div>
              {view === "pick" && <p className="mt-1 text-[13.5px] leading-relaxed text-ink-2">
                Tell the twin what to aim for. It searches staffing and capacity plans and shows the best one it found next to current practice. <span className="font-semibold text-ink">It handles the scheduling and capacity scaffolding so clinicians can focus on patients.</span>
              </p>}
            </div>
            <div className="glass flex max-w-full items-center !rounded-full p-1">
              <Steps view={view} canRun={!!job && !example && (running(job) || job.status.phase === "failed")} canResult={!!job?.result} go={go} />
            </div>
          </header>

          {!menu ? (
            <div className="glass-solid flex h-[420px] items-center justify-center text-[13px] text-ink-3">Loading…</div>
          ) : view === "run" && job ? (
            <SearchProgress job={job} lost={lost} onBack={() => go("pick")} onRetry={() => void run()} />
          ) : view === "result" && job?.result ? (
            <>
              <PlanResult key={job.job_id} job={job} result={job.result} example={example} onAgain={again} />
              <RunsList jobs={jobs} current={job.job_id} labels={labels} onOpen={(id) => void open(id)} />
            </>
          ) : (
            <>
              {source !== "live" && sample && <ExampleCard job={sample} onOpen={() => show(sample)} />}
              <GoalPicker menu={menu} picks={picks} setPicks={setPicks} canRun={source === "live"} why={why} busy={busy} error={error} onRun={() => void run()} onExample={source !== "live" ? openExample : null} onAttach={attachId ? () => void open(attachId) : null} headline={headline} narrow={narrow} />
              <RunsList jobs={jobs} current={null} labels={labels} onOpen={(id) => void open(id)} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
