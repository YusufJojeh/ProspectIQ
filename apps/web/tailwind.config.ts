import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "var(--border)",
        input: "var(--surface-soft)",
        ring: "rgba(20,184,166,0.28)",
        background: "var(--bg)",
        foreground: "var(--text)",
        primary: {
          DEFAULT: "var(--accent)",
          foreground: "#05211d",
        },
        secondary: {
          DEFAULT: "var(--surface-soft)",
          foreground: "var(--text)",
        },
        destructive: {
          DEFAULT: "var(--danger)",
          foreground: "#fff7f7",
        },
        muted: {
          DEFAULT: "var(--surface-soft)",
          foreground: "var(--muted)",
        },
        accent: {
          DEFAULT: "var(--accent-soft)",
          foreground: "var(--accent-ink)",
        },
        popover: {
          DEFAULT: "var(--panel-strong)",
          foreground: "var(--text)",
        },
        card: {
          DEFAULT: "var(--panel)",
          foreground: "var(--text)",
        },
        sidebar: {
          DEFAULT: "var(--panel-strong)",
          foreground: "var(--text)",
          primary: "var(--accent)",
          "primary-foreground": "#05211d",
          accent: "var(--surface-soft)",
          "accent-foreground": "var(--text)",
          border: "var(--border)",
          ring: "rgba(20,184,166,0.28)",
        },
        panel: "var(--panel)",
        surface: "var(--surface-soft)",
        "surface-raised": "var(--surface-raised)",
        "surface-contrast": "var(--surface-contrast)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
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
