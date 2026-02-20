import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cancelCalculationJob, runCalculationJob } from "./calculation_jobs.js";
import { DynastyCalculatorResults } from "./dynasty_calculator_results.jsx";
import { DynastyCalculatorSidebar } from "./dynasty_calculator_sidebar.jsx";
import { normalizeCalculatorRunSettingsInput } from "./calculator_submit.js";
import { parseDownloadFilename } from "./download_filename.js";
import { downloadBlob, triggerBlobDownload } from "./download_helpers.js";
import { RANK_COMPARE_ACTIONS, WATCHLIST_ACTIONS, rankCompareReducer, watchlistReducer } from "./rank_state_reducers.js";
import {
  CALC_LINK_QUERY_PARAM,
  buildWatchlistCsv,
  calculationRowExplainKey,
  decodeCalculatorSettings,
  encodeCalculatorSettings,
  mergeKnownCalculatorSettings,
  stablePlayerKeyFromRow,
} from "./app_state_storage.js";
import {
  CALC_SEARCH_DEBOUNCE_MS,
  HITTER_SLOT_FIELDS,
  POINTS_SCORING_FIELDS,
  POINTS_RESULT_COLUMN_LABELS,
  POINTS_RESULT_SUMMARY_COLS,
  PITCHER_SLOT_FIELDS,
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  buildCalculatorPayload,
  buildDefaultCalculatorSettings,
  coerceBooleanSetting,
  resolvePointsScoringDefaults,
  resolvePointsSlotDefaults,
  resolveRotoCategoryDefaults,
  resolveRotoSelectedStatColumns,
  resolveRotoSlotDefaults,
} from "./dynasty_calculator_config.js";
import { useDebouncedValue } from "./request_helpers.js";

export function DynastyCalculator({ apiBase, meta, presets, setPresets, watchlist, setWatchlist }) {
  const API = String(apiBase || "").trim();
  const [settings, setSettings] = useState(() => buildDefaultCalculatorSettings(meta));
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [sortCol, setSortCol] = useState("DynastyValue");
  const [sortDir, setSortDir] = useState("desc");
  const [searchInput, setSearchInput] = useState("");
  const debouncedRankSearch = useDebouncedValue(searchInput, CALC_SEARCH_DEBOUNCE_MS);
  const [posFilter, setPosFilter] = useState("");
  const [presetName, setPresetName] = useState("");
  const [selectedPresetName, setSelectedPresetName] = useState("");
  const [selectedExplainKey, setSelectedExplainKey] = useState("");
  const [selectedExplainYear, setSelectedExplainYear] = useState("");
  const [hiddenRankCols, setHiddenRankCols] = useState({});
  const [pinRankKeyColumns, setPinRankKeyColumns] = useState(true);
  const [rankWatchlistOnly, setRankWatchlistOnly] = useState(false);
  const [rankCompareRowsByKey, setRankCompareRowsByKey] = useState({});
  const calcRequestSeqRef = useRef(0);
  const calcAbortControllerRef = useRef(null);
  const calcActiveJobIdRef = useRef("");
  const rankTableScrollRef = useRef(null);
  const rankScrollRafRef = useRef(0);
  const rankScrollPendingTopRef = useRef(0);
  const [rankScrollTop, setRankScrollTop] = useState(0);
  const [rankViewportHeight, setRankViewportHeight] = useState(480);
  const availableYears = useMemo(
    () => (meta.years || []).map(Number).filter(Number.isFinite),
    [meta.years]
  );
  const rotoSlotDefaults = useMemo(() => resolveRotoSlotDefaults(meta), [meta]);
  const rotoCategoryDefaults = useMemo(() => resolveRotoCategoryDefaults(), []);
  const pointsSlotDefaults = useMemo(() => resolvePointsSlotDefaults(meta), [meta]);
  const pointsScoringDefaults = useMemo(() => resolvePointsScoringDefaults(meta), [meta]);
  const validationResult = useMemo(
    () => buildCalculatorPayload(settings, availableYears, meta),
    [settings, availableYears, meta]
  );
  const validationError = validationResult.error || "";
  const validationWarning = validationResult.warning || "";

  useEffect(() => {
    if (availableYears.length === 0) return;
    const currentYear = Number(settings.start_year);
    if (!availableYears.includes(currentYear)) {
      setSettings(prev => ({ ...prev, start_year: availableYears[0] }));
    }
  }, [availableYears, settings.start_year]);

  useEffect(() => {
    if (rankWatchlistOnly && Object.keys(watchlist).length === 0) {
      setRankWatchlistOnly(false);
    }
  }, [rankWatchlistOnly, watchlist]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const encoded = String(params.get(CALC_LINK_QUERY_PARAM) || "").trim();
    if (!encoded) return;
    const parsed = decodeCalculatorSettings(encoded);
    if (!parsed) return;
    setSettings(current => mergeKnownCalculatorSettings(current, parsed));
    setStatus("Loaded calculator settings from share link.");
  }, []);

  useEffect(() => {
    return () => {
      calcRequestSeqRef.current += 1;
      const activeJobId = String(calcActiveJobIdRef.current || "").trim();
      if (activeJobId) {
        void cancelCalculationJob(API, activeJobId);
        calcActiveJobIdRef.current = "";
      }
      if (calcAbortControllerRef.current) {
        calcAbortControllerRef.current.abort();
        calcAbortControllerRef.current = null;
      }
      if (rankScrollRafRef.current) {
        window.cancelAnimationFrame(rankScrollRafRef.current);
        rankScrollRafRef.current = 0;
      }
    };
  }, []);

  function update(key, val) {
    setSettings(s => ({ ...s, [key]: val }));
  }

  function applyScoringSetup(nextMode) {
    setSettings(curr => {
      const slotDefaults = nextMode === "points" ? pointsSlotDefaults : rotoSlotDefaults;
      return {
        ...curr,
        scoring_mode: nextMode,
        ...slotDefaults,
      };
    });
  }

  function resetPointsScoringDefaults() {
    setSettings(curr => ({ ...curr, ...pointsScoringDefaults }));
  }

  function resetRotoCategoryDefaults() {
    setSettings(curr => ({ ...curr, ...rotoCategoryDefaults }));
  }

  function reapplySetupDefaults() {
    setSettings(curr => (
      curr.scoring_mode === "points"
        ? { ...curr, ...pointsSlotDefaults, ...pointsScoringDefaults }
        : { ...curr, ...rotoSlotDefaults }
    ));
  }

  function buildQuickStartSettings(mode) {
    const availableStartYear = availableYears.length > 0
      ? availableYears[0]
      : Number(meta?.years?.[0] ?? 2026);
    const currentStartYear = Number(settings.start_year);
    const startYear = availableYears.includes(currentStartYear) ? currentStartYear : availableStartYear;
    const guardrails = meta?.calculator_guardrails || {};
    const defaultIr = Number(guardrails.default_ir_slots);
    const defaultMinors = Number(guardrails.default_minors_slots);
    const commonBase = {
      ...settings,
      teams: 12,
      horizon: 20,
      discount: 0.94,
      bench: 6,
      minors: Number.isInteger(defaultMinors) && defaultMinors >= 0 ? defaultMinors : 0,
      ir: Number.isInteger(defaultIr) && defaultIr >= 0 ? defaultIr : 0,
      ip_min: 0,
      ip_max: "",
      two_way: "sum",
      start_year: startYear,
      recent_projections: 3,
      sims: 300,
    };

    if (mode === "points") {
      return {
        ...commonBase,
        scoring_mode: "points",
        ...pointsSlotDefaults,
        ...pointsScoringDefaults,
      };
    }

    return {
      ...commonBase,
      scoring_mode: "roto",
      ...rotoSlotDefaults,
      ...rotoCategoryDefaults,
    };
  }

  function applyQuickStartAndRun(mode) {
    const nextSettings = buildQuickStartSettings(mode);
    setSettings(nextSettings);
    setSortCol("DynastyValue");
    setSortDir("desc");
    setStatus(`Applied quick start (${mode === "points" ? "12-team points" : "12-team 5x5 roto"}).`);
    run(nextSettings);
  }

  function savePreset() {
    const name = String(presetName || "").trim();
    if (!name) {
      setStatus("Error: Enter a preset name before saving.");
      return;
    }
    setPresets(current => ({ ...current, [name]: settings }));
    setStatus(`Saved preset '${name}'.`);
  }

  function loadPreset(name) {
    const preset = presets[name];
    if (!preset || typeof preset !== "object") {
      setStatus(`Error: Preset '${name}' was not found.`);
      return;
    }
    setSettings(current => mergeKnownCalculatorSettings(current, preset));
    setPresetName(name);
    setSelectedPresetName(name);
    setStatus(`Loaded preset '${name}'.`);
  }

  function deletePreset(name) {
    setPresets(current => {
      const next = { ...current };
      delete next[name];
      return next;
    });
    setSelectedPresetName(current => (current === name ? "" : current));
    setStatus(`Deleted preset '${name}'.`);
  }

  async function copyShareLink() {
    const encoded = encodeCalculatorSettings(settings);
    if (!encoded) {
      setStatus("Error: Unable to encode settings for sharing.");
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set(CALC_LINK_QUERY_PARAM, encoded);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url.toString());
      } else {
        throw new Error("Clipboard API unavailable");
      }
      setStatus("Copied share link to clipboard.");
      window.history.replaceState({}, "", url.toString());
    } catch {
      window.prompt("Copy calculator link:", url.toString());
      setStatus("Share link is ready.");
    }
  }

  async function exportRankings(format) {
    const payload = buildCalculatorPayload(settings, availableYears, meta);
    if (payload.error || !payload.payload) {
      setStatus(`Error: ${payload.error || "Invalid settings"}`);
      return;
    }

    try {
      setStatus("Preparing export...");
      const response = await fetch(`${API}/api/calculate/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload.payload,
          format,
          include_explanations: format === "xlsx",
          export_columns: visibleRankCols,
        }),
      });
      if (!response.ok) {
        const parsed = await readResponsePayload(response);
        throw new Error(formatApiError(response.status, parsed.payload, parsed.rawText));
      }
      const blob = await response.blob();
      const fallback = `dynasty-rankings.${format}`;
      const filename = parseDownloadFilename(response.headers.get("content-disposition"), fallback);
      triggerBlobDownload(filename, blob);
      setStatus(`Exported ${filename}`);
    } catch (err) {
      setStatus(`Error: ${err.message || "Failed to export rankings"}`);
    }
  }

  function run(runSettings = settings) {
    const normalizedSettings = normalizeCalculatorRunSettingsInput(runSettings, settings);
    const payload = buildCalculatorPayload(normalizedSettings, availableYears, meta);
    if (payload.error || !payload.payload) {
      setStatus(`Error: ${payload.error || "Invalid settings"}`);
      return;
    }

    const requestSeq = calcRequestSeqRef.current + 1;
    calcRequestSeqRef.current = requestSeq;
    const previousJobId = String(calcActiveJobIdRef.current || "").trim();
    if (previousJobId) {
      void cancelCalculationJob(API, previousJobId);
      calcActiveJobIdRef.current = "";
    }
    if (calcAbortControllerRef.current) {
      calcAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    calcAbortControllerRef.current = controller;
    setLoading(true);
    setStatus("Submitting simulation job...");
    void runCalculationJob({
      apiBase: API,
      payload: payload.payload,
      controller,
      requestSeq,
      requestSeqRef: calcRequestSeqRef,
      activeJobIdRef: calcActiveJobIdRef,
      timeoutSeconds: Number(meta?.calculator_guardrails?.job_timeout_seconds),
      onStatus: nextStatus => setStatus(nextStatus),
      onCompleted: result => {
        setResults(result);
        setLoading(false);
        setStatus(`Done - ${result.total} players ranked`);
      },
      onCancelled: () => {
        setLoading(false);
        setStatus("Calculation cancelled.");
      },
      onError: message => {
        setLoading(false);
        setStatus(`Error: ${message}`);
      },
    }).finally(() => {
      if (calcAbortControllerRef.current === controller) {
        calcAbortControllerRef.current = null;
      }
    });
  }

  const sortedAll = useMemo(() => {
    if (!results) return [];
    const source = Array.isArray(results.data) ? results.data : [];
    if (!sortCol) return source;
    return [...source].sort((a, b) => {
      let av = a[sortCol], bv = b[sortCol];
      if (sortCol === "Player" || sortCol === "Team" || sortCol === "Pos") {
        const avText = String(av ?? "").trim();
        const bvText = String(bv ?? "").trim();
        if (!avText && !bvText) return 0;
        if (!avText) return 1;
        if (!bvText) return -1;
        return sortDir === "asc" ? avText.localeCompare(bvText) : bvText.localeCompare(avText);
      }
      const avNum = Number(av);
      const bvNum = Number(bv);
      const safeAv = Number.isFinite(avNum) ? avNum : -Infinity;
      const safeBv = Number.isFinite(bvNum) ? bvNum : -Infinity;
      return sortDir === "asc" ? safeAv - safeBv : safeBv - safeAv;
    });
  }, [results, sortCol, sortDir]);

  function isRowWatched(row) {
    const key = stablePlayerKeyFromRow(row);
    return Boolean(watchlist[key]);
  }

  const rankedFiltered = useMemo(() => {
    const q = debouncedRankSearch.trim().toLowerCase();
    const posNeedle = posFilter.trim().toUpperCase();
    return sortedAll
      .map((row, idx) => ({ row, rank: idx + 1 }))
      .filter(({ row }) => {
        if (q && !(row.Player || "").toLowerCase().includes(q)) return false;
        if (posNeedle && !(row.Pos || "").toUpperCase().includes(posNeedle)) return false;
        if (rankWatchlistOnly && !isRowWatched(row)) return false;
        return true;
      });
  }, [sortedAll, debouncedRankSearch, posFilter, rankWatchlistOnly, watchlist]);

  function handleSort(col) {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir(col === "Player" || col === "Team" || col === "Pos" ? "asc" : "desc"); }
  }

  function toggleRankColumn(col) {
    if (requiredRankCols.has(col)) return;
    setHiddenRankCols(current => {
      const next = { ...current };
      if (next[col]) delete next[col];
      else next[col] = true;
      return next;
    });
  }

  function showAllRankColumns() {
    setHiddenRankCols({});
  }

  function clearRankFilters() {
    setSearchInput("");
    setPosFilter("");
    setRankWatchlistOnly(false);
  }

  function toggleRowWatch(row) {
    setWatchlist(current => watchlistReducer(current, {
      type: WATCHLIST_ACTIONS.TOGGLE_ROW,
      row,
    }));
  }

  function clearWatchlist() {
    setWatchlist(current => watchlistReducer(current, { type: WATCHLIST_ACTIONS.CLEAR }));
  }

  function exportWatchlistCsv() {
    const csv = buildWatchlistCsv(watchlist);
    downloadBlob("player-watchlist.csv", csv, "text/csv;charset=utf-8");
  }

  function toggleRankCompareRow(row) {
    setRankCompareRowsByKey(current => rankCompareReducer(current, {
      type: RANK_COMPARE_ACTIONS.TOGGLE_ROW,
      row,
    }));
  }

  function removeRankCompareRow(key) {
    setRankCompareRowsByKey(current => rankCompareReducer(current, {
      type: RANK_COMPARE_ACTIONS.REMOVE_KEY,
      key,
    }));
  }

  function clearRankCompareRows() {
    setRankCompareRowsByKey(current => rankCompareReducer(current, {
      type: RANK_COMPARE_ACTIONS.CLEAR,
    }));
  }

  // Determine columns to show
  const baseCols = ["Player", "DynastyValue", "Age", "Team", "Pos"];
  const yearCols = results
    ? Object.keys(results.data[0] || {})
      .filter(c => c.startsWith("Value_"))
      .sort((a, b) => {
        const av = Number(a.replace("Value_", ""));
        const bv = Number(b.replace("Value_", ""));
        if (Number.isFinite(av) && Number.isFinite(bv)) return av - bv;
        return a.localeCompare(b);
      })
    : [];
  const isPointsMode = settings.scoring_mode === "points";
  const selectedRotoHitCategoryCount = ROTO_HITTER_CATEGORY_FIELDS.filter(
    field => coerceBooleanSetting(settings[field.key], field.defaultValue)
  ).length;
  const selectedRotoPitchCategoryCount = ROTO_PITCHER_CATEGORY_FIELDS.filter(
    field => coerceBooleanSetting(settings[field.key], field.defaultValue)
  ).length;
  const resultSettings = (results && results.settings && typeof results.settings === "object")
    ? results.settings
    : settings;
  const resultScoringMode = String(resultSettings.scoring_mode || settings.scoring_mode || "roto")
    .trim()
    .toLowerCase() || "roto";
  const selectedRotoStatColsForResults = useMemo(() => {
    if (resultScoringMode !== "roto") return [];
    const requested = resolveRotoSelectedStatColumns(resultSettings);
    const firstResultRow = results?.data?.[0];
    if (!firstResultRow || typeof firstResultRow !== "object") return [];
    const available = new Set(Object.keys(firstResultRow));
    return requested.filter(col => available.has(col));
  }, [resultScoringMode, resultSettings, results]);
  const selectedPointsSummaryColsForResults = useMemo(() => {
    if (resultScoringMode !== "points") return [];
    const firstResultRow = results?.data?.[0];
    if (!firstResultRow || typeof firstResultRow !== "object") return [];
    const available = new Set(Object.keys(firstResultRow));
    return POINTS_RESULT_SUMMARY_COLS.filter(col => available.has(col));
  }, [resultScoringMode, results]);
  const displayCols = [
    ...baseCols,
    ...selectedRotoStatColsForResults,
    ...selectedPointsSummaryColsForResults,
    ...yearCols,
  ];
  const columnLabels = useMemo(() => {
    const labels = {};
    displayCols.forEach(col => {
      labels[col] = POINTS_RESULT_COLUMN_LABELS[col] || (col.startsWith("Value_") ? col.replace("Value_", "") : col);
    });
    return labels;
  }, [displayCols]);
  const requiredRankCols = useMemo(() => new Set(["Player", "DynastyValue"]), []);
  const visibleRankCols = useMemo(
    () => displayCols.filter(col => !hiddenRankCols[col]),
    [displayCols, hiddenRankCols]
  );
  const virtualRowHeight = 38;
  const virtualOverscan = 8;
  const totalRankRows = rankedFiltered.length;
  const virtualStartIndex = Math.max(0, Math.floor(rankScrollTop / virtualRowHeight) - virtualOverscan);
  const virtualVisibleCount = Math.ceil(rankViewportHeight / virtualRowHeight) + virtualOverscan * 2;
  const virtualEndIndex = Math.min(totalRankRows, virtualStartIndex + virtualVisibleCount);
  const virtualRows = rankedFiltered.slice(virtualStartIndex, virtualEndIndex);
  const virtualTopPad = virtualStartIndex * virtualRowHeight;
  const virtualBottomPad = Math.max(0, (totalRankRows - virtualEndIndex) * virtualRowHeight);
  const explanationMap = useMemo(() => (
    results && results.explanations && typeof results.explanations === "object"
      ? results.explanations
      : {}
  ), [results]);
  const activeExplanation = useMemo(() => {
    if (!selectedExplainKey) return null;
    return explanationMap[selectedExplainKey] || null;
  }, [explanationMap, selectedExplainKey]);
  const hittersPerTeam = useMemo(() => HITTER_SLOT_FIELDS.reduce((sum, slot) => {
    const value = Number(settings[slot.key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0), [settings]);
  const pitchersPerTeam = useMemo(() => PITCHER_SLOT_FIELDS.reduce((sum, slot) => {
    const value = Number(settings[slot.key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0), [settings]);
  const benchPerTeam = Number.isFinite(Number(settings.bench)) ? Number(settings.bench) : 0;
  const minorsPerTeam = Number.isFinite(Number(settings.minors)) ? Number(settings.minors) : 0;
  const reservePerTeam = benchPerTeam + minorsPerTeam;
  const totalPlayersPerTeam = hittersPerTeam + pitchersPerTeam + reservePerTeam;
  const pointRulesCount = POINTS_SCORING_FIELDS.length;
  const watchlistCount = Object.keys(watchlist).length;
  const rankCompareRows = useMemo(
    () => Object.values(rankCompareRowsByKey || {}).filter(Boolean),
    [rankCompareRowsByKey]
  );
  const compareYearCols = yearCols.slice(0, 6);
  const hasRankFilters = Boolean(searchInput.trim() || posFilter.trim() || rankWatchlistOnly);
  const rankSearchIsDebouncing = searchInput !== debouncedRankSearch;
  const statusIsError = Boolean(validationError) || String(status || "").startsWith("Error");
  const sidebarState = {
    hittersPerTeam,
    isPointsMode,
    loading,
    pointRulesCount,
    presetName,
    pitchersPerTeam,
    reservePerTeam,
    selectedPresetName,
    selectedRotoHitCategoryCount,
    selectedRotoPitchCategoryCount,
    status,
    statusIsError,
    totalPlayersPerTeam,
    validationError,
    validationWarning,
  };
  const sidebarActions = {
    applyQuickStartAndRun,
    applyScoringSetup,
    copyShareLink,
    deletePreset,
    loadPreset,
    reapplySetupDefaults,
    resetPointsScoringDefaults,
    resetRotoCategoryDefaults,
    run,
    savePreset,
    setPresetName,
    setSelectedPresetName,
    update,
  };
  const resultsState = {
    activeExplanation,
    compareYearCols,
    displayCols,
    hasRankFilters,
    hiddenRankCols,
    columnLabels,
    pinRankKeyColumns,
    posFilter,
    rankCompareRows,
    rankCompareRowsByKey,
    rankedFiltered,
    rankSearchIsDebouncing,
    rankWatchlistOnly,
    requiredRankCols,
    searchInput,
    selectedExplainKey,
    selectedExplainYear,
    sortCol,
    sortDir,
    sortedAll,
    virtualBottomPad,
    virtualRows,
    virtualStartIndex,
    virtualTopPad,
    visibleRankCols,
    watchlist,
    watchlistCount,
  };
  const resultsActions = {
    clearRankCompareRows,
    clearRankFilters,
    clearWatchlist,
    exportRankings,
    exportWatchlistCsv,
    handleSort,
    removeRankCompareRow,
    setPinRankKeyColumns,
    setPosFilter,
    setRankWatchlistOnly,
    setSearchInput,
    setSelectedExplainKey,
    setSelectedExplainYear,
    showAllRankColumns,
    toggleRankColumn,
    toggleRankCompareRow,
    toggleRowWatch,
  };

  const handleRankScroll = useCallback(event => {
    rankScrollPendingTopRef.current = event.currentTarget.scrollTop;
    if (rankScrollRafRef.current) return;
    rankScrollRafRef.current = window.requestAnimationFrame(() => {
      rankScrollRafRef.current = 0;
      setRankScrollTop(rankScrollPendingTopRef.current);
    });
  }, []);
  const resultsRefs = {
    handleRankScroll,
    rankTableScrollRef,
  };

  useEffect(() => {
    if (!results || !Array.isArray(results.data) || results.data.length === 0) {
      setSelectedExplainKey("");
      setSelectedExplainYear("");
      return;
    }
    const firstKey = calculationRowExplainKey(results.data[0]);
    setSelectedExplainKey(current => (current && explanationMap[current] ? current : firstKey));
  }, [results, explanationMap]);

  useEffect(() => {
    setSelectedExplainYear("");
  }, [selectedExplainKey]);

  useEffect(() => {
    setRankCompareRowsByKey(current => rankCompareReducer(current, {
      type: RANK_COMPARE_ACTIONS.SYNC_ROWS,
      rows: sortedAll,
    }));
  }, [sortedAll]);

  useEffect(() => {
    setHiddenRankCols(current => {
      const next = {};
      displayCols.forEach(col => {
        if (current[col] && !requiredRankCols.has(col)) next[col] = true;
      });
      return next;
    });
  }, [displayCols, requiredRankCols]);

  useEffect(() => {
    const tableEl = rankTableScrollRef.current;
    if (!tableEl) return;
    const measure = () => setRankViewportHeight(Math.max(240, tableEl.clientHeight || 480));
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [results]);

  useEffect(() => {
    const tableEl = rankTableScrollRef.current;
    if (tableEl) tableEl.scrollTop = 0;
    rankScrollPendingTopRef.current = 0;
    setRankScrollTop(0);
  }, [debouncedRankSearch, posFilter, rankWatchlistOnly, sortCol, sortDir, results, visibleRankCols.length]);

  return (
    <div className="fade-up fade-up-1">
      <div className="calc-layout">
        <DynastyCalculatorSidebar
          meta={meta}
          presets={presets}
          settings={settings}
          state={sidebarState}
          actions={sidebarActions}
        />
        <div>
          <DynastyCalculatorResults
            results={results}
            state={resultsState}
            refs={resultsRefs}
            actions={resultsActions}
          />
        </div>
      </div>
    </div>
  );
}
