import { useEffect, useMemo, useRef, useState } from "react";
import { MOBILE_BREAKPOINT_QUERY } from "../features/projections/hooks/useProjectionLayoutState";
import { resolveProjectionWindow } from "../formatting_utils";
import { useBottomSheet } from "./useBottomSheet";
import { useCalculatorOverlay } from "./useCalculatorOverlay";
import { useDefaultDynastyPlayers } from "./useDefaultDynastyPlayers";
import { useCalculatorState } from "./useCalculatorState";
import { useMetadata } from "./useMetadata";
import { useQuickStart } from "./useQuickStart";
import { useVersionPolling } from "./useVersionPolling";
import { useAccountMenu } from "./useAccountMenu";
import { useMobileNavMenu } from "./useMobileNavMenu";
import { useAccountSync } from "./useAccountSync";
import { usePremiumStatus } from "./usePremiumStatus";
import { useTheme } from "./useTheme";
import { useFantraxLeague } from "./useFantraxLeague";
import { useToastContext } from "../Toast";
import { parseBillingRedirectParam, cleanBillingParam } from "../billing_redirect";
import {
  installAnalyticsDebugBridge,
  setAnalyticsContext,
  trackEvent,
} from "../analytics";
import {
  readLastSuccessfulCalcRun,
  readPlayerWatchlist,
  readSessionFirstRunLandingTimestamp,
  writeSessionFirstRunLandingTimestamp,
  writePlayerWatchlist,
} from "../app_state_storage";

/**
 * Composes all top-level App hooks and side-effects into a single return value.
 * Keeps the App component as a pure render function.
 */
export function useAppState(apiBase: string) {
  const [section, setSection] = useState("projections");
  const { meta, metaError, metaLoading, retryMetaLoad } = useMetadata(apiBase);
  const { buildLabel, dataVersion } = useVersionPolling(apiBase);

  const calculatorState = useCalculatorState({ section, setSection, meta });
  const {
    calculatorPanelOpen,
    setCalculatorPanelOpen,
    calculatorSettings,
    lastSuccessfulCalcRun,
    presets,
    setPresets,
    calculatorPanelOpenSourceRef,
    openCalculatorPanel,
    scrollToCalculator,
    focusFirstCalculatorInput,
  } = calculatorState;

  const [watchlist, setWatchlist] = useState(() => readPlayerWatchlist());
  const calculatorOverlay = useCalculatorOverlay(dataVersion);
  const { calculatorResultRows } = calculatorOverlay;
  const defaultDynastyPlayers = useDefaultDynastyPlayers(apiBase);
  const effectiveDynastyPlayers = useMemo(
    () => (calculatorResultRows.length > 0 ? calculatorResultRows : defaultDynastyPlayers),
    [calculatorResultRows, defaultDynastyPlayers],
  );

  const auth = useAccountSync({ presets, setPresets, watchlist, setWatchlist });
  const { authUser } = auth;
  const premium = usePremiumStatus(authUser);
  const toast = useToastContext();
  const accountMenu = useAccountMenu({ section });
  const mobileNavMenu = useMobileNavMenu({ section });
  const bottomSheet = useBottomSheet();
  const { theme, toggleTheme } = useTheme();
  const fantrax = useFantraxLeague();

  const [tradeAnalyzerOpen, setTradeAnalyzerOpen] = useState(false);
  const [keeperCalculatorOpen, setKeeperCalculatorOpen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(
    () => window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches,
  );

  useEffect(() => {
    const mql = window.matchMedia(MOBILE_BREAKPOINT_QUERY);
    const handler = (e: MediaQueryListEvent): void => setIsMobileViewport(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  const landingTrackedRef = useRef(false);
  const sectionNeedsMeta = section === "projections";
  const projectionWindow = useMemo(() => resolveProjectionWindow(meta), [meta]);
  const resolvedScoringMode = String(calculatorSettings?.scoring_mode || "").trim().toLowerCase() === "points"
    ? "points"
    : calculatorSettings
      ? "roto"
      : "unknown";

  const quickStart = useQuickStart({
    meta,
    section,
    dataVersion,
    calculatorPanelOpen,
    lastSuccessfulCalcRun,
    openCalculatorPanel,
    scrollToCalculator,
    focusCalculatorHeading: focusFirstCalculatorInput,
  });

  // --- Side effects ---

  useEffect(() => {
    setAnalyticsContext({
      section,
      data_version: String(dataVersion || "").trim() || "unknown",
      is_signed_in: Boolean(authUser),
      scoring_mode: resolvedScoringMode,
    });
  }, [authUser, dataVersion, resolvedScoringMode, section]);

  useEffect(() => {
    installAnalyticsDebugBridge();
  }, []);

  useEffect(() => {
    if (landingTrackedRef.current) return;
    landingTrackedRef.current = true;
    const hasPriorRun = Boolean(readLastSuccessfulCalcRun());
    const existingLandingTs = readSessionFirstRunLandingTimestamp();
    if (!existingLandingTs) {
      writeSessionFirstRunLandingTimestamp(Date.now());
    }
    trackEvent("ff_landing_view", {
      source: "app_boot",
      is_first_run: !hasPriorRun,
      section,
    });
  }, [section]);

  useEffect(() => {
    writePlayerWatchlist(watchlist);
  }, [watchlist]);

  useEffect(() => {
    const billing = parseBillingRedirectParam(window.location.search);
    if (!billing || !toast) return;
    if (billing === "success") {
      toast.addToast("Subscription activated!", { type: "success" });
    } else {
      toast.addToast("Checkout cancelled.", { type: "info" });
    }
    cleanBillingParam();
  }, [toast]);

  return {
    section,
    setSection,
    meta,
    metaError,
    metaLoading,
    retryMetaLoad,
    buildLabel,
    dataVersion,
    calculatorState,
    calculatorOverlay,
    watchlist,
    setWatchlist,
    effectiveDynastyPlayers,
    auth,
    premium,
    accountMenu,
    mobileNavMenu,
    bottomSheet,
    theme,
    toggleTheme,
    fantrax,
    tradeAnalyzerOpen,
    setTradeAnalyzerOpen,
    keeperCalculatorOpen,
    setKeeperCalculatorOpen,
    isMobileViewport,
    sectionNeedsMeta,
    projectionWindow,
    quickStart,
    calculatorPanelOpenSourceRef,
    setCalculatorPanelOpen,
  };
}
