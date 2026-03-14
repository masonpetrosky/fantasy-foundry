import React, { createContext, useContext } from "react";
import type { useCalculatorOverlay } from "../hooks/useCalculatorOverlay";

export type CalculatorOverlayValue = ReturnType<typeof useCalculatorOverlay>;

export const CalculatorOverlayContext = createContext<CalculatorOverlayValue | null>(null);

export function useCalculatorOverlayContext(): CalculatorOverlayValue {
  const ctx = useContext(CalculatorOverlayContext);
  if (ctx === null) {
    throw new Error("useCalculatorOverlayContext must be used within CalculatorOverlayContext.Provider");
  }
  return ctx;
}
