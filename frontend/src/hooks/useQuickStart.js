import { useCallback, useEffect, useRef, useState } from "react";
import { trackEvent } from "../analytics.js";
import {
  FIRST_RUN_STATE_COMPLETED,
  FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS,
  FIRST_RUN_STATE_NEW,
  readFirstRunState,
  writeFirstRunState,
} from "../app_state_storage.js";
import { runQuickStartFlow } from "../quick_start.js";

export function useQuickStart({
  meta,
  section,
  calculatorPanelOpen,
  lastSuccessfulCalcRun,
  openCalculatorPanel,
  scrollToCalculator,
  focusCalculatorHeading,
}) {
  const [firstRunState, setFirstRunState] = useState(() => readFirstRunState());
  const [pendingQuickStartMode, setPendingQuickStartMode] = useState("");
  const [quickStartRunnerVersion, setQuickStartRunnerVersion] = useState(0);
  const quickStartRunnerRef = useRef(null);
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

  const requestQuickStartRun = useCallback((mode, options = {}) => {
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
      openCalculatorPanel,
      setPendingQuickStartMode,
      scrollToCalculator,
      focusCalculator: focusCalculatorHeading,
      scheduleFrame: window.requestAnimationFrame,
    });
  }, [firstRunState, focusCalculatorHeading, openCalculatorPanel, scrollToCalculator]);

  const dismissQuickStartOnboarding = useCallback(() => {
    setFirstRunState(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
    writeFirstRunState(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
    trackEvent("ff_quickstart_dismiss", { source: "activation_strip" });
  }, []);

  const reopenQuickStartOnboarding = useCallback(() => {
    setFirstRunState(FIRST_RUN_STATE_NEW);
    writeFirstRunState(FIRST_RUN_STATE_NEW);
  }, []);

  const handleRegisterQuickStartRunner = useCallback(runner => {
    quickStartRunnerRef.current = runner;
    setQuickStartRunnerVersion(version => version + 1);
  }, []);

  useEffect(() => {
    if (!pendingQuickStartMode) return;
    if (section !== "projections" || !calculatorPanelOpen) return;
    if (typeof quickStartRunnerRef.current !== "function") return;
    quickStartRunnerRef.current(pendingQuickStartMode);
    setPendingQuickStartMode("");
  }, [calculatorPanelOpen, pendingQuickStartMode, quickStartRunnerVersion, section]);

  useEffect(() => {
    if (!showQuickStartOnboarding || quickStartStripImpressionTrackedRef.current) return;
    trackEvent("quickstart_impression", { source: "activation_strip" });
    trackEvent("ff_quickstart_impression", { source: "activation_strip" });
    quickStartStripImpressionTrackedRef.current = true;
  }, [showQuickStartOnboarding]);

  useEffect(() => {
    if (!showQuickStartReminder || quickStartReminderImpressionTrackedRef.current) return;
    trackEvent("ff_quickstart_impression", { source: "activation_reminder" });
    quickStartReminderImpressionTrackedRef.current = true;
  }, [showQuickStartReminder]);

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
