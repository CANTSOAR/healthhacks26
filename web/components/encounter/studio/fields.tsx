"use client";
// Form building blocks for the Patient Studio editor, and the plumbing that puts validation findings next to fields.
import { createContext, useContext, useState, type ReactNode } from "react";
import type { ValidationReport } from "@/lib/encounter/types";
import { inputCls } from "../ui";

export type Level = "error" | "contradiction" | "warning";
export interface Issue {
  level: Level;
  path: string;
  message: string;
}

/** Flattens a validation report to one row per (finding, path). */
export function flatten(v: ValidationReport | null): Issue[] {
  if (!v) return [];
  const out: Issue[] = [];
  v.errors.forEach((e) => out.push({ level: "error", path: e.path || "/", message: e.message }));
  v.consistency.forEach((c) => (c.paths?.length ? c.paths : ["/"]).forEach((p) => out.push({ level: c.level === "contradiction" || c.level === "error" ? "contradiction" : "warning", path: p, message: c.message })));
  v.warnings.forEach((w) => out.push({ level: "warning", path: w.path || "/", message: w.message }));
  return out;
}

export const IssueCtx = createContext<Issue[]>([]);
export const useIssues = () => useContext(IssueCtx);
const under = (p: string, prefix: string) => p === prefix || p.startsWith(prefix + "/");
export const issuesUnder = (all: Issue[], prefix: string) => all.filter((i) => under(i.path, prefix));
export const worst = (list: Issue[]): Level | null => (list.some((i) => i.level !== "warning") ? "error" : list.length ? "warning" : null);

const TONE: Record<Level, { bg: string; fg: string; border: string; word: string }> = {
  error: { bg: "#FDE7E7", fg: "#8E1B23", border: "#F0A8AD", word: "Error" },
  contradiction: { bg: "#FDE7E7", fg: "#8E1B23", border: "#F0A8AD", word: "Contradiction" },
  warning: { bg: "#FFF4DC", fg: "#7A4A00", border: "#EBCB85", word: "Warning" },
};

export function IssueList({ items }: { items: Issue[] }) {
  if (!items.length) return null;
  const seen = new Set<string>();
  const uniq = items.filter((i) => {
    const k = i.level + i.message;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return (
    <ul className="mt-1 space-y-1">
      {uniq.map((i, k) => (
        <li key={k} className="rounded-md border px-2 py-1 text-[11.5px] font-medium leading-snug" style={{ background: TONE[i.level].bg, color: TONE[i.level].fg, borderColor: TONE[i.level].border }} data-testid="issue" data-level={i.level} data-path={i.path}>
          <span className="font-semibold">{TONE[i.level].word}: </span>
          {i.message}
        </li>
      ))}
    </ul>
  );
}

/** Findings whose path is this field (or below it). `skip` lists sub-paths that have their own field. */
export function Issues({ path, skip = [] }: { path: string; skip?: string[] }) {
  const all = useIssues();
  const mine = issuesUnder(all, path).filter((i) => !skip.some((s) => under(i.path, `${path}/${s}`)));
  return <IssueList items={mine} />;
}

export function IssueDot({ path }: { path: string }) {
  const w = worst(issuesUnder(useIssues(), path));
  if (!w) return null;
  return <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: w === "error" ? "#D8434C" : "#E0A100" }} title={w === "error" ? "Has errors" : "Has warnings"} data-testid="issue-dot" data-level={w} />;
}

function ring(path: string | undefined, all: Issue[]): string {
  if (!path) return "";
  const w = worst(issuesUnder(all, path));
  return w === "error" ? "!border-[#D8434C]" : w === "warning" ? "!border-[#E0A100]" : "";
}

export function F({ label, hint, path, children, className = "", skip }: { label: string; hint?: string; path?: string; children: ReactNode; className?: string; skip?: string[] }) {
  return (
    <div className={className}>
      <label className="block">
        <span className="mb-1 block text-[11px] font-semibold text-ink-2">{label}</span>
        {children}
      </label>
      {hint && <span className="mt-1 block text-[11px] leading-snug text-ink-3">{hint}</span>}
      {path && <Issues path={path} skip={skip} />}
    </div>
  );
}

interface Common {
  path?: string;
  disabled?: boolean;
  placeholder?: string;
  testid?: string;
}

export function Text({ value, onChange, path, disabled, placeholder, testid, list }: Common & { value: string | undefined; onChange: (v: string) => void; list?: string }) {
  const all = useIssues();
  return <input className={`${inputCls} ${ring(path, all)}`} value={value ?? ""} onChange={(e) => onChange(e.target.value)} disabled={disabled} placeholder={placeholder} data-testid={testid} list={list} />;
}
export function Num({ value, onChange, path, disabled, placeholder, testid, min, max, step }: Common & { value: number | undefined; onChange: (v: number | undefined) => void; min?: number; max?: number; step?: number }) {
  const all = useIssues();
  return <input type="number" className={`${inputCls} tnum ${ring(path, all)}`} value={value ?? ""} min={min} max={max} step={step} onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} disabled={disabled} placeholder={placeholder} data-testid={testid} />;
}
export function Area({ value, onChange, path, disabled, placeholder, testid, rows = 2 }: Common & { value: string | undefined; onChange: (v: string) => void; rows?: number }) {
  const all = useIssues();
  return <textarea rows={rows} className={`${inputCls} resize-y leading-snug ${ring(path, all)}`} value={value ?? ""} onChange={(e) => onChange(e.target.value)} disabled={disabled} placeholder={placeholder} data-testid={testid} />;
}
export function Select({ value, onChange, options, path, disabled, testid }: Common & { value: string | undefined; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  const all = useIssues();
  const has = options.some((o) => o.value === (value ?? ""));
  return (
    <select className={`${inputCls} cursor-pointer ${ring(path, all)}`} value={value ?? ""} onChange={(e) => onChange(e.target.value)} disabled={disabled} data-testid={testid}>
      {!has && <option value={value ?? ""}>{value ? `${value} (not in the list)` : "—"}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
export function Check({ value, onChange, label, disabled, testid, hint }: { value: boolean | undefined; onChange: (v: boolean) => void; label: string; disabled?: boolean; testid?: string; hint?: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-[12.5px] font-medium text-ink" title={hint}>
      <input type="checkbox" className="h-4 w-4 accent-[#2F55F5]" checked={!!value} onChange={(e) => onChange(e.target.checked)} disabled={disabled} data-testid={testid} />
      {label}
    </label>
  );
}

/** Comma-separated strings edited as free text (topics, differential, expected orders). */
export function Csv({ value, onChange, path, disabled, placeholder, testid }: Common & { value: string[] | undefined; onChange: (v: string[]) => void }) {
  const [raw, setRaw] = useState<string | null>(null);
  const all = useIssues();
  const shown = raw ?? (value ?? []).join(", ");
  return (
    <input
      className={`${inputCls} ${ring(path, all)}`}
      value={shown}
      disabled={disabled}
      placeholder={placeholder}
      data-testid={testid}
      onChange={(e) => {
        setRaw(e.target.value);
        onChange(
          e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        );
      }}
      onBlur={() => setRaw(null)}
    />
  );
}
/** One string per line (teaching points). */
export function Lines({ value, onChange, disabled, placeholder, rows = 3 }: Common & { value: string[] | undefined; onChange: (v: string[]) => void; rows?: number }) {
  const [raw, setRaw] = useState<string | null>(null);
  return (
    <textarea
      rows={rows}
      className={`${inputCls} resize-y leading-snug`}
      value={raw ?? (value ?? []).join("\n")}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => {
        setRaw(e.target.value);
        onChange(
          e.target.value
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
        );
      }}
      onBlur={() => setRaw(null)}
    />
  );
}

/** A set of ids picked from a known list (linked facts, evidence to confront with). */
export function IdPicker({ values, options, onChange, placeholder, disabled, testid, allowFree = false }: { values: string[] | undefined; options: { id: string; label: string }[]; onChange: (v: string[]) => void; placeholder: string; disabled?: boolean; testid?: string; allowFree?: boolean }) {
  const [free, setFree] = useState("");
  const vals = values ?? [];
  const label = (id: string) => options.find((o) => o.id === id)?.label;
  const rest = options.filter((o) => !vals.includes(o.id));
  return (
    <div data-testid={testid}>
      <div className="flex flex-wrap gap-1">
        {vals.map((id) => {
          const known = label(id);
          return (
            <span key={id} className="inline-flex max-w-full items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] font-medium" style={known || allowFree ? { background: "#E3E9FF", color: "#1F3FD1" } : { background: "#FDE7E7", color: "#8E1B23" }} title={known ? id : allowFree ? id : `${id} does not exist in this case`}>
              <span className="truncate">{known ?? id}</span>
              {!disabled && (
                <button type="button" aria-label={`Remove ${id}`} className="opacity-60 hover:opacity-100" onClick={() => onChange(vals.filter((x) => x !== id))}>
                  ×
                </button>
              )}
            </span>
          );
        })}
        {vals.length === 0 && <span className="text-[11.5px] text-ink-3">None linked.</span>}
      </div>
      {!disabled && (
        <div className="mt-1.5 flex gap-1.5">
          {rest.length > 0 && (
            <select
              className={`${inputCls} cursor-pointer !py-1 text-[12px]`}
              value=""
              onChange={(e) => e.target.value && onChange([...vals, e.target.value])}
              aria-label={placeholder}
            >
              <option value="">{placeholder}</option>
              {rest.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label.length > 90 ? o.label.slice(0, 88) + "…" : o.label}
                </option>
              ))}
            </select>
          )}
          {allowFree && (
            <input
              className={`${inputCls} !py-1 text-[12px]`}
              value={free}
              placeholder="or type and press Enter"
              onChange={(e) => setFree(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && free.trim()) {
                  e.preventDefault();
                  if (!vals.includes(free.trim())) onChange([...vals, free.trim()]);
                  setFree("");
                }
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}

export function Panel({ title, note, right, children, testid }: { title: string; note?: string; right?: ReactNode; children: ReactNode; testid?: string }) {
  return (
    <section className="glass p-4" data-testid={testid}>
      <div className="mb-3 flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-[14px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
          {note && <p className="mt-0.5 text-[11.5px] leading-snug text-ink-3">{note}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

export function RemoveBtn({ onClick, label = "Remove", disabled }: { onClick: () => void; label?: string; disabled?: boolean }) {
  return (
    <button type="button" className="btn !h-7 !px-2 text-[11.5px] !text-[#B4232C] hover:!bg-[#FDE7E7]" onClick={onClick} disabled={disabled}>
      {label}
    </button>
  );
}

export const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);
