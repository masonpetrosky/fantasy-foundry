import React from "react";

interface OverlayStatusMeta {
  isStale: boolean;
  chips: string[];
}

interface ProjectionOverlayBannerProps {
  hasCalculatorOverlay: boolean;
  resolvedCalculatorOverlayPlayerCount: number;
  overlayStatusMeta: OverlayStatusMeta;
  showOverlayWhy: boolean;
  setShowOverlayWhy: React.Dispatch<React.SetStateAction<boolean>>;
  onClearCalculatorOverlay?: (() => void) | null;
}

export const ProjectionOverlayBanner = React.memo(function ProjectionOverlayBanner({
  hasCalculatorOverlay,
  resolvedCalculatorOverlayPlayerCount,
  overlayStatusMeta,
  showOverlayWhy,
  setShowOverlayWhy,
  onClearCalculatorOverlay,
}: ProjectionOverlayBannerProps): React.ReactElement | null {
  if (!hasCalculatorOverlay) return null;

  return (
    <div
      className={`table-refresh-message projections-overlay-message ${overlayStatusMeta.isStale ? "warning" : ""}`.trim()}
      role="status"
      aria-live="polite"
    >
      <div className="overlay-status-copy">
        <span>
          Showing calculator-adjusted dynasty values for matched players ({resolvedCalculatorOverlayPlayerCount.toLocaleString()} available).
        </span>
        {overlayStatusMeta.chips.length > 0 && (
          <div className="overlay-status-chip-row" aria-label="Applied calculator overlay details">
            {overlayStatusMeta.chips.map(chip => (
              <span key={chip} className="overlay-status-chip">{chip}</span>
            ))}
          </div>
        )}
        {overlayStatusMeta.isStale && (
          <span className="overlay-stale-note">
            Overlay source is from an older projections build. Re-run the calculator to refresh these values.
          </span>
        )}
        <button
          type="button"
          className="inline-btn overlay-why-btn"
          onClick={() => setShowOverlayWhy(current => !current)}
        >
          {showOverlayWhy ? "Hide why this changed" : "Why this changed"}
        </button>
        {showOverlayWhy && (
          <p className="overlay-why-copy">
            Calculator overlays re-rank players using your league setup (teams, roster depth, scoring mode, and horizon) instead of baseline site defaults.
          </p>
        )}
      </div>
      {typeof onClearCalculatorOverlay === "function" && (
        <button type="button" className="inline-btn" onClick={onClearCalculatorOverlay}>
          Clear applied values
        </button>
      )}
    </div>
  );
});
