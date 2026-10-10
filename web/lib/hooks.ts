"use client";
import { useEffect, useRef, useState } from "react";
import type { Source } from "./api";
import type { Feed, FeedState } from "./feed";

/** Feed state for panels, refreshed at most every `ms` (snapshots can arrive 48 times a second; lists need not). */
export function useFeedState(feed: Feed, ms = 250): FeedState {
  const [state, setState] = useState(feed.getState());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastAt = useRef(0);
  useEffect(() => {
    setState(feed.getState());
    const flush = () => {
      timer.current = null;
      lastAt.current = performance.now();
      setState(feed.getState());
    };
    const unsub = feed.subscribe(() => {
      if (timer.current) return;
      const wait = Math.max(0, ms - (performance.now() - lastAt.current));
      timer.current = setTimeout(flush, wait);
    });
    return () => {
      unsub();
      if (timer.current) clearTimeout(timer.current);
      timer.current = null;
    };
  }, [feed, ms]);
  return state;
}

export function useNarrow(maxWidth = 900): boolean {
  const [narrow, setNarrow] = useState(() => (typeof window !== "undefined" ? window.innerWidth <= maxWidth : false));
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${maxWidth}px)`);
    const on = () => setNarrow(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [maxWidth]);
  return narrow;
}

export function useApi<T>(fn: () => Promise<{ data: T; source: Source }>, deps: unknown[]): { data: T | null; source: Source | null; loading: boolean; error: string | null } {
  const [st, setSt] = useState<{ data: T | null; source: Source | null; loading: boolean; error: string | null }>({ data: null, source: null, loading: true, error: null });
  useEffect(() => {
    let dead = false;
    setSt((s) => ({ ...s, loading: true, error: null }));
    fn().then(
      (r) => !dead && setSt({ data: r.data, source: r.source, loading: false, error: null }),
      (e) => !dead && setSt({ data: null, source: null, loading: false, error: String(e?.message ?? e) }),
    );
    return () => {
      dead = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return st;
}

export function useClickAway<T extends HTMLElement>(onAway: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const h = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onAway();
    };
    window.addEventListener("pointerdown", h);
    return () => window.removeEventListener("pointerdown", h);
  }, [onAway]);
  return ref;
}
