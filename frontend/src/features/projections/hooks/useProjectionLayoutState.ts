import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import {
  PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY,
  safeReadStorage,
  safeWriteStorage,
} from "../../../app_state_storage";
import { trackEvent } from "../../../analytics";

export const MOBILE_BREAKPOINT_QUERY = "(max-width: 768px)";

export type MobileLayoutMode = "cards" | "table";

export function readInitialMobileLayoutMode(): MobileLayoutMode {
  const saved = String(safeReadStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY) || "").trim().toLowerCase();
  if (saved === "cards" || saved === "table") return saved;
  return window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches ? "cards" : "table";
}

export interface HorizontalAffordance {
  canScrollLeft: boolean;
  canScrollRight: boolean;
}

export function resolveProjectionHorizontalAffordance(
  el: HTMLElement | null,
  _isMobileViewport: boolean,
): HorizontalAffordance {
  if (!el) {
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

export interface ProjectionLayoutState {
  isMobileViewport: boolean;
  mobileLayoutMode: MobileLayoutMode;
  setMobileLayoutMode: (mode: MobileLayoutMode) => void;
  projectionTableScrollRef: RefObject<HTMLElement | null>;
  canScrollLeft: boolean;
  canScrollRight: boolean;
  updateProjectionHorizontalAffordance: () => void;
  handleProjectionTableScroll: () => void;
}

export function useProjectionLayoutState(): ProjectionLayoutState {
  const [isMobileViewport, setIsMobileViewport] = useState<boolean>(() => (
    window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches
  ));
  const [mobileLayoutMode, setMobileLayoutMode] = useState<MobileLayoutMode>(readInitialMobileLayoutMode);
  const projectionTableScrollRef = useRef<HTMLElement | null>(null);
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
    const onViewportChange = (event: MediaQueryListEvent) => {
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

  const isInitialMountRef = useRef(true);
  useEffect(() => {
    safeWriteStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY, mobileLayoutMode);
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      return;
    }
    trackEvent("ff_projection_view_toggle", { mode: mobileLayoutMode });
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
