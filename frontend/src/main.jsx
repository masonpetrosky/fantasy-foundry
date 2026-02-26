import React, { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles/app.css";
import { AUTH_SYNC_ENABLED } from "./supabase_client.js";
import { AccountPanel } from "./account_panel.jsx";
import { ActivationDiagnosticsPanel, resolveActivationDiagnosticsPanelEnabled } from "./activation_diagnostics_panel.jsx";
import { resolveApiBase } from "./api_base.js";
import { PRIMARY_NAV_ITEMS } from "./app_content.js";
import { ProjectionsExplorer } from "./projections_explorer.jsx";
import { installAnalyticsDebugBridge, setAnalyticsContext, trackEvent } from "./analytics.js";
import { ErrorBoundary } from "./error_boundary.jsx";
import { FeatureErrorBoundary } from "./feature_error_boundary.jsx";
import { formatIsoDateLabel, resolveProjectionWindow } from "./formatting_utils.js";
import { useCalculatorOverlay } from "./hooks/useCalculatorOverlay.js";
import { useCalculatorState } from "./hooks/useCalculatorState.js";
import { useMetadata } from "./hooks/useMetadata.js";
import { useQuickStart } from "./hooks/useQuickStart.js";
import { useVersionPolling } from "./hooks/useVersionPolling.js";
import { useAccountMenu } from "./hooks/useAccountMenu.js";
import { useAccountSync } from "./hooks/useAccountSync.js";
import {
  readLastSuccessfulCalcRun,
  readPlayerWatchlist,
  readSessionFirstRunLandingTimestamp,
  writeSessionFirstRunLandingTimestamp,
  writePlayerWatchlist,
} from "./app_state_storage.js";

const API = resolveApiBase();
const ACTIVATION_SPRINT_ENABLED = String(import.meta.env.VITE_FF_ACTIVATION_SPRINT_V1 || "1").trim() !== "0";
const ACTIVATION_DIAGNOSTICS_PANEL_ENV_ENABLED = String(
  import.meta.env.VITE_FF_ACTIVATION_DIAGNOSTICS_PANEL_V1 || "0"
).trim() === "1";
const LazyMethodologySection = lazy(() => (
  import("./methodology_section.jsx").then(module => ({ default: module.MethodologySection }))
));
const LazyDynastyCalculator = lazy(() => (
  import("./dynasty_calculator.jsx").then(module => ({ default: module.DynastyCalculator }))
));

function App() {
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
    applyCalculatorOverlay,
    clearCalculatorOverlay,
  } = useCalculatorOverlay(dataVersion);
  const { authReady, authUser, authStatus, cloudStatus, signIn, signUp, signOut } = useAccountSync({
    presets,
    setPresets,
    watchlist,
    setWatchlist,
  });
  const { accountMenuOpen, setAccountMenuOpen, accountMenuRef, accountTriggerRef } = useAccountMenu({ section });
  const landingTrackedRef = useRef(false);
  const accountMenuLabel = !AUTH_SYNC_ENABLED || authUser ? "Account" : "Sign In";
  const sectionNeedsMeta = section === "projections";
  const projectionFreshness = useMemo(() => (
    meta?.projection_freshness && typeof meta.projection_freshness === "object" ? meta.projection_freshness : {}
  ), [meta]);
  const projectionCoveragePct = Number.isFinite(Number(projectionFreshness?.date_coverage_pct))
    ? Number(projectionFreshness.date_coverage_pct)
    : 0;
  const projectionLastUpdated = String(
    meta?.last_projection_update || projectionFreshness?.newest_projection_date || ""
  ).trim();
  const projectionWindow = useMemo(() => resolveProjectionWindow(meta), [meta]);
  const resolvedScoringMode = String(calculatorSettings?.scoring_mode || "").trim().toLowerCase() === "points"
    ? "points"
    : calculatorSettings
      ? "roto"
      : "unknown";

  const {
    showQuickStartOnboarding,
    showQuickStartReminder,
    requestQuickStartRun,
    dismissQuickStartOnboarding,
    reopenQuickStartOnboarding,
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
          {meta && (
            <>
              <p className="hero-freshness" role="status">
                Updated {formatIsoDateLabel(projectionLastUpdated)}. Coverage: {projectionCoveragePct.toFixed(1)}% of rows include projection dates.
              </p>
              <div className="hero-stats fade-up fade-up-2">
                <div className="hero-stat">
                  <div className="number">{meta.total_hitters}</div>
                  <div className="label">Hitters</div>
                </div>
                <div className="hero-stat">
                  <div className="number">{meta.total_pitchers}</div>
                  <div className="label">Pitchers</div>
                </div>
                <div className="hero-stat">
                  <div className="number">{projectionWindow.seasons || 20}</div>
                  <div className="label">Seasons</div>
                </div>
              </div>
            </>
          )}
        </div>

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
          {showQuickStartReminder && ACTIVATION_SPRINT_ENABLED && (
            <section className="activation-reminder" aria-label="Quick start reminder">
              <p>Quick start is hidden. Reopen it or run the default setup now.</p>
              <div className="activation-reminder-actions">
                <button
                  type="button"
                  className="inline-btn"
                  onClick={reopenQuickStartOnboarding}
                >
                  Reopen Quick Start
                </button>
                <button
                  type="button"
                  className="inline-btn activation-reminder-run"
                  onClick={() => requestQuickStartRun("roto", { source: "activation_reminder" })}
                >
                  Run Recommended 5x5 Roto
                </button>
              </div>
            </section>
          )}
          {activationDiagnosticsEnabled && (
            <ActivationDiagnosticsPanel
              section={section}
              dataVersion={dataVersion}
            />
          )}
          {sectionNeedsMeta && meta && (
            <div className="data-freshness-banner app-freshness-banner" role="status" aria-live="polite">
              Projection window {projectionWindow.start || "?"}-{projectionWindow.end || "?"} · Last updated {formatIsoDateLabel(projectionLastUpdated)} · Date coverage {projectionCoveragePct.toFixed(1)}%
            </div>
          )}
          {sectionNeedsMeta && lastSuccessfulCalcRun && (
            <section className="calc-last-success-summary" aria-label="Last successful calculator run">
              <p className="calc-last-success-kicker">Last successful run</p>
              <p className="calc-last-success-copy">
                {lastSuccessfulCalcRun.teams}-team {lastSuccessfulCalcRun.scoringMode === "points" ? "points" : "roto"} ·
                {" "}start {lastSuccessfulCalcRun.startYear || "default"} ·
                {" "}{lastSuccessfulCalcRun.horizon}-year horizon ·
                {" "}{lastSuccessfulCalcRun.playerCount.toLocaleString()} players ·
                {" "}completed {formatIsoDateLabel(lastSuccessfulCalcRun.completedAt)}.
              </p>
              <div className="calc-last-success-actions">
                <button
                  type="button"
                  className="inline-btn"
                  onClick={() => {
                    openCalculatorPanel("last_run_review");
                    window.requestAnimationFrame(() => {
                      scrollToCalculator();
                      focusFirstCalculatorInput();
                    });
                  }}
                >
                  Review calculator settings
                </button>
                <button
                  type="button"
                  className="inline-btn"
                  onClick={() => requestQuickStartRun(lastSuccessfulCalcRun.scoringMode, { source: "last_success_rerun" })}
                >
                  Run this setup again
                </button>
              </div>
            </section>
          )}
          {sectionNeedsMeta && (
            <p className="methodology-note app-methodology-note">
              For glossary definitions and detailed valuation notes, open the <strong>Methodology</strong> tab.
            </p>
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
                  <h2 id="embedded-calculator-heading" ref={calculatorHeadingRef} tabIndex={-1}>
                    Dynasty Calculator
                  </h2>
                  <button
                    type="button"
                    className={`embedded-calculator-toggle ${calculatorPanelOpen ? "open" : ""}`.trim()}
                    onClick={() => {
                      setCalculatorPanelOpen(current => {
                        const nextValue = !current;
                        if (nextValue) {
                          calculatorPanelOpenSourceRef.current = "panel_toggle";
                        }
                        return nextValue;
                      });
                    }}
                    aria-expanded={calculatorPanelOpen}
                    aria-controls="embedded-calculator-content"
                  >
                    <span className="embedded-calculator-toggle-label">
                      {calculatorPanelOpen ? "Hide Calculator" : "Show Calculator"}
                    </span>
                    <span className="embedded-calculator-toggle-chevron" aria-hidden="true">v</span>
                  </button>
                </div>
                <p className="methodology-note embedded-calculator-note">
                  Configure your league settings and apply custom dynasty values directly in the projections table.
                </p>
                {calculatorPanelOpen && (
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
                      />
                    </Suspense>
                    </FeatureErrorBoundary>
                  </div>
                )}
              </section>
              <div className="projections-content">
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
                />
                </FeatureErrorBoundary>
              </div>
            </div>
          )}
          {section === "methodology" && (
            <Suspense fallback={<p className="methodology-note">Loading methodology...</p>}>
              <LazyMethodologySection />
            </Suspense>
          )}
        </div>
        {section === "projections" && meta && !showQuickStartOnboarding && !showQuickStartReminder && (
          <button
            type="button"
            className="mobile-run-cta"
            onClick={() => {
              openCalculatorPanel("mobile_cta");
              window.requestAnimationFrame(() => {
                scrollToCalculator();
                focusFirstCalculatorInput();
              });
            }}
          >
            Run Dynasty Rankings
          </button>
        )}
      </main>

      <footer>
        Projections updated as-needed.
        {buildLabel && <span className="build-id">Build {buildLabel}</span>}
      </footer>
    </>
  );
}

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------
createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
