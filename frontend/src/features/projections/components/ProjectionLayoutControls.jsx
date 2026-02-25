import React from "react";
import { ColumnChooserControl } from "../../../ui_components.jsx";

export const ProjectionLayoutControls = React.memo(function ProjectionLayoutControls({
  isMobileViewport,
  mobileLayoutMode,
  setMobileLayoutMode,
  cardColumnCatalog,
  resolvedProjectionCardHiddenCols,
  requiredProjectionCardCols,
  toggleProjectionCardColumn,
  showAllProjectionCardColumns,
  colLabels,
}) {
  return (
    <div className="projection-layout-controls" role="group" aria-label="Projection layout controls">
      <div className="projection-layout-row">
        <span className="label">
          Layout
          {isMobileViewport ? ` · Viewing ${mobileLayoutMode === "cards" ? "Cards" : "Table"}` : ""}
        </span>
        <div className="projection-view-toggle">
          <button
            type="button"
            className={`projection-view-btn ${mobileLayoutMode === "cards" ? "active" : ""}`.trim()}
            onClick={() => setMobileLayoutMode("cards")}
            aria-pressed={mobileLayoutMode === "cards"}
          >
            Card View
          </button>
          <button
            type="button"
            className={`projection-view-btn ${mobileLayoutMode === "table" ? "active" : ""}`.trim()}
            onClick={() => setMobileLayoutMode("table")}
            aria-pressed={mobileLayoutMode === "table"}
          >
            Table View
          </button>
        </div>
      </div>
      {mobileLayoutMode === "cards" && ColumnChooserControl && (
        <div className="projection-layout-row">
          <span className="label">Cards</span>
          <ColumnChooserControl
            buttonLabel="Card Stats"
            columns={cardColumnCatalog}
            hiddenCols={resolvedProjectionCardHiddenCols}
            requiredCols={requiredProjectionCardCols}
            onToggleColumn={toggleProjectionCardColumn}
            onShowAllColumns={showAllProjectionCardColumns}
            columnLabels={colLabels}
          />
        </div>
      )}
    </div>
  );
});
