import { useCallback, useEffect, useRef, useState } from "react";
import { trackEvent } from "../analytics";
import {
  FIRST_RUN_STATE_COMPLETED,
  FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS,
  FIRST_RUN_STATE_NEW,
  readFirstRunState,
  writeFirstRunState,
} from "../app_state_storage";
import type { QuickStartMode } from "../quick_start";
import { runQuickStartFlow, trackQuickStartImpression } from "../quick_start";

type QuickStartRunner = (mode: QuickStartMode) => void;

export interface UseQuickStartInput {
  meta: Record<string, unknown> | null;
  section: string;
  dataVersion: string;
  calculatorPanelOpen: boolean;
  lastSuccessfulCalcRun: unknown;
  openCalculatorPanel: (source: string) => void;
  scrollToCalculator: () => void;
  focusCalculatorHeading: () => void;
}

export interface UseQuickStartReturn {
  firstRunState: string;
  showQuickStartOnboarding: boolean;
  showQuickStartReminder: boolean;
  requestQuickStartRun: (mode: unknown, options?: { source?: string }) => void;
  dismissQuickStartOnboarding: () => void;
  reopenQuickStartOnboarding: () => void;
  handleRegisterQuickStartRunner: (runner: QuickStartRunner) => void;
}

export function useQuickStart({
  meta,
  section,
  dataVersion,
  calculatorPanelOpen,
  lastSuccessfulCalcRun,
  openCalculatorPanel,
  scrollToCalculator,
  focusCalculatorHeading,
}: UseQuickStartInput): UseQuickStartReturn {
  const [firstRunState, setFirstRunState] = useState(() => readFirstRunState());
  const [pendingQuickStartMode, setPendingQuickStartMode] = useState("");
  const [quickStartRunnerVersion, setQuickStartRunnerVersion] = useState(0);
  const quickStartRunnerRef = useRef<QuickStartRunner | null>(null);
  const quickStartStripImpressionTrackedRef = useRef(false);
  const quickStartReminderImpressionTrackedRef = useRef(false);

  const sectionNeedsMeta = section === "projections";
  const hasSuccessfulRun = Boolean(lastSuccessfulCalcRun) || firstRunState === FIRST_RUN_STATE_COMPLETED;
  const showQuickStartOnboarding = (
    sectionNeedsMeta &&
    Boolean(meta) &&
    !hasSuccessfulRun &&
    firstRunState !== FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS
  );
  const showQuickStartReminder = (
    sectionNeedsMeta &&
    Boolean(meta) &&
    !hasSuccessfulRun &&
    firstRunState === FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS
  );

  const requestQuickStartRun = useCallback((mode: unknown, options: { source?: string } = {}) => {
    const source = String(options.source || "").trim() || (
      firstRunState === FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS ? "activation_reminder" : "activation_strip"
    );
    if (firstRunState !== FIRST_RUN_STATE_COMPLETED) {
      setFirstRunState(FIRST_RUN_STATE_NEW);
      writeFirstRunState(FIRST_RUN_STATE_NEW);
    }
    runQuickStartFlow({
      mode,
      source,
      isFirstRun: !hasSuccessfulRun,
      section,
      dataVersion,
      openCalculatorPanel,
      setPendingQuickStartMode,
      scrollToCalculator,
      focusCalculator: focusCalculatorHeading,
      scheduleFrame: window.requestAnimationFrame,
    });
  }, [
    dataVersion,
    firstRunState,
    focusCalculatorHeading,
    hasSuccessfulRun,
    openCalculatorPanel,
    scrollToCalculator,
    section,
  ]);

  const dismissQuickStartOnboarding = useCallback(() => {
    setFirstRunState(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
    writeFirstRunState(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
    trackEvent("ff_quickstart_dismiss", { source: "activation_strip" });
  }, []);

  const reopenQuickStartOnboarding = useCallback(() => {
    setFirstRunState(FIRST_RUN_STATE_NEW);
    writeFirstRunState(FIRST_RUN_STATE_NEW);
    trackEvent("ff_quickstart_reopen", { source: "activation_reminder" });
  }, []);

  const handleRegisterQuickStartRunner = useCallback((runner: QuickStartRunner) => {
    quickStartRunnerRef.current = runner;
    setQuickStartRunnerVersion(version => version + 1);
  }, []);

  useEffect(() => {
    if (!pendingQuickStartMode) return;
    if (section !== "projections" || !calculatorPanelOpen) return;
    if (typeof quickStartRunnerRef.current !== "function") return;
    quickStartRunnerRef.current(pendingQuickStartMode as QuickStartMode);
    setPendingQuickStartMode("");
  }, [calculatorPanelOpen, pendingQuickStartMode, quickStartRunnerVersion, section]);

  useEffect(() => {
    if (!showQuickStartOnboarding || quickStartStripImpressionTrackedRef.current) return;
    trackQuickStartImpression({
      source: "activation_strip",
      isFirstRun: !hasSuccessfulRun,
      section,
      dataVersion,
    });
    quickStartStripImpressionTrackedRef.current = true;
  }, [dataVersion, hasSuccessfulRun, section, showQuickStartOnboarding]);

  useEffect(() => {
    if (!showQuickStartReminder || quickStartReminderImpressionTrackedRef.current) return;
    trackQuickStartImpression({
      source: "activation_reminder",
      isFirstRun: !hasSuccessfulRun,
      section,
      dataVersion,
    });
    quickStartReminderImpressionTrackedRef.current = true;
  }, [dataVersion, hasSuccessfulRun, section, showQuickStartReminder]);

  useEffect(() => {
    if (!lastSuccessfulCalcRun) return;
    if (firstRunState === FIRST_RUN_STATE_COMPLETED) return;
    setFirstRunState(FIRST_RUN_STATE_COMPLETED);
    writeFirstRunState(FIRST_RUN_STATE_COMPLETED);
  }, [firstRunState, lastSuccessfulCalcRun]);

  return {
    firstRunState,
    showQuickStartOnboarding,
    showQuickStartReminder,
    requestQuickStartRun,
    dismissQuickStartOnboarding,
    reopenQuickStartOnboarding,
    handleRegisterQuickStartRunner,
  };
}
