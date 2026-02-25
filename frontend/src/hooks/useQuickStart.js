import { useCallback, useEffect, useRef, useState } from "react";
import { trackEvent } from "../analytics.js";
import {
  readOnboardingDismissed,
  writeOnboardingDismissed,
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
  const [onboardingDismissed, setOnboardingDismissed] = useState(() => readOnboardingDismissed());
  const [pendingQuickStartMode, setPendingQuickStartMode] = useState("");
  const [quickStartRunnerVersion, setQuickStartRunnerVersion] = useState(0);
  const quickStartRunnerRef = useRef(null);
  const quickStartImpressionTrackedRef = useRef(false);

  const sectionNeedsMeta = section === "projections";
  const showQuickStartOnboarding = sectionNeedsMeta && Boolean(meta) && !onboardingDismissed && !lastSuccessfulCalcRun;

  const requestQuickStartRun = useCallback(mode => {
    runQuickStartFlow({
      mode,
      onboardingDismissed,
      markOnboardingDismissed: () => {
        setOnboardingDismissed(true);
        writeOnboardingDismissed(true);
      },
      openCalculatorPanel,
      setPendingQuickStartMode,
      scrollToCalculator,
      focusCalculator: focusCalculatorHeading,
      scheduleFrame: window.requestAnimationFrame,
    });
  }, [focusCalculatorHeading, onboardingDismissed, openCalculatorPanel, scrollToCalculator]);

  const dismissQuickStartOnboarding = useCallback(() => {
    setOnboardingDismissed(true);
    writeOnboardingDismissed(true);
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
    if (!showQuickStartOnboarding || quickStartImpressionTrackedRef.current) return;
    trackEvent("quickstart_impression", { source: "onboarding_strip" });
    quickStartImpressionTrackedRef.current = true;
  }, [showQuickStartOnboarding]);

  return {
    showQuickStartOnboarding,
    requestQuickStartRun,
    dismissQuickStartOnboarding,
    handleRegisterQuickStartRunner,
  };
}
