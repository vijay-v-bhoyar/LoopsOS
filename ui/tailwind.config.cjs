/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg1: "var(--f2-bg-1)",
        bg2: "var(--f2-bg-2)",
        bg3: "var(--f2-bg-3)",
        fg1: "var(--f2-fg-1)",
        fg2: "var(--f2-fg-2)",
        fg3: "var(--f2-fg-3)",
        brand: "var(--f2-brand)",
        brandStrong: "var(--f2-brand-strong)",
        brandSubtle: "var(--f2-brand-subtle)",
        border1: "var(--f2-border-1)",
        border2: "var(--f2-border-2)",
        success: "var(--f2-success)",
        successBg: "var(--f2-success-bg)",
        warning: "var(--f2-warning)",
        warningBg: "var(--f2-warning-bg)",
        danger: "var(--f2-danger)",
        dangerBg: "var(--f2-danger-bg)",
        infoBg: "var(--f2-info-bg)",
        glassBg: "var(--f2-glass-bg)",
        glassBorder: "var(--f2-glass-border)"
      },
      boxShadow: {
        card: "var(--f2-shadow-card)",
        panel: "var(--f2-shadow-panel)",
        focus: "var(--f2-shadow-focus)"
      },
      borderRadius: {
        control: "var(--f2-radius-control)",
        panel: "var(--f2-radius-panel)"
      },
      fontFamily: {
        sans: "var(--f2-font-family-base)"
      }
    }
  },
  plugins: []
};
