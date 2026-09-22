// Global unit system (metric | imperial) for the whole UI.
//
// One source of truth for "which units is the user viewing in", so the header
// toggle, the dashboard, and the chat panel all read/flip the same value.
// The choice persists across reloads via localStorage. We store the CANONICAL
// metric data everywhere and only convert at the display edge (see units.js) —
// this context just tracks WHICH edge we're rendering.

import { createContext, useContext, useState } from "react";
import { METRIC, IMPERIAL } from "./units.js";

// v2 key: the old "units" key was auto-written on first load, which would pin
// early visitors to whatever the previous default was. Bumping the key lets the
// current default (imperial) apply until the user explicitly chooses.
const STORAGE_KEY = "cadence_units_v2";

// The context object itself. The default (null) is only used if a component
// calls useUnits() while NOT wrapped in a <UnitProvider> — we turn that into a
// clear error below instead of failing silently.
const UnitContext = createContext(null);

export function UnitProvider({ children }) {
  // Lazy initializer: passing a FUNCTION to useState makes React call it only
  // once, on the first render, instead of touching localStorage on every render.
  const [system, setSystem] = useState(() => {
    // Default to imperial (miles/pounds) — the athlete thinks in miles. Only a
    // previously-saved explicit "metric" choice overrides that default.
    let saved = null;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch { /* private mode */ }
    return saved === METRIC ? METRIC : IMPERIAL;
  });

  // Persist ONLY on an explicit toggle (not on mount), so the default applies to
  // everyone who hasn't deliberately chosen the other system.
  const toggle = () => {
    setSystem((prev) => {
      const next = prev === METRIC ? IMPERIAL : METRIC;
      try { localStorage.setItem(STORAGE_KEY, next); } catch { /* private mode */ }
      return next;
    });
  };

  return (
    <UnitContext.Provider value={{ system, toggle }}>
      {children}
    </UnitContext.Provider>
  );
}

// The hook every component uses: `const { system, toggle } = useUnits();`
export function useUnits() {
  const ctx = useContext(UnitContext);
  if (ctx === null) {
    throw new Error("useUnits must be used inside a <UnitProvider>");
  }
  return ctx;
}
