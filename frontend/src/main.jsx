import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AUTH_SYNC_ENABLED } from "./supabase_client.js";
import { AccountPanel } from "./account_panel.jsx";
import { resolveApiBase } from "./api_base.js";
import { PRIMARY_NAV_ITEMS } from "./app_content.js";
import { MethodologySection } from "./methodology_section.jsx";
import { ProjectionsExplorer } from "./projections_explorer.jsx";
import { DynastyCalculator } from "./dynasty_calculator.jsx";
import { useVersionPolling } from "./hooks/useVersionPolling.js";
import { useAccountSync } from "./hooks/useAccountSync.js";
import {
  CALC_LINK_QUERY_PARAM,
  readCalculatorPresets,
  readPlayerWatchlist,
  stablePlayerKeyFromRow,
  writeCalculatorPresets,
  writePlayerWatchlist,
} from "./app_state_storage.js";

const API = resolveApiBase();

function buildCalculatorOverlayMap(result) {
  const rows = Array.isArray(result?.data) ? result.data : [];
  const byPlayerKey = {};

  rows.forEach(row => {
    const key = stablePlayerKeyFromRow(row);
    if (!key) return;

    const overlayRow = {};
    if (row?.DynastyValue != null && row?.DynastyValue !== "") {
      overlayRow.DynastyValue = row.DynastyValue;
    }
    Object.keys(row || {}).forEach(col => {
      if (!col.startsWith("Value_")) return;
      const value = row[col];
      if (value == null || value === "") return;
      overlayRow[col] = value;
    });
    if (Object.keys(overlayRow).length === 0) return;
    byPlayerKey[key] = overlayRow;
  });

  return byPlayerKey;
}

function App() {
  const [section, setSection] = useState("projections"); // projections | methodology
  const [calculatorPanelOpen, setCalculatorPanelOpen] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return Boolean(String(params.get(CALC_LINK_QUERY_PARAM) || "").trim());
  });
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState("");
  const { buildLabel, dataVersion } = useVersionPolling(API);
  const [presets, setPresets] = useState(() => readCalculatorPresets());
  const [watchlist, setWatchlist] = useState(() => readPlayerWatchlist());
  const [calculatorSettings, setCalculatorSettings] = useState(null);
  const [calculatorOverlayByPlayerKey, setCalculatorOverlayByPlayerKey] = useState({});
  const [calculatorOverlayActive, setCalculatorOverlayActive] = useState(false);
  const [calculatorOverlayJobId, setCalculatorOverlayJobId] = useState("");
  const { authReady, authUser, authStatus, cloudStatus, signIn, signUp, signOut } = useAccountSync({
    presets,
    setPresets,
    watchlist,
    setWatchlist,
  });
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef(null);
  const accountMenuLabel = !AUTH_SYNC_ENABLED || authUser ? "Account" : "Sign In";
  const sectionNeedsMeta = section === "projections";
  const calculatorOverlayPlayerCount = Object.keys(calculatorOverlayByPlayerKey).length;

  const applyCalculatorOverlay = useCallback((result, _settings, runMeta) => {
    const nextOverlay = buildCalculatorOverlayMap(result);
    const hasOverlay = Object.keys(nextOverlay).length > 0;
    const nextJobId = hasOverlay ? String(runMeta?.jobId || "").trim() : "";
    setCalculatorOverlayByPlayerKey(nextOverlay);
    setCalculatorOverlayActive(hasOverlay);
    setCalculatorOverlayJobId(nextJobId);
  }, []);

  const clearCalculatorOverlay = useCallback(() => {
    setCalculatorOverlayByPlayerKey({});
    setCalculatorOverlayActive(false);
    setCalculatorOverlayJobId("");
  }, []);

  useEffect(() => {
    writeCalculatorPresets(presets);
  }, [presets]);

  useEffect(() => {
    writePlayerWatchlist(watchlist);
  }, [watchlist]);

  useEffect(() => {
    const controller = new AbortController();
    setMetaError("");
    fetch(`${API}/api/meta`, { signal: controller.signal })
      .then(r => {
        if (!r.ok) throw new Error(`Server returned ${r.status} while loading /api/meta`);
        return r.json();
      })
      .then(res => {
        setMeta(res);
      })
      .catch(err => {
        if (err?.name === "AbortError") return;
        setMetaError(err.message || "Failed to load metadata");
        console.error(err);
      });
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!accountMenuOpen) return undefined;

    function handleOutsideClick(event) {
      if (accountMenuRef.current && !accountMenuRef.current.contains(event.target)) {
        setAccountMenuOpen(false);
      }
    }

    function handleEscape(event) {
      if (event.key === "Escape") {
        setAccountMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("touchstart", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("touchstart", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [accountMenuOpen]);

  useEffect(() => {
    setAccountMenuOpen(false);
  }, [section]);

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
          <h1>The Only <em>20-Year</em><br/>Dynasty Baseball Projections</h1>
          <p>Comprehensive player projections from 2026 through 2045. Browse the data, configure your league settings, and generate personalized dynasty rankings.</p>
          {meta && (
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
                <div className="number">20</div>
                <div className="label">Seasons</div>
              </div>
            </div>
          )}
        </div>

        <div className="container">
          {sectionNeedsMeta && (
            <p className="methodology-note app-methodology-note">
              For glossary definitions and detailed valuation notes, open the <strong>Methodology</strong> tab.
            </p>
          )}
          {sectionNeedsMeta && metaError && (
            <p style={{marginBottom: "16px", color: "var(--red)"}}>
              Unable to load API data. Check that the backend is running and reachable. ({metaError})
            </p>
          )}
          {section === "projections" && meta && (
            <div className="projections-workspace">
              <section className="embedded-calculator-section" aria-labelledby="embedded-calculator-heading">
                <div className="embedded-calculator-head">
                  <h2 id="embedded-calculator-heading">Dynasty Calculator</h2>
                  <button
                    type="button"
                    className={`embedded-calculator-toggle ${calculatorPanelOpen ? "open" : ""}`.trim()}
                    onClick={() => setCalculatorPanelOpen(current => !current)}
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
                    <DynastyCalculator
                      apiBase={API}
                      meta={meta}
                      presets={presets}
                      setPresets={setPresets}
                      onSettingsChange={setCalculatorSettings}
                      onApplyToMainTable={applyCalculatorOverlay}
                      onClearMainTableOverlay={clearCalculatorOverlay}
                      mainTableOverlayActive={calculatorOverlayActive}
                    />
                  </div>
                )}
              </section>
              <div className="projections-content">
                <ProjectionsExplorer
                  apiBase={API}
                  meta={meta}
                  dataVersion={dataVersion}
                  watchlist={watchlist}
                  setWatchlist={setWatchlist}
                  activeCalculatorSettings={calculatorSettings}
                  calculatorOverlayByPlayerKey={calculatorOverlayByPlayerKey}
                  calculatorOverlayActive={calculatorOverlayActive}
                  calculatorOverlayJobId={calculatorOverlayJobId}
                  calculatorOverlayPlayerCount={calculatorOverlayPlayerCount}
                />
              </div>
            </div>
          )}
          {section === "methodology" && <MethodologySection />}
        </div>
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
createRoot(document.getElementById("root")).render(<App />);
