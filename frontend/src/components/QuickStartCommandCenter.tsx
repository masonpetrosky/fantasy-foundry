import React from "react";

type QuickStartMode = "roto" | "points" | "deep";

export interface QuickStartCommandCenterProps {
  showQuickStartOnboarding: boolean;
  showQuickStartReminder: boolean;
  showPostSuccessActions: boolean;
  allowExport: boolean;
  onRunQuickStart: (mode: QuickStartMode, source: string) => void;
  onDismissQuickStart: () => void;
  onReopenQuickStart: () => void;
  onSavePreset: () => void;
  onCopyShareLink: () => void;
  onOpenExports: () => void;
}

export function QuickStartCommandCenter({
  showQuickStartOnboarding,
  showQuickStartReminder,
  showPostSuccessActions,
  allowExport,
  onRunQuickStart,
  onDismissQuickStart,
  onReopenQuickStart,
  onSavePreset,
  onCopyShareLink,
  onOpenExports,
}: QuickStartCommandCenterProps): React.ReactElement | null {
  if (showQuickStartOnboarding) {
    return (
      <section className="activation-strip" aria-label="Quick start dynasty rankings">
        <div className="activation-strip-copy">
          <p className="activation-strip-kicker">Recommended Start</p>
          <h2>Start with a preset league, then fine-tune after results load.</h2>
          <p>Pick the format closest to your league and generate custom dynasty rankings immediately.</p>
          <ul className="activation-benefits" aria-label="Quick start benefits">
            <li>League-specific rankings in one click</li>
            <li>Career plus season-by-season views</li>
            <li>Shareable settings and export-ready results</li>
          </ul>
        </div>
        <div className="activation-strip-actions" role="group" aria-label="Quick start options">
          <button
            type="button"
            className="activation-strip-btn activation-strip-btn-primary"
            onClick={() => onRunQuickStart("roto", "activation_strip")}
          >
            Run Standard 5x5
          </button>
          <button
            type="button"
            className="activation-strip-btn"
            onClick={() => onRunQuickStart("points", "activation_strip_points")}
          >
            Run Points
          </button>
          <button
            type="button"
            className="activation-strip-btn"
            onClick={() => onRunQuickStart("deep", "activation_strip_deep")}
          >
            Run Deep Dynasty
          </button>
        </div>
        <button
          type="button"
          className="activation-strip-dismiss"
          onClick={onDismissQuickStart}
          aria-label="Dismiss quick start guide"
        >
          Dismiss
        </button>
      </section>
    );
  }

  if (showQuickStartReminder) {
    return (
      <section className="activation-strip" aria-label="Quick start reminder">
        <div className="activation-strip-copy">
          <p className="activation-strip-kicker">Reminder</p>
          <h2>Need a fast starting point?</h2>
          <p>Reopen the preset launcher or run the standard roto setup immediately.</p>
        </div>
        <div className="activation-strip-actions" role="group" aria-label="Quick start reminder actions">
          <button
            type="button"
            className="activation-strip-btn activation-strip-btn-primary"
            onClick={onReopenQuickStart}
          >
            Reopen Presets
          </button>
          <button
            type="button"
            className="activation-strip-btn"
            onClick={() => onRunQuickStart("roto", "activation_reminder")}
          >
            Run Standard 5x5
          </button>
        </div>
      </section>
    );
  }

  if (showPostSuccessActions) {
    return (
      <section className="activation-strip" aria-label="Calculator next steps">
        <div className="activation-strip-copy">
          <p className="activation-strip-kicker">Next Steps</p>
          <h2>Your custom rankings are ready.</h2>
          <p>Save this setup, copy a share link, or jump to export actions without rebuilding the run.</p>
        </div>
        <div className="activation-strip-actions" role="group" aria-label="Post-success actions">
          <button
            type="button"
            className="activation-strip-btn activation-strip-btn-primary"
            onClick={onSavePreset}
          >
            Save Preset
          </button>
          <button
            type="button"
            className="activation-strip-btn"
            onClick={onCopyShareLink}
          >
            Copy Share Link
          </button>
          <button
            type="button"
            className="activation-strip-btn"
            onClick={onOpenExports}
          >
            {allowExport ? "Open Export Actions" : "See Export Options"}
          </button>
        </div>
      </section>
    );
  }

  return null;
}
