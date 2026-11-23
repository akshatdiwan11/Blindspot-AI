/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#0B1020", 900: "#0B1020", 800: "#121A2B", 700: "#19243A", 600: "#22304A", 500: "#2D3D5C" },
        line: "#24314A",
        accent: { DEFAULT: "#6275FF", soft: "#6275FF1F", 2: "#8B5CF6" },
        ok: "#20C997",
        warn: "#F5B942",
        bad: "#F26B75",
        fg: { DEFAULT: "#F4F6FC", muted: "#98A4B8", faint: "#6B778C" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["'Instrument Serif'", "ui-serif", "Georgia", "serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { "fade-up": "fade-up 0.35s ease-out both" },
    },
  },
  plugins: [],
};
