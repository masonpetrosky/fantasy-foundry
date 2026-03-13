import React, { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./styles/typography-table.css";
import "./styles/app.css";
import { initSentry } from "./sentry";
import { initGA4 } from "./ga4";

initSentry();
initGA4();
import { AUTH_SYNC_ENABLED } from "./supabase_client";
import { AccountPanel } from "./account_panel";
import { ActivationDiagnosticsPanel, resolveActivationDiagnosticsPanelEnabled } from "./activation_diagnostics_panel";
import { resolveApiBase } from "./api_base";
import { PRIMARY_NAV_ITEMS } from "./app_content";
import { ProjectionsExplorer } from "./projections_explorer";
import { MobileCalculatorSheet } from "./MobileCalculatorSheet";
import { installAnalyticsDebugBridge, setAnalyticsContext, trackEvent } from "./analytics";
import { ErrorBoundary } from "./error_boundary";
import { FeatureErrorBoundary } from "./feature_error_boundary";
import { ToastProvider } from "./Toast";
import { PlayerPage } from "./PlayerPage";
import { MoversPage } from "./MoversPage";
import { TradeAnalyzer } from "./TradeAnalyzer";
import { KeeperCalculator } from "./KeeperCalculator";
import { PricingSection } from "./PricingSection";
import { NewsletterSignup } from "./NewsletterSignup";
import { MOBILE_BREAKPOINT_QUERY } from "./features/projections/hooks/useProjectionLayoutState";
import { resolveProjectionWindow } from "./formatting_utils";
import { useBottomSheet } from "./hooks/useBottomSheet";
import { useCalculatorOverlay } from "./hooks/useCalculatorOverlay";
import { useDefaultDynastyPlayers } from "./hooks/useDefaultDynastyPlayers";
import { useCalculatorState } from "./hooks/useCalculatorState";
import { useMetadata } from "./hooks/useMetadata";
import { useQuickStart } from "./hooks/useQuickStart";
import { useVersionPolling } from "./hooks/useVersionPolling";
import { useAccountMenu } from "./hooks/useAccountMenu";
import { useMobileNavMenu } from "./hooks/useMobileNavMenu";
import { useAccountSync } from "./hooks/useAccountSync";
import { usePremiumStatus } from "./hooks/usePremiumStatus";
import { useTheme } from "./hooks/useTheme";
import { useFantraxLeague } from "./hooks/useFantraxLeague";
import { parseBillingRedirectParam, cleanBillingParam } from "./billing_redirect";
import { useToastContext } from "./Toast";
import {
  readLastSuccessfulCalcRun,
  readPlayerWatchlist,
  readSessionFirstRunLandingTimestamp,
  writeSessionFirstRunLandingTimestamp,
  writePlayerWatchlist,
} from "./app_state_storage";

const API = resolveApiBase();
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

function App(): React.ReactElement {
  const [section, setSection] = useState("projections"); // projections | methodology
  const { meta, metaError, metaLoading, retryMetaLoad } = useMetadata(API);
  const { buildLabel, dataVersion } = useVersionPolling(API);
  const {
    calculatorPanelOpen,
    setCalculatorPanelOpen,
    calculatorSettings,
    setCalculatorSettings,
    lastSuccessfulCalcRun,
    presets,
    setPresets,
    calculatorSectionRef,
    calculatorHeadingRef,
    calculatorPanelOpenSourceRef,
    scrollToCalculator,
    focusFirstCalculatorInput,
    openCalculatorPanel,
    handleCalculationSuccess,
    openMethodologyGlossary,
  } = useCalculatorState({ section, setSection, meta });
  const [watchlist, setWatchlist] = useState(() => readPlayerWatchlist());
  const {
    calculatorOverlayByPlayerKey,
    calculatorOverlayActive,
    calculatorOverlayJobId,
    calculatorOverlayDataVersion,
    calculatorOverlaySummary,
    calculatorOverlayPlayerCount,
    calculatorResultRows,
    applyCalculatorOverlay,
    clearCalculatorOverlay,
  } = useCalculatorOverlay(dataVersion);
  const defaultDynastyPlayers = useDefaultDynastyPlayers(API);
  const effectiveDynastyPlayers = useMemo(
    () => (calculatorResultRows.length > 0 ? calculatorResultRows : defaultDynastyPlayers),
    [calculatorResultRows, defaultDynastyPlayers],
  );
  const { authReady, authUser, authStatus, cloudStatus, signIn, signUp, signOut } = useAccountSync({
    presets,
    setPresets,
    watchlist,
    setWatchlist,
  });
  const { subscription, tierLimits } = usePremiumStatus(authUser);
  const toast = useToastContext();
  const { accountMenuOpen, setAccountMenuOpen, accountMenuRef, accountTriggerRef } = useAccountMenu({ section });
  const { mobileNavOpen, setMobileNavOpen, mobileNavMenuRef, mobileNavTriggerRef } = useMobileNavMenu({ section });
  const bottomSheet = useBottomSheet();
  const { theme, toggleTheme } = useTheme();
  const fantrax = useFantraxLeague();
  const [tradeAnalyzerOpen, setTradeAnalyzerOpen] = useState(false);
  const [keeperCalculatorOpen, setKeeperCalculatorOpen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(() => window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches);
  useEffect(() => {
    const mql = window.matchMedia(MOBILE_BREAKPOINT_QUERY);
    const handler = (e: MediaQueryListEvent): void => setIsMobileViewport(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);
  const landingTrackedRef = useRef(false);
  const accountMenuLabel = !AUTH_SYNC_ENABLED || authUser ? "Account" : "Sign In";
  const sectionNeedsMeta = section === "projections";
  const projectionWindow = useMemo(() => resolveProjectionWindow(meta), [meta]);
  const resolvedScoringMode = String(calculatorSettings?.scoring_mode || "").trim().toLowerCase() === "points"
    ? "points"
    : calculatorSettings
      ? "roto"
      : "unknown";

  const {
    showQuickStartOnboarding,
    requestQuickStartRun,
    dismissQuickStartOnboarding,
    handleRegisterQuickStartRunner,
  } = useQuickStart({
    meta,
    section,
    dataVersion,
    calculatorPanelOpen,
    lastSuccessfulCalcRun,
    openCalculatorPanel,
    scrollToCalculator,
    focusCalculatorHeading: focusFirstCalculatorInput,
  });
  const activationDiagnosticsEnabled = useMemo(() => resolveActivationDiagnosticsPanelEnabled({
    envEnabled: ACTIVATION_DIAGNOSTICS_PANEL_ENV_ENABLED,
    locationSearch: typeof window !== "undefined" ? window.location.search : "",
  }), []);

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

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header>
        <div className="nav-inner">
          <a
            className="brand"
            href="#"
            onClick={event => {
              event.preventDefault();
              setSection("projections");
            }}
            aria-label="Fantasy Foundry home"
          >
            <span className="brand-mark" aria-hidden="true">
              <img src="/assets/favicon.svg" alt="" />
            </span>
            <span className="brand-text">
              <span className="brand-title">Fantasy Foundry</span>
              <span className="brand-tagline">Dynasty Baseball Intelligence</span>
            </span>
          </a>
          <nav className="primary-nav" aria-label="Primary">
            <div className="primary-nav-scroll">
              {PRIMARY_NAV_ITEMS.map(item => (
                <button
                  key={item.key}
                  type="button"
                  className={`primary-nav-btn ${section === item.key ? "active" : ""}`.trim()}
                  onClick={() => setSection(item.key)}
                  aria-pressed={section === item.key}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </nav>
          <div className="mobile-nav-menu" ref={mobileNavMenuRef}>
            <button
              type="button"
              ref={mobileNavTriggerRef}
              className={`inline-btn mobile-nav-toggle${mobileNavOpen ? " open" : ""}`}
              onClick={() => setMobileNavOpen(prev => !prev)}
              aria-expanded={mobileNavOpen}
              aria-controls="mobile-nav-dropdown"
              aria-label="Navigation menu"
            >
              <span aria-hidden="true">{mobileNavOpen ? "\u2715" : "\u2630"}</span>
            </button>
            {mobileNavOpen && (
              <nav id="mobile-nav-dropdown" className="mobile-nav-dropdown" aria-label="Primary">
                {PRIMARY_NAV_ITEMS.map(item => (
                  <button
                    key={item.key}
                    type="button"
                    className={`mobile-nav-item${section === item.key ? " active" : ""}`}
                    onClick={() => setSection(item.key)}
                    aria-pressed={section === item.key}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
            )}
          </div>
          <button
            type="button"
            className="inline-btn theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title={theme === "dark" ? "Light mode" : "Dark mode"}
          >
            {theme === "dark" ? "\u2600" : "\u263E"}
          </button>
          <div className="account-menu" ref={accountMenuRef}>
            <button
              type="button"
              ref={accountTriggerRef}
              className={`inline-btn account-menu-btn ${accountMenuOpen ? "open" : ""}`.trim()}
              onClick={() => setAccountMenuOpen(open => !open)}
              aria-expanded={accountMenuOpen}
              aria-controls="header-account-panel"
            >
              <span>{accountMenuLabel}</span>
              {authUser && <span className="account-menu-pill">Signed In</span>}
            </button>
            {accountMenuOpen && (
              <div id="header-account-panel" className="account-popover" role="region" aria-label="Account">
                <AccountPanel
                  authEnabled={AUTH_SYNC_ENABLED}
                  authReady={authReady}
                  authUser={authUser}
                  authStatus={authStatus}
                  cloudStatus={cloudStatus}
                  onSignIn={signIn}
                  onSignUp={signUp}
                  onSignOut={signOut}
                />
              </div>
            )}
          </div>
        </div>
      </header>

      <main id="main-content">
        <div className="hero fade-up">
          <h1>The Only <em>20-Year</em><br />Dynasty Baseball Projections</h1>
          <p>Comprehensive player projections from 2026 through 2045. Browse the data, configure your league settings, and generate personalized dynasty rankings.</p>
          <div className="hero-actions fade-up fade-up-2">
            {subscription?.status !== "active" && (
              <button className="hero-cta hero-cta-primary" onClick={scrollToCalculator}>
                Get Started Free
              </button>
            )}
            <button className="hero-cta hero-cta-secondary" onClick={() => setSection("methodology")}>
              See Methodology
            </button>
          </div>
          {meta && (
            <>
              <div className="hero-stats fade-up fade-up-2">
                <div className="hero-stat">
                  <div className="number">{String(meta.total_hitters)}</div>
                  <div className="label">Hitters</div>
                </div>
                <div className="hero-stat">
                  <div className="number">{String(meta.total_pitchers)}</div>
                  <div className="label">Pitchers</div>
                </div>
                <div className="hero-stat">
                  <div className="number">{projectionWindow.seasons || 20}</div>
                  <div className="label">Seasons</div>
                </div>
              </div>
              <div className="hero-proof fade-up fade-up-2">
                <span>Updated for the 2026 season</span>
              </div>
            </>
          )}
        </div>

        <section className="how-it-works fade-up">
          <div className="how-it-works-steps">
            <div className="how-it-works-step">
              <div className="how-it-works-number">1</div>
              <h3>Browse Projections</h3>
              <p>Explore 20 years of MLB projections for hundreds of hitters and pitchers.</p>
            </div>
            <div className="how-it-works-step">
              <div className="how-it-works-number">2</div>
              <h3>Configure Your League</h3>
              <p>Set your roster slots, scoring categories, and league size to match your format.</p>
            </div>
            <div className="how-it-works-step">
              <div className="how-it-works-number">3</div>
              <h3>Generate Rankings</h3>
              <p>Run Monte Carlo simulations to produce custom dynasty values for every player.</p>
            </div>
          </div>
        </section>

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
              >
                Dismiss
              </button>
            </section>
          )}
          {activationDiagnosticsEnabled && (
            <ActivationDiagnosticsPanel
              section={section}
              dataVersion={dataVersion}
            />
          )}
          {sectionNeedsMeta && metaLoading && !metaError && !meta && (
            <p className="methodology-note">Loading projections metadata...</p>
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
                    <Suspense fallback={<p className="methodology-note">Loading calculator...</p>}>
                      <LazyDynastyCalculator
                        apiBase={API}
                        meta={meta}
                        presets={presets}
                        setPresets={setPresets}
                        hasSuccessfulRun={Boolean(lastSuccessfulCalcRun)}
                        onSettingsChange={setCalculatorSettings}
                        onApplyToMainTable={applyCalculatorOverlay}
                        onCalculationSuccess={handleCalculationSuccess}
                        onClearMainTableOverlay={clearCalculatorOverlay}
                        mainTableOverlayActive={calculatorOverlayActive}
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
                  <TradeAnalyzer
                    calculatorResults={effectiveDynastyPlayers}
                    onClose={() => setTradeAnalyzerOpen(false)}
                    onOpenCalculator={() => { openCalculatorPanel("trade_analyzer"); scrollToCalculator(); }}
                  />
                )}
                {keeperCalculatorOpen && tierLimits?.allowTradeAnalyzer && (
                  <KeeperCalculator
                    calculatorResults={effectiveDynastyPlayers}
                    onClose={() => setKeeperCalculatorOpen(false)}
                    onOpenCalculator={() => { openCalculatorPanel("keeper_calculator"); scrollToCalculator(); }}
                  />
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
                  calculatorOverlayByPlayerKey={calculatorOverlayByPlayerKey}
                  calculatorOverlayActive={calculatorOverlayActive}
                  calculatorOverlayJobId={calculatorOverlayJobId}
                  calculatorOverlayDataVersion={calculatorOverlayDataVersion}
                  calculatorOverlayPlayerCount={calculatorOverlayPlayerCount}
                  calculatorOverlaySummary={calculatorOverlaySummary}
                  onClearCalculatorOverlay={clearCalculatorOverlay}
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
            <Suspense fallback={<p className="methodology-note">Loading methodology...</p>}>
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
              <Suspense fallback={<p className="methodology-note">Loading calculator...</p>}>
                <LazyDynastyCalculator
                  apiBase={API}
                  meta={meta}
                  presets={presets}
                  setPresets={setPresets}
                  hasSuccessfulRun={Boolean(lastSuccessfulCalcRun)}
                  onSettingsChange={setCalculatorSettings}
                  onApplyToMainTable={applyCalculatorOverlay}
                  onCalculationSuccess={handleCalculationSuccess}
                  onClearMainTableOverlay={clearCalculatorOverlay}
                  mainTableOverlayActive={calculatorOverlayActive}
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

      <footer>
        <div className="footer-inner">
          <div>
            {meta?.last_projection_update
              ? <>Projections updated {meta.last_projection_update}.</>
              : <>Projections updated as-needed.</>
            }
            {buildLabel && <span className="build-id">Build {buildLabel}</span>}
          </div>
          <NewsletterSignup apiBase={API} />
        </div>
      </footer>
    </>
  );
}

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------
createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route path="/player/:slug" element={<PlayerPage />} />
          <Route path="/movers" element={<MoversPage />} />
          <Route path="*" element={<App />} />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  </ErrorBoundary>
);
