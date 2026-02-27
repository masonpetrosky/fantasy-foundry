import React from "react";
import { SortableHeaderCell } from "../../../accessibility_components";

export const ProjectionResultsShell = React.memo(function ProjectionResultsShell({
  showCards,
  displayedPage,
  showInitialLoadSkeleton,
  error,
  retryFetch,
  emptyStateHeadline,
  emptyStateGuidance,
  emptyStateActions,
  cardRowsMarkup,
  showMobileSwipeHint,
  swipeHintText,
  canScrollLeft,
  canScrollRight,
  showInlineRefreshError,
  loading,
  cols,
  colLabels,
  sortCol,
  sortDir,
  onSort,
  projectionTableScrollRef,
  onTableScroll,
  tableRowsMarkup,
  totalRows,
  limit,
  offset,
  setOffset,
}) {
  const scrollIndicatorClass = `table-scroll-indicators${canScrollLeft ? " can-scroll-left" : ""}${canScrollRight ? " can-scroll-right" : ""}`;
  return (
    <>
      {showCards && (
        <div className="projection-card-list">
          {showInitialLoadSkeleton ? (
            Array.from({ length: 8 }).map((_, idx) => (
              <div className="projection-card" key={`loading-card-${idx}`}>
                <div className="loading-shimmer" style={{ width: "60%", margin: 0 }} />
                <div className="loading-shimmer" style={{ width: "90%", marginTop: 10 }} />
              </div>
            ))
          ) : error && displayedPage.length === 0 ? (
            <div className="projection-card-empty">Unable to load projections. {error}{" "}<button type="button" className="inline-btn" onClick={retryFetch}>Retry</button></div>
          ) : displayedPage.length === 0 ? (
            <div className="projection-card-empty">
              <p>{emptyStateHeadline}</p>
              <p className="projection-empty-guidance">{emptyStateGuidance}</p>
              {emptyStateActions}
            </div>
          ) : (
            cardRowsMarkup
          )}
        </div>
      )}
      {showMobileSwipeHint && (
        <div className="table-swipe-hint" role="note">
          {swipeHintText}
        </div>
      )}
      {showInlineRefreshError && (
        <div className="table-refresh-message error" role="status" aria-live="polite">
          Refresh failed. Showing last loaded page. {error}
        </div>
      )}
      {loading && displayedPage.length > 0 && !showInlineRefreshError && (
        <div className="table-refresh-message" role="status" aria-live="polite">
          Refreshing results...
        </div>
      )}

      {(!showCards || totalRows > limit) && (
        <div className="table-wrapper">
          {!showCards && (
            <div className={scrollIndicatorClass}>
            <div className="table-scroll" ref={projectionTableScrollRef} onScroll={onTableScroll}>
              <table className="projections-table">
                <thead>
                  <tr>
                    <th scope="col" className="index-col" style={{ width: 40 }}>#</th>
                    {cols.map(c => (
                      <SortableHeaderCell
                        key={c}
                        columnKey={c}
                        label={colLabels[c] || c}
                        sortCol={sortCol}
                        sortDir={sortDir}
                        onSort={onSort}
                        className={`${sortCol === c ? "sorted" : ""}${c === "Player" ? " player-col" : ""}`.trim()}
                      />
                    ))}
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {showInitialLoadSkeleton ? (
                    Array.from({ length: 15 }).map((_, i) => (
                      <tr key={i}>
                        <td className="index-col"><div className="loading-shimmer" style={{ width: 24 }} /></td>
                        {cols.map((c, j) => <td key={j}><div className="loading-shimmer" style={{ width: c === "Player" ? 120 : 50 }} /></td>)}
                        <td><div className="loading-shimmer" style={{ width: 90 }} /></td>
                      </tr>
                    ))
                  ) : error && displayedPage.length === 0 ? (
                    <tr>
                      <td colSpan={cols.length + 2} style={{ textAlign: "center", padding: "40px", color: "var(--red)" }}>
                        Unable to load projections. {error}{" "}<button type="button" className="inline-btn" onClick={retryFetch}>Retry</button>
                      </td>
                    </tr>
                  ) : displayedPage.length === 0 ? (
                    <tr>
                      <td className="projection-empty-cell" colSpan={cols.length + 2}>
                        <p className="projection-empty-title">{emptyStateHeadline}</p>
                        <p className="projection-empty-guidance">{emptyStateGuidance}</p>
                        {emptyStateActions}
                      </td>
                    </tr>
                  ) : (
                    tableRowsMarkup
                  )}
                </tbody>
              </table>
            </div>
            </div>
          )}
          {totalRows > limit && (
            <div className="pagination">
              <button aria-label="Previous page" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))}>← Previous</button>
              <span className="page-info">
                {totalRows === 0 ? 0 : offset + 1}–{Math.min(offset + limit, totalRows)} of {totalRows}
              </span>
              <button aria-label="Next page" disabled={offset + limit >= totalRows || loading} onClick={() => setOffset(offset + limit)}>Next →</button>
            </div>
          )}
        </div>
      )}
    </>
  );
});
