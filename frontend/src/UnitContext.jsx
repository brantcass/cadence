// Global unit system (metric | imperial) for the whole UI.
//
// One source of truth for "which units is the user viewing in", so the header
// toggle, the dashboard, and the chat panel all read/flip the same value.
// The choice persists across reloads via localStorage. We store the CANONICAL
// metric data everywhere and only convert at the display edge (see units.js) —
// this context just tracks WHICH edge we're rendering.

import { createContext, useContext, useEffect, useState } from "react";
import { METRIC, IMPERIAL } from "./units.js";

const STORAGE_KEY = "units";

// The context object itself. The default (null) is only used if a component
// calls useUnits() while NOT wrapped in a <UnitProvider> — we turn that into a
// clear error below instead of failing silently.
const UnitContext = createContext(null);

export function UnitProvider({ children }) {
  // Lazy initializer: passing a FUNCTION to useState makes React call it only
  // once, on the first render, instead of touching localStorage on every render.
  const [system, setSystem] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    // Only trust a value we recognize; anything else falls back to metric.
    return saved === IMPERIAL ? IMPERIAL : METRIC;
  });

  // Persist the choice whenever it changes, so a reload restores it.
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, system);
  }, [system]);

  // Flip between the two systems. Using the updater form (prev => ...) means we
  // never read a stale `system` value.
  const toggle = () => {
    setSystem((prev) => (prev === METRIC ? IMPERIAL : METRIC));
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
