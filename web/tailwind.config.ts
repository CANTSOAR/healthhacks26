import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ground: "#E9ECFB",
        accent: { DEFAULT: "#2F55F5", soft: "#E3E9FF", dark: "#1F3FD1" },
        ink: { DEFAULT: "#141A33", 2: "#4A5275", 3: "#8089A8", 4: "#B4BAD1" },
        line: "rgba(20,26,51,0.08)",
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.7) inset, 0 12px 32px -12px rgba(47,65,140,0.22), 0 2px 6px rgba(47,65,140,0.06)",
        pill: "0 4px 14px -4px rgba(47,65,140,0.25)",
      },
      borderRadius: { xl2: "20px" },
    },
  },
  plugins: [],
};
export default config;
