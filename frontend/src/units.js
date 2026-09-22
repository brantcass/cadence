// Unit conversion + formatting for the UI.
//
// This is the frontend mirror of backend/analytics/units.py — same constants,
// same "store metric, convert only at display" rule. The React components import
// these helpers; they never do conversion arithmetic inline.
//
// Reminder: pace converts INVERSELY to distance (a mile is longer, so it takes
// more minutes per mile than per km).

const KM_PER_MILE = 1.609344;
const KG_PER_POUND = 0.45359237;

export const METRIC = "metric";
export const IMPERIAL = "imperial";

// ---- raw converters (number in, number out) ----
export const kmToMi = (km) => km / KM_PER_MILE;
export const kgToLb = (kg) => kg / KG_PER_POUND;
export const pacePerKmToPerMi = (minPerKm) => minPerKm * KM_PER_MILE;

// ---- display formatters (canonical metric value in, string out) ----
function mmss(decimalMinutes) {
  let minutes = Math.floor(decimalMinutes);
  let seconds = Math.round((decimalMinutes - minutes) * 60);
  if (seconds === 60) {
    minutes += 1;
    seconds = 0;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatDistance(km, system, digits = 1) {
  if (system === IMPERIAL) return `${kmToMi(km).toFixed(digits)} mi`;
  return `${km.toFixed(digits)} km`;
}

export function formatPace(minPerKm, system) {
  if (minPerKm == null) return "—";
  if (system === IMPERIAL) return `${mmss(pacePerKmToPerMi(minPerKm))}/mi`;
  return `${mmss(minPerKm)}/km`;
}

export function formatWeight(kg, system, digits = 1) {
  if (system === IMPERIAL) return `${kgToLb(kg).toFixed(digits)} lb`;
  return `${kg.toFixed(digits)} kg`;
}

// The label to show on a units toggle for the OPPOSITE of the current system.
export const unitLabel = (system) => (system === IMPERIAL ? "mi / lb" : "km / kg");
