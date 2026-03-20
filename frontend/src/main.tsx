import React, { Suspense, lazy, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./styles/typography-table.css";
import "./styles/app.css";
import { QueryClientProvider } from "@tanstack/react-query";
import { createAppQueryClient } from "./lib/queryClient";
import { initSentry } from "./sentry";
import { initGA4 } from "./ga4";

initSentry();
initGA4();
import { AppHeader } from "./components/AppHeader";
import { HeroSection } from "./components/HeroSection";
import { AppFooter } from "./components/AppFooter";
function resolveActivationDiagnosticsPanelEnabled({
  envEnabled = false,
  locationSearch = "",
}: { envEnabled?: boolean | string; locationSearch?: string } = {}): boolean {
  const resolvedEnvEnabled = envEnabled === true || String(envEnabled).trim() === "1";
  let queryEnabled: boolean;
  try {
    const params = new URLSearchParams(String(locationSearch || ""));
    const raw = String(params.get("activation_debug") || "").trim().toLowerCase();
    queryEnabled = raw === "1" || raw === "true" || raw === "yes" || raw === "on";
  } catch {
    queryEnabled = false;
  }
  return resolvedEnvEnabled || queryEnabled;
}
import { resolveApiBase } from "./api_base";
import { ProjectionsExplorer } from "./projections_explorer";
import { MobileCalculatorSheet } from "./MobileCalculatorSheet";
import { ErrorBoundary } from "./error_boundary";
import { FeatureErrorBoundary } from "./feature_error_boundary";
import { ToastProvider } from "./Toast";
import { PricingSection } from "./PricingSection";
import { CalculatorOverlayContext } from "./contexts/CalculatorOverlayContext";
import { useAppState } from "./hooks/useAppState";

const API = resolveApiBase();
const queryClient = createAppQueryClient();
const ACTIVATION_SPRINT_ENABLED = String(import.meta.env.VITE_FF_ACTIVATION_SPRINT_V1 || "1").trim() !== "0";
const ACTIVATION_DIAGNOSTICS_PANEL_ENV_ENABLED = String(
  import.meta.env.VITE_FF_ACTIVATION_DIAGNOSTICS_PANEL_V1 || "0"
).trim() === "1";
const LazyMethodologySection = lazy(() => (
  import("./methodology_section").then(module => ({ default: module.MethodologySection }))
));
const LazyDynastyCalculator = lazy(() => (
  import("./dynasty_calculator").then(module => ({ default: module.DynastyCalculator }))
));
const LazyPlayerPage = lazy(() => import("./PlayerPage").then(m => ({ default: m.PlayerPage })));
const LazyMoversPage = lazy(() => import("./MoversPage").then(m => ({ default: m.MoversPage })));
const LazyTradeAnalyzer = lazy(() => import("./TradeAnalyzer").then(m => ({ default: m.TradeAnalyzer })));
const LazyKeeperCalculator = lazy(() => import("./KeeperCalculator").then(m => ({ default: m.KeeperCalculator })));
const LazyActivationDiagnosticsPanel = lazy(() => import("./activation_diagnostics_panel").then(m => ({ default: m.ActivationDiagnosticsPanel })));

function App(): React.ReactElement {
  const {
    section, setSection,
    meta, metaError, metaLoading, retryMetaLoad,
    buildLabel, dataVersion,
    calculatorState,
    calculatorOverlay,
    watchlist, setWatchlist,
    effectiveDynastyPlayers,
    auth,
    premium,
    accountMenu,
    mobileNavMenu,
    bottomSheet,
    theme, toggleTheme,
    fantrax,
    tradeAnalyzerOpen, setTradeAnalyzerOpen,
    keeperCalculatorOpen, setKeeperCalculatorOpen,
    isMobileViewport,
    sectionNeedsMeta,
    projectionWindow,
    quickStart,
    calculatorPanelOpenSourceRef,
    setCalculatorPanelOpen,
  } = useAppState(API);

  const {
    calculatorPanelOpen,
    calculatorSettings,
    lastSuccessfulCalcRun,
    presets, setPresets,
    calculatorSectionRef,
    calculatorHeadingRef,
    scrollToCalculator,
    focusFirstCalculatorInput,
    openCalculatorPanel,
    handleCalculationSuccess,
    setCalculatorSettings,
    openMethodologyGlossary,
  } = calculatorState;

  const { authReady, authUser, authStatus, cloudStatus, signIn, signUp, signOut } = auth;
  const { subscription, tierLimits } = premium;
  const { accountMenuOpen, setAccountMenuOpen, accountMenuRef, accountTriggerRef } = accountMenu;
  const { mobileNavOpen, setMobileNavOpen, mobileNavMenuRef, mobileNavTriggerRef } = mobileNavMenu;
  const {
    showQuickStartOnboarding,
    requestQuickStartRun,
    dismissQuickStartOnboarding,
    handleRegisterQuickStartRunner,
  } = quickStart;

  const activationDiagnosticsEnabled = useMemo(() => resolveActivationDiagnosticsPanelEnabled({
    envEnabled: ACTIVATION_DIAGNOSTICS_PANEL_ENV_ENABLED,
    locationSearch: typeof window !== "undefined" ? window.location.search : "",
  }), []);

  return (
    <CalculatorOverlayContext.Provider value={calculatorOverlay}>
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <AppHeader
        section={section}
        setSection={setSection}
        theme={theme}
        toggleTheme={toggleTheme}
        authReady={authReady}
        authUser={authUser}
        authStatus={authStatus}
        cloudStatus={cloudStatus}
        signIn={signIn}
        signUp={signUp}
        signOut={signOut}
        accountMenuOpen={accountMenuOpen}
        setAccountMenuOpen={setAccountMenuOpen}
        accountMenuRef={accountMenuRef}
        accountTriggerRef={accountTriggerRef}
        mobileNavOpen={mobileNavOpen}
        setMobileNavOpen={setMobileNavOpen}
        mobileNavMenuRef={mobileNavMenuRef}
        mobileNavTriggerRef={mobileNavTriggerRef}
      />

      <main id="main-content">
        <HeroSection
          meta={meta}
          subscriptionActive={subscription?.status === "active"}
          projectionSeasons={projectionWindow.seasons || 20}
          scrollToCalculator={scrollToCalculator}
          setSection={setSection}
        />

        <div className="container">
          {showQuickStartOnboarding && ACTIVATION_SPRINT_ENABLED && (
            <section className="activation-strip" aria-label="Quick start dynasty rankings">
              <div className="activation-strip-copy">
                <p className="activation-strip-kicker">Recommended Start</p>
                <h2>Generate your first custom dynasty rankings now.</h2>
                <p>Run the default 12-team 5x5 setup, then fine-tune league settings after results load.</p>
                <ul className="activation-benefits" aria-label="Quick start benefits">
                  <li>League-specific rankings</li>
                  <li>Career plus season views</li>
                  <li>CSV and XLSX export</li>
                </ul>
              </div>
              <div className="activation-strip-actions" role="group" aria-label="Quick start options">
                <button
                  type="button"
                  className="activation-strip-btn activation-strip-btn-primary"
                  onClick={() => requestQuickStartRun("roto", { source: "activation_strip" })}
                >
                  Run Recommended 5x5 Roto
                </button>
                <button
                  type="button"
                  className="activation-strip-link"
                  onClick={() => requestQuickStartRun("points", { source: "activation_strip_points_link" })}
                >
                  Use Points Instead
                </button>
              </div>
              <button
                type="button"
                className="activation-strip-dismiss"
                onClick={dismissQuickStartOnboarding}
                aria-label="Dismiss quick start guide"
              >
                Dismiss
              </button>
            </section>
          )}
          {activationDiagnosticsEnabled && (
            <Suspense fallback={null}>
              <LazyActivationDiagnosticsPanel
                section={section}
                dataVersion={dataVersion}
              />
            </Suspense>
          )}
          {sectionNeedsMeta && metaLoading && !metaError && !meta && (
            <p className="methodology-note" role="status" aria-live="polite">Loading projections metadata...</p>
          )}
          {sectionNeedsMeta && metaError && (
            <section className="meta-error-panel" role="alert" aria-live="assertive">
              <h2>Unable to load projections metadata</h2>
              <p>{metaError}</p>
              <p>Try reloading metadata now. If this keeps failing, check backend readiness at <code>/api/ready</code>.</p>
              <div className="meta-error-actions">
                <button type="button" className="inline-btn" onClick={retryMetaLoad}>
                  Retry metadata request
                </button>
                <button
                  type="button"
                  className="inline-btn"
                  onClick={() => setSection("methodology")}
                >
                  Open Methodology
                </button>
              </div>
            </section>
          )}
          {section === "projections" && meta && (
            <div className="projections-workspace">
              <section
                className="embedded-calculator-section"
                aria-labelledby="embedded-calculator-heading"
                ref={calculatorSectionRef}
              >
                <div className="embedded-calculator-head">
                  <h2 id="embedded-calculator-heading" ref={calculatorHeadingRef as React.RefObject<HTMLHeadingElement | null>} tabIndex={-1}>
                    Dynasty Calculator
                  </h2>
                  <button
                    type="button"
                    className={`embedded-calculator-toggle ${calculatorPanelOpen ? "open" : ""}`.trim()}
                    onClick={() => {
                      if (isMobileViewport) {
                        openCalculatorPanel("panel_toggle");
                        bottomSheet.open();
                      } else {
                        setCalculatorPanelOpen(current => {
                          const nextValue = !current;
                          if (nextValue) {
                            calculatorPanelOpenSourceRef.current = "panel_toggle";
                          }
                          return nextValue;
                        });
                      }
                    }}
                    aria-expanded={isMobileViewport ? bottomSheet.isOpen : calculatorPanelOpen}
                    aria-controls="embedded-calculator-content"
                  >
                    <span className="embedded-calculator-toggle-label">
                      {(isMobileViewport ? bottomSheet.isOpen : calculatorPanelOpen) ? "Hide Calculator" : "Show Calculator"}
                    </span>
                    <span className="embedded-calculator-toggle-chevron" aria-hidden="true">v</span>
                  </button>
                </div>
                <p className="methodology-note embedded-calculator-note">
                  Configure your league settings and apply custom dynasty values directly in the projections table.
                </p>
                {calculatorPanelOpen && !isMobileViewport && (
                  <div id="embedded-calculator-content" className="embedded-calculator-content">
                    <FeatureErrorBoundary featureName="Dynasty Calculator">
                    <Suspense fallback={<p className="methodology-note" role="status" aria-live="polite">Loading calculator...</p>}>
                      <LazyDynastyCalculator
                        apiBase={API}
                        meta={meta}
                        presets={presets}
                        setPresets={setPresets}
                        hasSuccessfulRun={Boolean(lastSuccessfulCalcRun)}
                        onSettingsChange={setCalculatorSettings}
                        onCalculationSuccess={handleCalculationSuccess}
                        onRegisterQuickStartRunner={handleRegisterQuickStartRunner}
                        onOpenMethodologyGlossary={openMethodologyGlossary}
                        tierLimits={tierLimits}
                        fantrax={fantrax}
                      />
                    </Suspense>
                    </FeatureErrorBoundary>
                  </div>
                )}
              </section>
              <div className="projections-content">
                {tierLimits?.allowTradeAnalyzer && (
                  <div className="trade-analyzer-toggle-wrap">
                    <button
                      type="button"
                      className={`inline-btn ${tradeAnalyzerOpen ? "open" : ""}`.trim()}
                      onClick={() => setTradeAnalyzerOpen(v => !v)}
                    >
                      {tradeAnalyzerOpen ? "Hide Trade Analyzer" : "Open Trade Analyzer"}
                    </button>
                    <button
                      type="button"
                      className={`inline-btn ${keeperCalculatorOpen ? "open" : ""}`.trim()}
                      onClick={() => setKeeperCalculatorOpen(v => !v)}
                    >
                      {keeperCalculatorOpen ? "Hide Keeper Calculator" : "Open Keeper Calculator"}
                    </button>
                  </div>
                )}
                {tradeAnalyzerOpen && tierLimits?.allowTradeAnalyzer && (
                  <FeatureErrorBoundary featureName="Trade Analyzer">
                    <Suspense fallback={<p className="methodology-note" role="status" aria-live="polite">Loading trade analyzer...</p>}>
                      <LazyTradeAnalyzer
                        calculatorResults={effectiveDynastyPlayers}
                        onClose={() => setTradeAnalyzerOpen(false)}
                        onOpenCalculator={() => { openCalculatorPanel("trade_analyzer"); scrollToCalculator(); }}
                      />
                    </Suspense>
                  </FeatureErrorBoundary>
                )}
                {keeperCalculatorOpen && tierLimits?.allowTradeAnalyzer && (
                  <FeatureErrorBoundary featureName="Keeper Calculator">
                    <Suspense fallback={<p className="methodology-note" role="status" aria-live="polite">Loading keeper calculator...</p>}>
                      <LazyKeeperCalculator
                        calculatorResults={effectiveDynastyPlayers}
                        onClose={() => setKeeperCalculatorOpen(false)}
                        onOpenCalculator={() => { openCalculatorPanel("keeper_calculator"); scrollToCalculator(); }}
                        keeperLimit={
                          Number.isInteger(Number(calculatorSettings?.keeper_limit))
                            && Number(calculatorSettings?.keeper_limit) > 0
                            ? Number(calculatorSettings?.keeper_limit)
                            : null
                        }
                      />
                    </Suspense>
                  </FeatureErrorBoundary>
                )}
                <FeatureErrorBoundary featureName="Projections Explorer">
                <ProjectionsExplorer
                  apiBase={API}
                  meta={meta}
                  dataVersion={dataVersion}
                  watchlist={watchlist}
                  setWatchlist={setWatchlist}
                  hasSuccessfulCalcRun={Boolean(lastSuccessfulCalcRun)}
                  activeCalculatorSettings={calculatorSettings}
                  tierLimits={tierLimits}
                  fantraxRosterPlayerKeys={fantrax.rosterPlayerKeys}
                />
                </FeatureErrorBoundary>
              </div>
            </div>
          )}
          {section === "pricing" && (
            <PricingSection authUser={authUser} subscription={subscription} />
          )}
          {section === "methodology" && (
            <Suspense fallback={<p className="methodology-note" role="status" aria-live="polite">Loading methodology...</p>}>
              <LazyMethodologySection />
            </Suspense>
          )}
        </div>
        {section === "projections" && meta && !showQuickStartOnboarding && !bottomSheet.isOpen && (
          <button
            type="button"
            className="mobile-run-cta"
            onClick={() => {
              openCalculatorPanel("mobile_cta");
              if (isMobileViewport) {
                bottomSheet.open();
              } else {
                window.requestAnimationFrame(() => {
                  scrollToCalculator();
                  focusFirstCalculatorInput();
                });
              }
            }}
          >
            Run Dynasty Rankings
          </button>
        )}
        {isMobileViewport && meta && (
          <MobileCalculatorSheet
            isOpen={bottomSheet.isOpen}
            onClose={bottomSheet.close}
            sheetRef={bottomSheet.sheetRef}
            dragHandleProps={bottomSheet.dragHandleProps}
            sheetStyle={bottomSheet.sheetStyle}
          >
            <FeatureErrorBoundary featureName="Dynasty Calculator">
              <Suspense fallback={<p className="methodology-note" role="status" aria-live="polite">Loading calculator...</p>}>
                <LazyDynastyCalculator
                  apiBase={API}
                  meta={meta}
                  presets={presets}
                  setPresets={setPresets}
                  hasSuccessfulRun={Boolean(lastSuccessfulCalcRun)}
                  onSettingsChange={setCalculatorSettings}
                  onCalculationSuccess={handleCalculationSuccess}
                  onRegisterQuickStartRunner={handleRegisterQuickStartRunner}
                  onOpenMethodologyGlossary={openMethodologyGlossary}
                  tierLimits={tierLimits}
                  fantrax={fantrax}
                />
              </Suspense>
            </FeatureErrorBoundary>
          </MobileCalculatorSheet>
        )}
      </main>

      <AppFooter meta={meta} buildLabel={buildLabel} apiBase={API} />
    </>
    </CalculatorOverlayContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route path="/player/:slug" element={
            <FeatureErrorBoundary featureName="Player Page">
              <Suspense fallback={<p className="methodology-note" role="status" aria-live="polite">Loading player...</p>}>
                <LazyPlayerPage />
              </Suspense>
            </FeatureErrorBoundary>
          } />
          <Route path="/movers" element={
            <FeatureErrorBoundary featureName="Movers Page">
              <Suspense fallback={<p className="methodology-note" role="status" aria-live="polite">Loading movers...</p>}>
                <LazyMoversPage />
              </Suspense>
            </FeatureErrorBoundary>
          } />
          <Route path="*" element={<App />} />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
    </QueryClientProvider>
  </ErrorBoundary>
);
