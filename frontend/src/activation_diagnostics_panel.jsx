import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  clearAnalyticsEventBuffer,
  downloadAnalyticsEventCsv,
  readAnalyticsEventBuffer,
  summarizeActivationFunnel,
} from "./analytics.js";

const ACTIVATION_DIAGNOSTICS_QUERY_PARAM = "activation_debug";
const DEFAULT_READOUT_CURRENT_PATH = "tmp/activation_current.csv";
const DEFAULT_READOUT_BASELINE_PATH = "tmp/activation_baseline.csv";
const DEFAULT_CHECKPOINT_CURRENT_24H_PATH = "tmp/activation_current_24h.csv";
const DEFAULT_CHECKPOINT_BASELINE_24H_PATH = "tmp/activation_baseline_24h.csv";
const DEFAULT_CHECKPOINT_CURRENT_48H_PATH = "tmp/activation_current_48h.csv";
const DEFAULT_CHECKPOINT_BASELINE_48H_PATH = "tmp/activation_baseline_48h.csv";
const DEFAULT_READOUT_OWNER = "Analytics Team";
const DEFAULT_OPS_REFRESH_INTERVAL_MS = 30000;
const FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function formatPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/a";
  return `${numeric.toFixed(1)}%`;
}

function formatDuration(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return "n/a";
  if (numeric < 1000) return `${Math.round(numeric)} ms`;
  const seconds = numeric / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const remSeconds = seconds - (minutes * 60);
  return `${minutes}m ${remSeconds.toFixed(1)}s`;
}

function formatTimestamp(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return "n/a";
  return new Date(numeric).toLocaleString();
}

function formatSecondsAsDuration(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return "n/a";
  return formatDuration(numeric * 1000);
}

function resolveReportDate(now = new Date()) {
  const dateValue = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(dateValue.getTime())) {
    return new Date().toISOString().slice(0, 10);
  }
  return dateValue.toISOString().slice(0, 10);
}

function addDaysToIsoDate(dateText, days = 0) {
  const normalizedDate = String(dateText || "").trim();
  if (!normalizedDate) return resolveReportDate();
  const parsed = new Date(`${normalizedDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return resolveReportDate();
  const next = new Date(parsed.getTime());
  next.setUTCDate(next.getUTCDate() + Math.trunc(Number(days) || 0));
  return next.toISOString().slice(0, 10);
}

function describeDatePresetOffset(offsetDays) {
  const offset = Math.trunc(Number(offsetDays) || 0);
  if (offset === 0) return "today";
  if (offset === 1) return "tomorrow";
  if (offset === -1) return "yesterday";
  const absOffset = Math.abs(offset);
  const suffix = absOffset === 1 ? "day" : "days";
  return `${offset > 0 ? "+" : ""}${offset} ${suffix}`;
}

function shellQuoted(value) {
  const text = String(value || "").trim();
  if (!text) return "''";
  return `'${text.replace(/'/g, "'\"'\"'")}'`;
}

function copyTextToClipboard(text) {
  const value = String(text || "").trim();
  if (!value) return Promise.resolve(false);
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(value).then(
      () => true,
      () => false
    );
  }
  return Promise.resolve(false);
}

async function fetchOpsSnapshotFromApi() {
  if (typeof fetch !== "function") return null;
  try {
    const response = await fetch("/api/ops", {
      method: "GET",
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) return null;
    const payload = await response.json();
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

export function buildActivationReadoutCommand({
  currentPath = DEFAULT_READOUT_CURRENT_PATH,
  baselinePath = DEFAULT_READOUT_BASELINE_PATH,
  reportDate = "",
  owner = DEFAULT_READOUT_OWNER,
} = {}) {
  const resolvedDate = String(reportDate || "").trim() || resolveReportDate();
  const resolvedCurrent = String(currentPath || "").trim() || DEFAULT_READOUT_CURRENT_PATH;
  const resolvedBaseline = String(baselinePath || "").trim() || DEFAULT_READOUT_BASELINE_PATH;
  const resolvedOwner = String(owner || "").trim() || DEFAULT_READOUT_OWNER;
  return [
    "scripts/run_activation_readout.sh",
    `--current ${shellQuoted(resolvedCurrent)}`,
    `--baseline ${shellQuoted(resolvedBaseline)}`,
    `--date ${shellQuoted(resolvedDate)}`,
    `--owner ${shellQuoted(resolvedOwner)}`,
  ].join(" ");
}

export function buildActivationCheckpointReadoutCommand({
  current24hPath = DEFAULT_CHECKPOINT_CURRENT_24H_PATH,
  baseline24hPath = DEFAULT_CHECKPOINT_BASELINE_24H_PATH,
  current48hPath = DEFAULT_CHECKPOINT_CURRENT_48H_PATH,
  baseline48hPath = DEFAULT_CHECKPOINT_BASELINE_48H_PATH,
  date24h = "",
  date48h = "",
  owner = DEFAULT_READOUT_OWNER,
} = {}) {
  const resolvedDate24h = String(date24h || "").trim() || resolveReportDate();
  const resolvedDate48h = String(date48h || "").trim() || addDaysToIsoDate(resolvedDate24h, 1);
  const resolvedCurrent24h = String(current24hPath || "").trim() || DEFAULT_CHECKPOINT_CURRENT_24H_PATH;
  const resolvedBaseline24h = String(baseline24hPath || "").trim() || DEFAULT_CHECKPOINT_BASELINE_24H_PATH;
  const resolvedCurrent48h = String(current48hPath || "").trim() || DEFAULT_CHECKPOINT_CURRENT_48H_PATH;
  const resolvedBaseline48h = String(baseline48hPath || "").trim() || DEFAULT_CHECKPOINT_BASELINE_48H_PATH;
  const resolvedOwner = String(owner || "").trim() || DEFAULT_READOUT_OWNER;
  return [
    "scripts/run_activation_readout_checkpoints.sh",
    `--current-24h ${shellQuoted(resolvedCurrent24h)}`,
    `--baseline-24h ${shellQuoted(resolvedBaseline24h)}`,
    `--date-24h ${shellQuoted(resolvedDate24h)}`,
    `--current-48h ${shellQuoted(resolvedCurrent48h)}`,
    `--baseline-48h ${shellQuoted(resolvedBaseline48h)}`,
    `--date-48h ${shellQuoted(resolvedDate48h)}`,
    `--owner ${shellQuoted(resolvedOwner)}`,
  ].join(" ");
}

export function resolveActivationDatePreset({
  anchorDate = "",
  offsetDays = 0,
} = {}) {
  const baseDate = String(anchorDate || "").trim() || resolveReportDate();
  const readoutDate = addDaysToIsoDate(baseDate, offsetDays);
  return {
    readoutDate,
    date24h: readoutDate,
    date48h: addDaysToIsoDate(readoutDate, 1),
  };
}

export function resolveActivationDiagnosticsPanelEnabled({
  envEnabled = false,
  locationSearch = "",
} = {}) {
  const resolvedEnvEnabled = envEnabled === true || String(envEnabled).trim() === "1";
  let queryEnabled = false;
  try {
    const params = new URLSearchParams(String(locationSearch || ""));
    const raw = String(params.get(ACTIVATION_DIAGNOSTICS_QUERY_PARAM) || "").trim().toLowerCase();
    queryEnabled = raw === "1" || raw === "true" || raw === "yes" || raw === "on";
  } catch {
    queryEnabled = false;
  }
  return resolvedEnvEnabled || queryEnabled;
}

export function ActivationDiagnosticsPanel({
  section,
  dataVersion,
  readEvents = readAnalyticsEventBuffer,
  summarize = summarizeActivationFunnel,
  clearEvents = clearAnalyticsEventBuffer,
  exportCsv = downloadAnalyticsEventCsv,
  fetchOpsSnapshot = fetchOpsSnapshotFromApi,
  opsRefreshIntervalMs = DEFAULT_OPS_REFRESH_INTERVAL_MS,
}) {
  const [refreshToken, setRefreshToken] = useState(0);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [commandCenterOpen, setCommandCenterOpen] = useState(false);
  const initialDates = useMemo(() => resolveActivationDatePreset(), []);
  const [readoutDate, setReadoutDate] = useState(initialDates.readoutDate);
  const [date24h, setDate24h] = useState(initialDates.date24h);
  const [date48h, setDate48h] = useState(initialDates.date48h);
  const [owner, setOwner] = useState(DEFAULT_READOUT_OWNER);
  const [readoutCurrentPath, setReadoutCurrentPath] = useState(DEFAULT_READOUT_CURRENT_PATH);
  const [readoutBaselinePath, setReadoutBaselinePath] = useState(DEFAULT_READOUT_BASELINE_PATH);
  const [current24hPath, setCurrent24hPath] = useState(DEFAULT_CHECKPOINT_CURRENT_24H_PATH);
  const [baseline24hPath, setBaseline24hPath] = useState(DEFAULT_CHECKPOINT_BASELINE_24H_PATH);
  const [current48hPath, setCurrent48hPath] = useState(DEFAULT_CHECKPOINT_CURRENT_48H_PATH);
  const [baseline48hPath, setBaseline48hPath] = useState(DEFAULT_CHECKPOINT_BASELINE_48H_PATH);
  const [statusMessage, setStatusMessage] = useState("");
  const [opsSnapshot, setOpsSnapshot] = useState(null);
  const [opsLoading, setOpsLoading] = useState(false);
  const [opsError, setOpsError] = useState("");
  const commandCenterRef = useRef(null);
  const previousFocusRef = useRef(null);
  const opsRequestTokenRef = useRef(0);

  const events = useMemo(
    () => readEvents(),
    [readEvents, refreshToken]
  );
  const summary = useMemo(
    () => summarize(events),
    [events, summarize]
  );
  const recentEvents = useMemo(
    () => events.slice(-10).reverse(),
    [events]
  );

  const eventWindow = summary?.window || {};
  const quickstart = summary?.quickstart || {};
  const lastEventAtLabel = formatTimestamp(eventWindow.last_event_at_ms);
  const queuePressure = opsSnapshot?.queues?.job_pressure || {};
  const rateLimitTotals = opsSnapshot?.queues?.rate_limit_activity?.totals || {};
  const queueUtilizationPct = formatPercent(Number(queuePressure.utilization_ratio) * 100);
  const queueActiveLabel = Number.isFinite(Number(queuePressure.capacity_total))
    ? `${Number(queuePressure.active_jobs || 0)} / ${Number(queuePressure.capacity_total || 0)}`
    : String(Number(queuePressure.active_jobs || 0));
  const opsTimestampLabel = formatTimestamp(Date.parse(String(opsSnapshot?.timestamp || "")));
  const queueAlert = Boolean(
    queuePressure?.alerts?.queue_wait_exceeds_request_timeout
    || queuePressure?.alerts?.runtime_exceeds_request_timeout
  );
  const readoutCommand = useMemo(
    () => buildActivationReadoutCommand({
      currentPath: readoutCurrentPath,
      baselinePath: readoutBaselinePath,
      reportDate: readoutDate,
      owner,
    }),
    [owner, readoutBaselinePath, readoutCurrentPath, readoutDate]
  );
  const checkpointCommand = useMemo(
    () => buildActivationCheckpointReadoutCommand({
      current24hPath,
      baseline24hPath,
      current48hPath,
      baseline48hPath,
      date24h,
      date48h,
      owner,
    }),
    [baseline24hPath, baseline48hPath, current24hPath, current48hPath, date24h, date48h, owner]
  );

  const loadOpsSnapshot = useCallback(async () => {
    const requestToken = opsRequestTokenRef.current + 1;
    opsRequestTokenRef.current = requestToken;
    setOpsLoading(true);
    const snapshot = await fetchOpsSnapshot();
    if (requestToken !== opsRequestTokenRef.current) return;
    if (snapshot && typeof snapshot === "object") {
      setOpsSnapshot(snapshot);
      setOpsError("");
    } else {
      setOpsSnapshot(null);
      setOpsError("Ops snapshot unavailable.");
    }
    setOpsLoading(false);
  }, [fetchOpsSnapshot]);

  useEffect(() => {
    void loadOpsSnapshot();
    return () => {
      opsRequestTokenRef.current += 1;
    };
  }, [loadOpsSnapshot]);

  useEffect(() => {
    const intervalMs = Number(opsRefreshIntervalMs);
    if (typeof window === "undefined" || !Number.isFinite(intervalMs) || intervalMs < 5000) {
      return undefined;
    }
    const timerId = window.setInterval(() => {
      void loadOpsSnapshot();
    }, intervalMs);
    return () => {
      window.clearInterval(timerId);
    };
  }, [loadOpsSnapshot, opsRefreshIntervalMs]);

  useEffect(() => {
    if (!commandCenterOpen) return undefined;
    previousFocusRef.current = document.activeElement;
    window.requestAnimationFrame(() => {
      commandCenterRef.current?.focus();
    });
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setCommandCenterOpen(false);
        return;
      }
      if (event.key === "Tab" && commandCenterRef.current) {
        const focusable = Array.from(commandCenterRef.current.querySelectorAll(FOCUSABLE_SELECTOR))
          .filter(element => !element.disabled);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey) {
          if (document.activeElement === first || document.activeElement === commandCenterRef.current) {
            event.preventDefault();
            last.focus();
          }
          return;
        }
        if (document.activeElement === last || document.activeElement === commandCenterRef.current) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [commandCenterOpen]);

  function handleRefresh() {
    setRefreshToken(version => version + 1);
    void loadOpsSnapshot();
  }

  function handleClear() {
    clearEvents();
    setRefreshToken(version => version + 1);
    setStatusMessage("Cleared local analytics events.");
  }

  function handleExportCsv() {
    const dateTag = new Date().toISOString().slice(0, 10);
    const exported = exportCsv(`ff-analytics-events-${dateTag}.csv`);
    setStatusMessage(exported ? "Exported analytics CSV." : "CSV export failed; check browser permissions.");
  }

  async function handleCopyReadoutCommand() {
    const copied = await copyTextToClipboard(readoutCommand);
    if (copied) {
      setStatusMessage("Copied activation readout command.");
      return;
    }
    if (typeof window !== "undefined" && typeof window.prompt === "function") {
      window.prompt("Copy activation readout command:", readoutCommand);
    }
    setStatusMessage("Unable to copy automatically; command shown in prompt.");
  }

  async function handleCopyCheckpointReadoutCommand() {
    const copied = await copyTextToClipboard(checkpointCommand);
    if (copied) {
      setStatusMessage("Copied checkpoint readout command.");
      return;
    }
    if (typeof window !== "undefined" && typeof window.prompt === "function") {
      window.prompt("Copy checkpoint readout command:", checkpointCommand);
    }
    setStatusMessage("Unable to copy automatically; checkpoint command shown in prompt.");
  }

  function applyDatePreset(offsetDays) {
    const next = resolveActivationDatePreset({ offsetDays });
    setReadoutDate(next.readoutDate);
    setDate24h(next.date24h);
    setDate48h(next.date48h);
    setStatusMessage(`Applied date preset (${describeDatePresetOffset(offsetDays)}).`);
  }

  return (
    <section className="activation-diagnostics-panel" aria-label="Activation diagnostics">
      <div className="activation-diagnostics-header">
        <div>
          <p className="activation-diagnostics-kicker">Owner Diagnostics</p>
          <h2>Activation Funnel Snapshot</h2>
          <p className="activation-diagnostics-meta">
            Section: {String(section || "unknown")} | Data version: {String(dataVersion || "unknown")} | Last event: {lastEventAtLabel}
          </p>
        </div>
        <div className="activation-diagnostics-actions">
          <button type="button" className="inline-btn" onClick={handleRefresh}>
            Refresh
          </button>
          <button type="button" className="inline-btn" onClick={handleExportCsv}>
            Export CSV
          </button>
          <button type="button" className="inline-btn" onClick={() => setCommandCenterOpen(true)}>
            Command Center
          </button>
          <button type="button" className="inline-btn" onClick={handleClear}>
            Clear
          </button>
          <button
            type="button"
            className="inline-btn"
            onClick={() => setDetailsOpen(open => !open)}
            aria-expanded={detailsOpen}
          >
            {detailsOpen ? "Hide JSON" : "Show JSON"}
          </button>
        </div>
      </div>
      {statusMessage && (
        <p className="activation-diagnostics-status" role="status">{statusMessage}</p>
      )}
      {opsError && (
        <p className="activation-diagnostics-note">{opsError}</p>
      )}
      {queueAlert && (
        <p className="activation-diagnostics-note activation-diagnostics-status-alert" role="alert">
          Queue alert: request timeout threshold exceeded for queued or running jobs.
        </p>
      )}

      <div className="activation-diagnostics-grid">
        <article className="activation-diagnostics-card">
          <h3>Events</h3>
          <dl>
            <dt>Total events</dt>
            <dd>{Number(eventWindow.events_total || 0).toLocaleString()}</dd>
            <dt>Impressions</dt>
            <dd>{Number(quickstart.impressions || 0).toLocaleString()}</dd>
            <dt>Clicks</dt>
            <dd>{Number(quickstart.clicks || 0).toLocaleString()}</dd>
            <dt>Runs started</dt>
            <dd>{Number(quickstart.runs_started || 0).toLocaleString()}</dd>
          </dl>
        </article>

        <article className="activation-diagnostics-card">
          <h3>Conversion</h3>
          <dl>
            <dt>Click-through</dt>
            <dd>{formatPercent(quickstart.click_through_rate_pct)}</dd>
            <dt>Start after click</dt>
            <dd>{formatPercent(quickstart.run_start_rate_pct)}</dd>
            <dt>Run success</dt>
            <dd>{formatPercent(quickstart.run_success_rate_pct)}</dd>
            <dt>Run failures</dt>
            <dd>{Number(quickstart.runs_failed || 0).toLocaleString()}</dd>
          </dl>
        </article>

        <article className="activation-diagnostics-card">
          <h3>Latency</h3>
          <dl>
            <dt>Median first success</dt>
            <dd>{formatDuration(quickstart.median_time_to_first_success_ms)}</dd>
            <dt>Window start</dt>
            <dd>{formatTimestamp(eventWindow.first_event_at_ms)}</dd>
            <dt>Window end</dt>
            <dd>{formatTimestamp(eventWindow.last_event_at_ms)}</dd>
            <dt>Recent rows</dt>
            <dd>{recentEvents.length}</dd>
          </dl>
        </article>

        <article className="activation-diagnostics-card">
          <h3>Runtime</h3>
          <dl>
            <dt>Queue utilization</dt>
            <dd>{opsLoading ? "loading..." : queueUtilizationPct}</dd>
            <dt>Active jobs</dt>
            <dd>{opsLoading ? "loading..." : queueActiveLabel}</dd>
            <dt>Oldest queued job</dt>
            <dd>{opsLoading ? "loading..." : formatSecondsAsDuration(queuePressure.queued_oldest_age_seconds)}</dd>
            <dt>Rate-limit blocks</dt>
            <dd>{opsLoading ? "loading..." : Number(rateLimitTotals.blocked || 0).toLocaleString()}</dd>
            <dt>Ops timestamp</dt>
            <dd>{opsLoading ? "loading..." : opsTimestampLabel}</dd>
          </dl>
        </article>
      </div>

      <div className="activation-diagnostics-recent">
        <h3>Recent Events</h3>
        {recentEvents.length === 0 ? (
          <p className="activation-diagnostics-empty">No events captured in local buffer yet.</p>
        ) : (
          <ul>
            {recentEvents.map((event, idx) => (
              <li key={`${event.event}-${event.timestamp}-${idx}`}>
                <strong>{event.event}</strong>
                <span>{formatTimestamp(event.timestamp)}</span>
                <span>{String(event.properties?.source || "n/a")}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {detailsOpen && (
        <pre className="activation-diagnostics-json">{JSON.stringify(summary, null, 2)}</pre>
      )}
      {commandCenterOpen && (
        <div className="activation-command-center-backdrop" onClick={() => setCommandCenterOpen(false)}>
          <div
            className="activation-command-center"
            role="dialog"
            aria-modal="true"
            aria-label="Activation command center"
            tabIndex={-1}
            ref={commandCenterRef}
            onClick={event => event.stopPropagation()}
          >
            <div className="activation-command-center-header">
              <h3>Command Center</h3>
              <button type="button" className="inline-btn" onClick={() => setCommandCenterOpen(false)}>
                Close
              </button>
            </div>
            <p className="activation-command-center-meta">
              Generate copy-ready commands for readout scripts. Update dates, then copy.
            </p>
            <div className="activation-command-center-presets">
              <button type="button" className="inline-btn" onClick={() => applyDatePreset(0)}>
                Use Today
              </button>
              <button type="button" className="inline-btn" onClick={() => applyDatePreset(1)}>
                Use Tomorrow
              </button>
            </div>
            <div className="activation-command-grid">
              <label>
                Owner
                <input
                  type="text"
                  value={owner}
                  onChange={event => setOwner(String(event.target.value || "").trim())}
                  placeholder="Analytics Team"
                />
              </label>
            </div>
            <div className="activation-command-grid">
              <label>
                Readout Date
                <input
                  type="date"
                  value={readoutDate}
                  onChange={event => setReadoutDate(String(event.target.value || "").trim())}
                />
              </label>
              <label>
                Checkpoint 24h
                <input
                  type="date"
                  value={date24h}
                  onChange={event => setDate24h(String(event.target.value || "").trim())}
                />
              </label>
              <label>
                Checkpoint 48h
                <input
                  type="date"
                  value={date48h}
                  onChange={event => setDate48h(String(event.target.value || "").trim())}
                />
              </label>
            </div>
            <div className="activation-command-item">
              <h4>Single Readout</h4>
              <div className="activation-command-grid">
                <label>
                  Current CSV Path
                  <input
                    type="text"
                    value={readoutCurrentPath}
                    onChange={event => setReadoutCurrentPath(String(event.target.value || "").trim())}
                    placeholder={DEFAULT_READOUT_CURRENT_PATH}
                  />
                </label>
                <label>
                  Baseline CSV Path
                  <input
                    type="text"
                    value={readoutBaselinePath}
                    onChange={event => setReadoutBaselinePath(String(event.target.value || "").trim())}
                    placeholder={DEFAULT_READOUT_BASELINE_PATH}
                  />
                </label>
              </div>
              <code>{readoutCommand}</code>
              <button type="button" className="inline-btn" onClick={() => void handleCopyReadoutCommand()}>
                Copy Readout Cmd
              </button>
            </div>
            <div className="activation-command-item">
              <h4>24h/48h Checkpoint Gate</h4>
              <div className="activation-command-grid">
                <label>
                  Current 24h CSV Path
                  <input
                    type="text"
                    value={current24hPath}
                    onChange={event => setCurrent24hPath(String(event.target.value || "").trim())}
                    placeholder={DEFAULT_CHECKPOINT_CURRENT_24H_PATH}
                  />
                </label>
                <label>
                  Baseline 24h CSV Path
                  <input
                    type="text"
                    value={baseline24hPath}
                    onChange={event => setBaseline24hPath(String(event.target.value || "").trim())}
                    placeholder={DEFAULT_CHECKPOINT_BASELINE_24H_PATH}
                  />
                </label>
                <label>
                  Current 48h CSV Path
                  <input
                    type="text"
                    value={current48hPath}
                    onChange={event => setCurrent48hPath(String(event.target.value || "").trim())}
                    placeholder={DEFAULT_CHECKPOINT_CURRENT_48H_PATH}
                  />
                </label>
                <label>
                  Baseline 48h CSV Path
                  <input
                    type="text"
                    value={baseline48hPath}
                    onChange={event => setBaseline48hPath(String(event.target.value || "").trim())}
                    placeholder={DEFAULT_CHECKPOINT_BASELINE_48H_PATH}
                  />
                </label>
              </div>
              <code>{checkpointCommand}</code>
              <button type="button" className="inline-btn" onClick={() => void handleCopyCheckpointReadoutCommand()}>
                Copy Checkpoint Cmd
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
