/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        panel: "var(--bg-panel)",
        rail: "var(--bg-rail)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        "ink-faint": "var(--ink-faint)",
        line: "var(--line)",
        "line-soft": "var(--line-soft)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        "accent-ink": "var(--accent-ink)",
        ok: "var(--ok)",
        "ok-bg": "var(--ok-bg)",
        err: "var(--err)",
        "err-bg": "var(--err-bg)",
        warn: "var(--warn)",
        "warn-bg": "var(--warn-bg)",
        "rail-ink": "var(--rail-ink)",
        "rail-ink-dim": "var(--rail-ink-dim)",
        "rail-line": "var(--rail-line)",
        code: "var(--code-bg)",
      },
      fontFamily: {
        mono: ["ui-monospace", "JetBrains Mono", "Cascadia Code", "SF Mono", "Menlo", "Consolas", "monospace"],
        sans: ["Inter", "-apple-system", "Segoe UI", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "var(--shadow)",
      },
      borderRadius: {
        xl2: "14px",
      },
    },
  },
  plugins: [],
};
