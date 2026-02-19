import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AUTH_SYNC_ENABLED, SUPABASE_PREFS_TABLE, loadSupabaseClient } from "./supabase_client.js";
import { AccountPanel } from "./account_panel.jsx";
import { resolveApiBase } from "./api_base.js";
import { PRIMARY_NAV_ITEMS } from "./app_content.js";
import { MethodologySection } from "./methodology_section.jsx";
import { ProjectionsExplorer } from "./projections_explorer.jsx";
import { DynastyCalculator } from "./dynasty_calculator.jsx";
import {
  BUILD_QUERY_PARAM,
  BUILD_STORAGE_KEY,
  CLOUD_SYNC_DEBOUNCE_MS,
  buildCloudPreferencesPayload,
  formatAuthError,
  normalizeCloudPreferences,
  readCalculatorPresets,
  readPlayerWatchlist,
  safeReadStorage,
  safeWriteStorage,
  writeCalculatorPresets,
  writePlayerWatchlist,
} from "./app_state_storage.js";

const API = resolveApiBase();
const INDEX_BUILD_ID = (() => {
  const metaEl = document.querySelector('meta[name="ff-build-id"]');
  const value = String(metaEl?.getAttribute("content") || "").trim();
  return value.startsWith("__APP_BUILD_") ? "" : value;
})();
const VERSION_POLL_INTERVAL_MS = 60000;

function App() {
  const [section, setSection] = useState("projections"); // projections | calculator | methodology
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState("");
  const [buildLabel, setBuildLabel] = useState("");
  const [dataVersion, setDataVersion] = useState("");
  const [presets, setPresets] = useState(() => readCalculatorPresets());
  const [watchlist, setWatchlist] = useState(() => readPlayerWatchlist());
  const [authReady, setAuthReady] = useState(!AUTH_SYNC_ENABLED);
  const [authUser, setAuthUser] = useState(null);
  const [authStatus, setAuthStatus] = useState("");
  const [cloudStatus, setCloudStatus] = useState("");
  const [cloudReadyForSave, setCloudReadyForSave] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const presetsRef = useRef(presets);
  const watchlistRef = useRef(watchlist);
  const versionEtagRef = useRef("");
  const accountMenuRef = useRef(null);
  const accountMenuLabel = !AUTH_SYNC_ENABLED || authUser ? "Account" : "Sign In";
  const sectionNeedsMeta = section === "projections" || section === "calculator";

  useEffect(() => {
    presetsRef.current = presets;
  }, [presets]);

  useEffect(() => {
    watchlistRef.current = watchlist;
  }, [watchlist]);

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
    let cancelled = false;
    let timer = null;
    let activeController = null;

    const scheduleNextPoll = () => {
      if (cancelled) return;
      timer = window.setTimeout(runVersionCheck, VERSION_POLL_INTERVAL_MS);
    };

    const runVersionCheck = async () => {
      if (cancelled) return;
      if (activeController) activeController.abort();
      const controller = new AbortController();
      activeController = controller;
      const headers = { "Cache-Control": "no-cache" };
      if (versionEtagRef.current) {
        headers["If-None-Match"] = versionEtagRef.current;
      }

      try {
        const response = await fetch(`${API}/api/version`, {
          signal: controller.signal,
          cache: "no-store",
          headers,
        });
        if (response.status === 304) return;
        if (!response.ok) throw new Error(`Server returned ${response.status} while loading /api/version`);

        const etag = String(response.headers.get("etag") || "").trim();
        if (etag) {
          versionEtagRef.current = etag;
        }

        const res = await response.json();
        if (cancelled) return;

        const buildId = String(res?.build_id || "").trim();
        const resolvedDataVersion = String(res?.data_version || buildId || "").trim();
        if (resolvedDataVersion) {
          setDataVersion(resolvedDataVersion);
        }
        if (!buildId) return;

        setBuildLabel(buildId.slice(0, 12));

        const previousBuildId = safeReadStorage(BUILD_STORAGE_KEY);
        const url = new URL(window.location.href);
        const urlBuildId = String(url.searchParams.get(BUILD_QUERY_PARAM) || "").trim();

        // If the currently loaded HTML build is stale (or we previously saw a
        // different build), force one cache-busting navigation to the latest build.
        const pageIsStale = Boolean(INDEX_BUILD_ID && INDEX_BUILD_ID !== buildId);
        const seenBuildChange = Boolean(previousBuildId && previousBuildId !== buildId);
        if ((pageIsStale || seenBuildChange) && urlBuildId !== buildId) {
          url.searchParams.set(BUILD_QUERY_PARAM, buildId);
          window.location.replace(url.toString());
          return;
        }

        if (urlBuildId && urlBuildId !== buildId) {
          url.searchParams.set(BUILD_QUERY_PARAM, buildId);
          window.history.replaceState({}, "", url.toString());
        }

        safeWriteStorage(BUILD_STORAGE_KEY, buildId);
      } catch (err) {
        if (err?.name === "AbortError" || cancelled) return;
        console.warn("Version check failed:", err);
      } finally {
        if (activeController === controller) {
          activeController = null;
        }
        scheduleNextPoll();
      }
    };

    runVersionCheck();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED) return undefined;
    let mounted = true;
    let unsubscribe = null;

    const setupAuth = async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        if (!mounted) return;
        setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to initialize account sync.")}`);
        setAuthReady(true);
        return;
      }

      if (!mounted || !client) {
        if (mounted) setAuthReady(true);
        return;
      }

      const { data: authState } = client.auth.onAuthStateChange((_event, session) => {
        setAuthUser(session?.user || null);
        setCloudReadyForSave(false);
        if (!session?.user) {
          setCloudStatus("");
        }
      });
      unsubscribe = () => authState?.subscription?.unsubscribe();

      const { data, error } = await client.auth.getSession();
      if (!mounted) return;
      if (error) {
        setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to restore session.")}`);
      } else if (!data?.session) {
        setAuthStatus("Sign in to sync your presets and watchlist across devices.");
      }
      setAuthUser(data?.session?.user || null);
      setAuthReady(true);
    };

    setupAuth().catch(error => {
      if (!mounted) return;
      setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to initialize account sync.")}`);
      setAuthReady(true);
    });

    return () => {
      mounted = false;
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED || !authReady) return undefined;
    if (!authUser?.id) {
      setCloudReadyForSave(false);
      return undefined;
    }

    let cancelled = false;
    setCloudStatus("Syncing account settings...");
    setCloudReadyForSave(false);

    const loadCloudPreferences = async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        if (cancelled) return;
        setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unable to initialize account settings.")}`);
        return;
      }
      if (!client || cancelled) return;

      const { data, error } = await client
        .from(SUPABASE_PREFS_TABLE)
        .select("preferences")
        .eq("user_id", authUser.id)
        .maybeSingle();

      if (cancelled) return;
      if (error) {
        setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unable to load account settings.")}`);
        return;
      }

      if (data?.preferences) {
        const normalized = normalizeCloudPreferences(data.preferences);
        setPresets(normalized.calculatorPresets);
        setWatchlist(normalized.playerWatchlist);
        setCloudStatus("Loaded saved account settings.");
        setCloudReadyForSave(true);
        return;
      }

      const seedPayload = buildCloudPreferencesPayload({
        calculatorPresets: presetsRef.current,
        playerWatchlist: watchlistRef.current,
      });

      const { error: upsertError } = await client
        .from(SUPABASE_PREFS_TABLE)
        .upsert(
          {
            user_id: authUser.id,
            preferences: seedPayload,
          },
          { onConflict: "user_id" }
        );

      if (cancelled) return;
      if (upsertError) {
        setCloudStatus(`Cloud sync error: ${formatAuthError(upsertError, "Unable to initialize account settings.")}`);
        return;
      }

      setCloudStatus("Cloud sync enabled.");
      setCloudReadyForSave(true);
    };

    loadCloudPreferences().catch(error => {
      if (cancelled) return;
      setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unexpected sync failure.")}`);
    });

    return () => {
      cancelled = true;
    };
  }, [authReady, authUser?.id]);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED || !authUser?.id || !cloudReadyForSave) return undefined;

    const timer = window.setTimeout(async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        setCloudStatus(`Cloud save error: ${formatAuthError(error, "Unable to initialize cloud sync.")}`);
        return;
      }
      if (!client) return;

      const payload = buildCloudPreferencesPayload({
        calculatorPresets: presets,
        playerWatchlist: watchlist,
      });
      const { error } = await client
        .from(SUPABASE_PREFS_TABLE)
        .upsert(
          {
            user_id: authUser.id,
            preferences: payload,
          },
          { onConflict: "user_id" }
        );
      if (error) {
        setCloudStatus(`Cloud save error: ${formatAuthError(error, "Unable to save settings.")}`);
        return;
      }
      setCloudStatus("Saved account settings.");
    }, CLOUD_SYNC_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [authUser?.id, cloudReadyForSave, presets, watchlist]);

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

  const signIn = useCallback(async (email, password) => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign in failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await loadSupabaseClient();
      if (!client) return;
      const { error } = await client.auth.signInWithPassword({
        email: normalizedEmail,
        password: normalizedPassword,
      });
      if (error) {
        setAuthStatus(`Sign in failed: ${formatAuthError(error, "Invalid login.")}`);
        return;
      }
      setAuthStatus("Signed in.");
    } catch (error) {
      setAuthStatus(`Sign in failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

  const signUp = useCallback(async (email, password) => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign up failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await loadSupabaseClient();
      if (!client) return;
      const { data, error } = await client.auth.signUp({
        email: normalizedEmail,
        password: normalizedPassword,
      });
      if (error) {
        setAuthStatus(`Sign up failed: ${formatAuthError(error, "Unable to create account.")}`);
        return;
      }
      if (data?.session) {
        setAuthStatus("Account created. You are signed in.");
        return;
      }
      setAuthStatus("Account created. Check your email to confirm your login.");
    } catch (error) {
      setAuthStatus(`Sign up failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

  const signOut = useCallback(async () => {
    if (!AUTH_SYNC_ENABLED) return;
    try {
      const client = await loadSupabaseClient();
      if (!client) return;
      const { error } = await client.auth.signOut();
      if (error) {
        setAuthStatus(`Sign out failed: ${formatAuthError(error, "Unable to sign out.")}`);
        return;
      }
      setAuthStatus("Signed out.");
      setCloudStatus("");
    } catch (error) {
      setAuthStatus(`Sign out failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

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
            <ProjectionsExplorer
              apiBase={API}
              meta={meta}
              dataVersion={dataVersion}
              watchlist={watchlist}
              setWatchlist={setWatchlist}
            />
          )}
          {section === "calculator" && meta && (
            <DynastyCalculator
              apiBase={API}
              meta={meta}
              presets={presets}
              setPresets={setPresets}
              watchlist={watchlist}
              setWatchlist={setWatchlist}
            />
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
