import { useCallback, useEffect, useMemo, useState } from "react";
import {
  PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY,
  PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY,
  readHiddenColumnOverridesByTab,
  writeHiddenColumnOverridesByTab,
} from "../../../app_state_storage";
import type { ProjectionRow } from "../../../app_state_storage";
import {
  normalizeHiddenColumnOverridesByTab,
  projectionCardColumnCatalog,
  projectionCardDefaultVisibleColumns,
  projectionCardOptionalColumnHiddenByDefault,
  projectionTableColumnCatalog,
  projectionTableColumnHiddenByDefault,
  resolveProjectionCardColumns,
} from "../../../projections_view_config";
import type {
  HiddenColumnOverrides,
  HiddenColumnOverridesByTab,
} from "../../../projections_view_config";
import type { CalculatorSettings } from "../../../dynasty_calculator_config";

export function resolveProjectionTableColumnHidden(
  tab: string,
  col: string,
  hiddenOverridesByTab: HiddenColumnOverrides = {},
): boolean {
  if (Object.prototype.hasOwnProperty.call(hiddenOverridesByTab, col)) {
    return Boolean(hiddenOverridesByTab[col]);
  }
  return projectionTableColumnHiddenByDefault(tab, col);
}

export function resolveProjectionCardColumnHidden(
  col: string,
  hiddenOverridesByTab: HiddenColumnOverrides = {},
  cardDefaultVisibleSet: ReadonlySet<string> = new Set(),
): boolean {
  if (Object.prototype.hasOwnProperty.call(hiddenOverridesByTab, col)) {
    return Boolean(hiddenOverridesByTab[col]);
  }
  return projectionCardOptionalColumnHiddenByDefault(col, cardDefaultVisibleSet);
}

export function buildHiddenColumnOverridesByTab({
  currentByTab,
  tab,
  col,
  hidden,
  defaultHidden,
}: {
  currentByTab: HiddenColumnOverridesByTab;
  tab: string;
  col: string;
  hidden: boolean;
  defaultHidden: boolean;
}): HiddenColumnOverridesByTab {
  const next = normalizeHiddenColumnOverridesByTab(currentByTab);
  const nextTab: HiddenColumnOverrides = { ...(next[tab] || {}) };
  if (hidden === defaultHidden) {
    delete nextTab[col];
  } else {
    nextTab[col] = hidden;
  }
  next[tab] = nextTab;
  return next;
}

export function buildShowAllColumnsOverridesByTab({
  currentByTab,
  tab,
  columns,
  requiredCols = new Set(),
}: {
  currentByTab: HiddenColumnOverridesByTab;
  tab: string;
  columns: string[];
  requiredCols?: ReadonlySet<string>;
}): HiddenColumnOverridesByTab {
  const next = normalizeHiddenColumnOverridesByTab(currentByTab);
  const nextTab: HiddenColumnOverrides = { ...(next[tab] || {}) };
  columns.forEach(col => {
    if (requiredCols.has(col)) return;
    nextTab[col] = false;
  });
  next[tab] = nextTab;
  return next;
}

export interface UseProjectionColumnVisibilityInput {
  tab: string;
  seasonCol: string;
  dynastyYearCols: string[];
  activeCalculatorSettings: CalculatorSettings | null | undefined;
}

export interface UseProjectionColumnVisibilityResult {
  tableColumnCatalog: string[];
  requiredProjectionTableCols: ReadonlySet<string>;
  resolvedProjectionTableHiddenCols: Record<string, boolean>;
  cols: string[];
  toggleProjectionTableColumn: (col: string) => void;
  showAllProjectionTableColumns: () => void;
  cardColumnCatalog: string[];
  requiredProjectionCardCols: ReadonlySet<string>;
  resolvedProjectionCardHiddenCols: Record<string, boolean>;
  projectionCardColumnsForRow: (row: ProjectionRow) => string[];
  toggleProjectionCardColumn: (col: string) => void;
  showAllProjectionCardColumns: () => void;
}

export function useProjectionColumnVisibility({
  tab,
  seasonCol,
  dynastyYearCols,
  activeCalculatorSettings,
}: UseProjectionColumnVisibilityInput): UseProjectionColumnVisibilityResult {
  const [projectionTableHiddenColsByTab, setProjectionTableHiddenColsByTab] = useState<HiddenColumnOverridesByTab>(() => (
    readHiddenColumnOverridesByTab(PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY)
  ));
  const [projectionCardHiddenColsByTab, setProjectionCardHiddenColsByTab] = useState<HiddenColumnOverridesByTab>(() => (
    readHiddenColumnOverridesByTab(PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY)
  ));

  useEffect(() => {
    writeHiddenColumnOverridesByTab(PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY, projectionTableHiddenColsByTab);
  }, [projectionTableHiddenColsByTab]);

  useEffect(() => {
    writeHiddenColumnOverridesByTab(PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY, projectionCardHiddenColsByTab);
  }, [projectionCardHiddenColsByTab]);

  const tableColumnCatalog = useMemo(
    () => projectionTableColumnCatalog(tab, seasonCol, dynastyYearCols, activeCalculatorSettings),
    [tab, seasonCol, dynastyYearCols, activeCalculatorSettings]
  );

  const requiredProjectionTableCols = useMemo<ReadonlySet<string>>(() => new Set(["Player"]), []);

  const activeProjectionTableHiddenCols: HiddenColumnOverrides = useMemo(
    () => projectionTableHiddenColsByTab[tab] || {},
    [projectionTableHiddenColsByTab, tab]
  );

  const isProjectionTableColHidden = useCallback((col: string, hiddenOverrides: HiddenColumnOverrides = activeProjectionTableHiddenCols): boolean => {
    return resolveProjectionTableColumnHidden(tab, col, hiddenOverrides);
  }, [tab, activeProjectionTableHiddenCols]);

  const resolvedProjectionTableHiddenCols = useMemo(() => {
    const hidden: Record<string, boolean> = {};
    tableColumnCatalog.forEach(col => {
      if (isProjectionTableColHidden(col)) hidden[col] = true;
    });
    return hidden;
  }, [tableColumnCatalog, isProjectionTableColHidden]);

  const cols = useMemo(
    () => tableColumnCatalog.filter(col => !isProjectionTableColHidden(col)),
    [tableColumnCatalog, isProjectionTableColHidden]
  );

  const cardColumnCatalog = useMemo(
    () => projectionCardColumnCatalog(tab, seasonCol, dynastyYearCols, activeCalculatorSettings),
    [tab, seasonCol, dynastyYearCols, activeCalculatorSettings]
  );

  const cardDefaultVisibleSet = useMemo<ReadonlySet<string>>(
    () => new Set(projectionCardDefaultVisibleColumns(tab, null, activeCalculatorSettings)),
    [tab, activeCalculatorSettings]
  );

  const activeProjectionCardHiddenCols: HiddenColumnOverrides = useMemo(
    () => projectionCardHiddenColsByTab[tab] || {},
    [projectionCardHiddenColsByTab, tab]
  );

  const isProjectionCardOptionalColHidden = useCallback((col: string, hiddenOverrides: HiddenColumnOverrides = activeProjectionCardHiddenCols): boolean => {
    return resolveProjectionCardColumnHidden(col, hiddenOverrides, cardDefaultVisibleSet);
  }, [activeProjectionCardHiddenCols, cardDefaultVisibleSet]);

  const cardOptionalCols = useMemo(
    () => [...cardColumnCatalog],
    [cardColumnCatalog]
  );

  const requiredProjectionCardCols = useMemo<ReadonlySet<string>>(() => new Set(), []);

  const resolvedProjectionCardHiddenCols = useMemo(() => {
    const hidden: Record<string, boolean> = {};
    cardColumnCatalog.forEach(col => {
      if (isProjectionCardOptionalColHidden(col)) hidden[col] = true;
    });
    return hidden;
  }, [cardColumnCatalog, isProjectionCardOptionalColHidden]);

  const projectionCardColumnsForRow = useCallback((row: ProjectionRow): string[] => (
    resolveProjectionCardColumns(
      tab,
      seasonCol,
      dynastyYearCols,
      row,
      activeProjectionCardHiddenCols,
      activeCalculatorSettings
    )
  ), [tab, seasonCol, dynastyYearCols, activeProjectionCardHiddenCols, activeCalculatorSettings]);

  const setProjectionTableColumnHidden = useCallback((col: string, hidden: boolean) => {
    setProjectionTableHiddenColsByTab(current => buildHiddenColumnOverridesByTab({
      currentByTab: current,
      tab,
      col,
      hidden,
      defaultHidden: projectionTableColumnHiddenByDefault(tab, col),
    }));
  }, [tab]);

  const toggleProjectionTableColumn = useCallback((col: string) => {
    if (requiredProjectionTableCols.has(col)) return;
    const currentlyHidden = isProjectionTableColHidden(col);
    setProjectionTableColumnHidden(col, !currentlyHidden);
  }, [isProjectionTableColHidden, requiredProjectionTableCols, setProjectionTableColumnHidden]);

  const showAllProjectionTableColumns = useCallback(() => {
    setProjectionTableHiddenColsByTab(current => buildShowAllColumnsOverridesByTab({
      currentByTab: current,
      tab,
      columns: tableColumnCatalog,
      requiredCols: requiredProjectionTableCols,
    }));
  }, [requiredProjectionTableCols, tab, tableColumnCatalog]);

  const setProjectionCardOptionalColumnHidden = useCallback((col: string, hidden: boolean) => {
    setProjectionCardHiddenColsByTab(current => buildHiddenColumnOverridesByTab({
      currentByTab: current,
      tab,
      col,
      hidden,
      defaultHidden: projectionCardOptionalColumnHiddenByDefault(col, cardDefaultVisibleSet),
    }));
  }, [cardDefaultVisibleSet, tab]);

  const toggleProjectionCardColumn = useCallback((col: string) => {
    if (requiredProjectionCardCols.has(col)) return;
    const currentlyHidden = isProjectionCardOptionalColHidden(col);
    setProjectionCardOptionalColumnHidden(col, !currentlyHidden);
  }, [
    isProjectionCardOptionalColHidden,
    requiredProjectionCardCols,
    setProjectionCardOptionalColumnHidden,
  ]);

  const showAllProjectionCardColumns = useCallback(() => {
    setProjectionCardHiddenColsByTab(current => buildShowAllColumnsOverridesByTab({
      currentByTab: current,
      tab,
      columns: cardOptionalCols,
    }));
  }, [cardOptionalCols, tab]);

  return {
    tableColumnCatalog,
    requiredProjectionTableCols,
    resolvedProjectionTableHiddenCols,
    cols,
    toggleProjectionTableColumn,
    showAllProjectionTableColumns,
    cardColumnCatalog,
    requiredProjectionCardCols,
    resolvedProjectionCardHiddenCols,
    projectionCardColumnsForRow,
    toggleProjectionCardColumn,
    showAllProjectionCardColumns,
  };
}
