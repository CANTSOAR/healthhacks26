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
      <body>{children}</body>
    </html>
  );
}
