import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--bg)",
        foreground: "var(--text)",
        border: "var(--border)",
        panel: "var(--panel)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        surface: "var(--surface-soft)",
      },
      borderRadius: {
        xl: "1rem",
      },
      fontFamily: {
        sans: ["Manrope", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [animate],
} satisfies Config;
