import React, { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { SortableHeaderCell } from "../../../accessibility_components";

const ESTIMATED_ROW_HEIGHT = 40;
const OVERSCAN_COUNT = 5;

interface VirtualizedProjectionTableProps {
  cols: string[];
  colLabels: Record<string, string>;
  sortCol: string;
  sortDir: "asc" | "desc";
  onSort: (col: string) => void;
  tableRowsMarkup: React.ReactElement[];
  loading: boolean;
  onTableScroll: () => void;
  canScrollLeft?: boolean;
  canScrollRight?: boolean;
}

export const VirtualizedProjectionTable = React.memo(function VirtualizedProjectionTable({
  cols,
  colLabels,
  sortCol,
  sortDir,
  onSort,
  tableRowsMarkup,
  loading,
  onTableScroll,
  canScrollLeft,
  canScrollRight,
}: VirtualizedProjectionTableProps): React.ReactElement {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: tableRowsMarkup.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => ESTIMATED_ROW_HEIGHT,
    overscan: OVERSCAN_COUNT,
  });

  const virtualItems = rowVirtualizer.getVirtualItems();
  const totalSize = rowVirtualizer.getTotalSize();

  const paddingTop = virtualItems.length > 0 ? virtualItems[0].start : 0;
  const paddingBottom = virtualItems.length > 0
    ? totalSize - virtualItems[virtualItems.length - 1].end
    : 0;

  const scrollIndicatorClass = `table-scroll-indicators${canScrollLeft ? " can-scroll-left" : ""}${canScrollRight ? " can-scroll-right" : ""}`;

  return (
    <div className={scrollIndicatorClass}>
      <div
        className="table-scroll"
        ref={scrollContainerRef}
        onScroll={onTableScroll}
      >
        <table
          className="projections-table"
          aria-label="Player projections"
          aria-busy={loading}
          aria-rowcount={tableRowsMarkup.length}
          style={{ tableLayout: "fixed" }}
        >
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
            {paddingTop > 0 && (
              <tr aria-hidden="true">
                <td style={{ height: paddingTop, padding: 0, border: "none" }} />
              </tr>
            )}
            {virtualItems.map(virtualRow => {
              const row = tableRowsMarkup[virtualRow.index];
              return React.cloneElement(row, {
                key: row.key ?? virtualRow.index,
                "data-index": virtualRow.index,
                ref: rowVirtualizer.measureElement,
              });
            })}
            {paddingBottom > 0 && (
              <tr aria-hidden="true">
                <td style={{ height: paddingBottom, padding: 0, border: "none" }} />
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
});
