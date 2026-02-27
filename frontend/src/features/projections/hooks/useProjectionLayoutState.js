import { useCallback, useEffect, useRef, useState } from "react";
import {
  PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY,
  safeReadStorage,
  safeWriteStorage,
} from "../../../app_state_storage";

export const MOBILE_BREAKPOINT_QUERY = "(max-width: 768px)";

export function readInitialMobileLayoutMode() {
  const saved = String(safeReadStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY) || "").trim().toLowerCase();
  if (saved === "cards" || saved === "table") return saved;
  return window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches ? "cards" : "table";
}

export function resolveProjectionHorizontalAffordance(el, isMobileViewport) {
  if (!el || !isMobileViewport) {
    return {
      canScrollLeft: false,
      canScrollRight: false,
    };
  }
  const maxLeft = Math.max(0, el.scrollWidth - el.clientWidth);
  return {
    canScrollLeft: el.scrollLeft > 2,
    canScrollRight: el.scrollLeft < maxLeft - 2,
  };
}

export function useProjectionLayoutState() {
  const [isMobileViewport, setIsMobileViewport] = useState(() => (
    window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches
  ));
  const [mobileLayoutMode, setMobileLayoutMode] = useState(readInitialMobileLayoutMode);
  const projectionTableScrollRef = useRef(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateProjectionHorizontalAffordance = useCallback(() => {
    const el = projectionTableScrollRef.current;
    const next = resolveProjectionHorizontalAffordance(el, isMobileViewport);
    setCanScrollLeft(next.canScrollLeft);
    setCanScrollRight(next.canScrollRight);
  }, [isMobileViewport]);

  const handleProjectionTableScroll = useCallback(() => {
    updateProjectionHorizontalAffordance();
  }, [updateProjectionHorizontalAffordance]);

  useEffect(() => {
    const mediaQuery = window.matchMedia(MOBILE_BREAKPOINT_QUERY);
    const onViewportChange = event => {
      setIsMobileViewport(Boolean(event.matches));
    };

    setIsMobileViewport(mediaQuery.matches);
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", onViewportChange);
      return () => mediaQuery.removeEventListener("change", onViewportChange);
    }
    mediaQuery.addListener(onViewportChange);
    return () => mediaQuery.removeListener(onViewportChange);
  }, []);

  useEffect(() => {
    safeWriteStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY, mobileLayoutMode);
  }, [mobileLayoutMode]);

  return {
    isMobileViewport,
    mobileLayoutMode,
    setMobileLayoutMode,
    projectionTableScrollRef,
    canScrollLeft,
    canScrollRight,
    updateProjectionHorizontalAffordance,
    handleProjectionTableScroll,
  };
}
