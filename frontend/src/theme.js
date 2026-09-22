// Cadence visual theme — one place for every color the UI and charts use.
//
// Brand is forest-green + beige (a calm, outdoorsy endurance feel). Chart colors
// were chosen by job and validated for colorblind-safety and contrast with the
// dataviz palette validator (see the project notes): single-hue sequential ramp
// for the ordinal effort mix, distinct categorical hues for the four training
// phases, and a reserved status palette for the load readout (always paired with
// a text label, never color alone). Light theme only — a beige surface is
// inherently a light design.

export const colors = {
  // brand / surfaces
  forest: "#2f5d50",
  forestDark: "#1e3d34",
  beige: "#f5f1e7",
  surface: "#ffffff",
  card: "#fbfaf5",
  ink: "#1f2a26",
  muted: "#5f6b66",
  border: "#e4ddcd",

  // single-series chart marks (each chart is one series, so no CVD concern)
  mileage: "#2f5d50",
  hrv: "#2f5d50",
  sleep: "#6f9c8a",
  hr: "#c05a2a",

  // effort mix — ordinal ramp, Easy -> Moderate -> Hard (light -> dark)
  effort: ["#86b6ef", "#3987e5", "#184f95"],

  // training phases — validated categorical set
  phase: { Base: "#159b70", Build: "#2f6fb0", Peak: "#c05a2a", Taper: "#8a5fb0" },

  // acute:chronic load status — reserved status colors (shown with the status word)
  status: {
    optimal: "#2f7d5b",
    elevated: "#c2621c",
    "high risk": "#c0392b",
    detraining: "#8a6d1f",
    unknown: "#5f6b66",
  },
};

// Session-kind accents for the plan view (a colored left border per day).
export const kindColor = {
  run: colors.forest,
  strength: "#8a5fb0",
  cross: "#c05a2a",
  race: "#c0392b",
  rest: colors.border,
};

export const phaseColor = (phase) => colors.phase[phase] || colors.muted;
export const statusColor = (status) => colors.status[status] || colors.status.unknown;
