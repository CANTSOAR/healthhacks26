import type { Metadata, Viewport } from "next";
import "@fontsource-variable/inter"; // bundled locally: no network font at run time
import "./globals.css";

export const metadata: Metadata = {
  title: "HospitalGym",
  description: "A hospital you run like a strategy game. A model built from public information; all flows are simulated.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#E9ECFB" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {process.env.NEXT_PUBLIC_STATIC_SNAPSHOT === "1" ? (
          <div
            style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 100, background: "#141a33", color: "#fff", fontSize: 12, lineHeight: 1.4, padding: "6px 12px", textAlign: "center" }}
          >
            Recorded snapshot. This page has no live simulator: Watch, Compare, Trade-off and the inspector replay recorded simulated runs.
            Play, Encounter, Studio and Journey need the server (see the repository README). All numbers are simulated; not affiliated with the hospital.
          </div>
        ) : null}
        {children}
      </body>
    </html>
  );
}
