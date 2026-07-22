/**
 * Design tokens for GradeSense — see the design plan in the Phase 11 README
 * section for the reasoning behind these choices (a "graded paper" palette
 * tied to the subject, not a generic AI-default terracotta/cream or
 * dark-mode-acid-green look).
 */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF8F3",   // warm off-white background — the "page" a submission gets marked on
        ink: "#22282E",     // primary text — soft near-black, not pure black
        pen: {              // primary brand color — deep teal-ink, evokes a fountain pen / chalkboard
          DEFAULT: "#2B4C52",
          light: "#3E6B72",
          dark: "#1B3439",
        },
        gold: {              // the grading-stamp accent — used sparingly, for scores and highlights only
          DEFAULT: "#C89B3C",
          light: "#E0BE6E",
        },
        sage: "#3F7D5C",     // pass / success
        brick: "#A8443A",    // fail / error / flagged for review
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["\"IBM Plex Mono\"", "\"Fira Code\"", "monospace"],
      },
      borderRadius: {
        stamp: "9999px",
      },
    },
  },
  plugins: [],
};
