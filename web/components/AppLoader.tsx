"use client";
import dynamic from "next/dynamic";

// The whole app is client-only: it is a WebGL canvas plus panels driven by a websocket / replay clock.
const App = dynamic(() => import("./App"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen w-screen items-center justify-center bg-ground text-[13px] font-medium text-ink-3">Loading the hospital…</div>
  ),
});
export default function AppLoader() {
  return <App />;
}
