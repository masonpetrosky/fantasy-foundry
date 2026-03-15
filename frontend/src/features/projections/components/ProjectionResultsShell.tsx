import React, { useMemo } from "react";
import { SortableHeaderCell } from "../../../accessibility_components";
import { VirtualizedProjectionTable } from "./VirtualizedProjectionTable";

const VIRTUALIZATION_THRESHOLD = 50;

const CARD_SKELETON_COUNT = 8;
const TABLE_SKELETON_COUNT = 15;

const CardSkeletons = React.memo(function CardSkeletons(): React.ReactElement {
  return (
    <>
      {Array.from({ length: CARD_SKELETON_COUNT }).map((_, idx) => (
        <div className="projection-card" key={`loading-card-${idx}`}>
          <div className="loading-shimmer loading-shimmer--half" />
          <div className="loading-shimmer loading-shimmer--wide" />
        </div>
      ))}
    </>
  );
});

interface ProjectionResultsShellProps {
  showCards: boolean;
  displayedPage: unknown[];
  showInitialLoadSkeleton: boolean;
  error: string;
  retryFetch: () => void;
  emptyStateHeadline: string;
  emptyStateGuidance: string;
  emptyStateActions: React.ReactNode;
  cardRowsMarkup: React.ReactNode;
  showMobileSwipeHint: boolean;
  swipeHintText: string;
  canScrollLeft?: boolean;
  canScrollRight?: boolean;
  showInlineRefreshError: boolean;
  loading: boolean;
  cols: string[];
  colLabels: Record<string, string>;
  sortCol: string;
  sortDir: "asc" | "desc";
  onSort: (col: string) => void;
  projectionTableScrollRef: React.RefObject<HTMLDivElement | null>;
  onTableScroll: () => void;
  tableRowsMarkup: React.ReactNode;
  totalRows: number;
  limit: number;
  offset: number;
  setOffset: (offset: number) => void;
}

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
}: ProjectionResultsShellProps): React.ReactElement {
  const scrollIndicatorClass = `table-scroll-indicators${canScrollLeft ? " can-scroll-left" : ""}${canScrollRight ? " can-scroll-right" : ""}`;

  const hasNormalData = !showInitialLoadSkeleton && !(error && displayedPage.length === 0) && displayedPage.length > 0;
  const useVirtualized = hasNormalData && Array.isArray(tableRowsMarkup) && tableRowsMarkup.length > VIRTUALIZATION_THRESHOLD;

  const tableSkeletonRows = useMemo(() => (
    Array.from({ length: TABLE_SKELETON_COUNT }).map((_, i) => (
      <tr key={i}>
        <td className="index-col"><div className="loading-shimmer loading-shimmer--xs" /></td>
        {cols.map((c, j) => <td key={j}><div className={`loading-shimmer ${c === "Player" ? "loading-shimmer--lg" : "loading-shimmer--sm"}`} /></td>)}
        <td><div className="loading-shimmer loading-shimmer--md" /></td>
      </tr>
    ))
  ), [cols]);

  return (
    <>
      {showCards && (
        <div className="projection-card-list">
          {showInitialLoadSkeleton ? (
            <CardSkeletons />
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
          {!showCards && useVirtualized ? (
            <VirtualizedProjectionTable
              cols={cols}
              colLabels={colLabels}
              sortCol={sortCol}
              sortDir={sortDir}
              onSort={onSort}
              tableRowsMarkup={tableRowsMarkup as React.ReactElement[]}
              loading={loading}
              onTableScroll={onTableScroll}
              canScrollLeft={canScrollLeft}
              canScrollRight={canScrollRight}
            />
          ) : !showCards ? (
            <div className={scrollIndicatorClass}>
            <div className="table-scroll" ref={projectionTableScrollRef} onScroll={onTableScroll}>
              <table className="projections-table" aria-busy={showInitialLoadSkeleton || loading}>
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
                    tableSkeletonRows
                  ) : error && displayedPage.length === 0 ? (
                    <tr>
                      <td colSpan={cols.length + 2} className="projection-error-cell">
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
          ) : null}
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
