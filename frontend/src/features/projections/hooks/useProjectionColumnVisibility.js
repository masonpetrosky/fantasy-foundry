import { useCallback, useEffect, useMemo, useState } from "react";
import {
  PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY,
  PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY,
  readHiddenColumnOverridesByTab,
  writeHiddenColumnOverridesByTab,
} from "../../../app_state_storage";
import {
  normalizeHiddenColumnOverridesByTab,
  projectionCardColumnCatalog,
  projectionCardDefaultVisibleColumns,
  projectionCardOptionalColumnHiddenByDefault,
  projectionTableColumnCatalog,
  projectionTableColumnHiddenByDefault,
  resolveProjectionCardColumns,
} from "../../../projections_view_config";

export function resolveProjectionTableColumnHidden(tab, col, hiddenOverridesByTab = {}) {
  if (Object.prototype.hasOwnProperty.call(hiddenOverridesByTab, col)) {
    return Boolean(hiddenOverridesByTab[col]);
  }
  return projectionTableColumnHiddenByDefault(tab, col);
}

export function resolveProjectionCardColumnHidden(col, hiddenOverridesByTab = {}, cardDefaultVisibleSet = new Set()) {
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
}) {
  const next = normalizeHiddenColumnOverridesByTab(currentByTab);
  const nextTab = { ...(next[tab] || {}) };
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
}) {
  const next = normalizeHiddenColumnOverridesByTab(currentByTab);
  const nextTab = { ...(next[tab] || {}) };
  columns.forEach(col => {
    if (requiredCols.has(col)) return;
    nextTab[col] = false;
  });
  next[tab] = nextTab;
  return next;
}

export function useProjectionColumnVisibility({
  tab,
  seasonCol,
  dynastyYearCols,
  activeCalculatorSettings,
}) {
  const [projectionTableHiddenColsByTab, setProjectionTableHiddenColsByTab] = useState(() => (
    readHiddenColumnOverridesByTab(PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY)
  ));
  const [projectionCardHiddenColsByTab, setProjectionCardHiddenColsByTab] = useState(() => (
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

  const activeProjectionTableHiddenCols = projectionTableHiddenColsByTab[tab] || {};
  const requiredProjectionTableCols = useMemo(() => new Set(["Player"]), []);

  const isProjectionTableColHidden = useCallback((col, hiddenOverrides = activeProjectionTableHiddenCols) => {
    return resolveProjectionTableColumnHidden(tab, col, hiddenOverrides);
  }, [tab, activeProjectionTableHiddenCols]);

  const resolvedProjectionTableHiddenCols = useMemo(() => {
    const hidden = {};
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

  const cardDefaultVisibleSet = useMemo(
    () => new Set(projectionCardDefaultVisibleColumns(tab, null, activeCalculatorSettings)),
    [tab, activeCalculatorSettings]
  );

  const activeProjectionCardHiddenCols = projectionCardHiddenColsByTab[tab] || {};

  const isProjectionCardOptionalColHidden = useCallback((col, hiddenOverrides = activeProjectionCardHiddenCols) => {
    return resolveProjectionCardColumnHidden(col, hiddenOverrides, cardDefaultVisibleSet);
  }, [activeProjectionCardHiddenCols, cardDefaultVisibleSet]);

  const cardOptionalCols = useMemo(
    () => [...cardColumnCatalog],
    [cardColumnCatalog]
  );

  const requiredProjectionCardCols = useMemo(() => new Set(), []);

  const resolvedProjectionCardHiddenCols = useMemo(() => {
    const hidden = {};
    cardColumnCatalog.forEach(col => {
      if (isProjectionCardOptionalColHidden(col)) hidden[col] = true;
    });
    return hidden;
  }, [cardColumnCatalog, isProjectionCardOptionalColHidden]);

  const projectionCardColumnsForRow = useCallback(row => (
    resolveProjectionCardColumns(
      tab,
      seasonCol,
      dynastyYearCols,
      row,
      activeProjectionCardHiddenCols,
      activeCalculatorSettings
    )
  ), [tab, seasonCol, dynastyYearCols, activeProjectionCardHiddenCols, activeCalculatorSettings]);

  const setProjectionTableColumnHidden = useCallback((col, hidden) => {
    setProjectionTableHiddenColsByTab(current => buildHiddenColumnOverridesByTab({
      currentByTab: current,
      tab,
      col,
      hidden,
      defaultHidden: projectionTableColumnHiddenByDefault(tab, col),
    }));
  }, [tab]);

  const toggleProjectionTableColumn = useCallback(col => {
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

  const setProjectionCardOptionalColumnHidden = useCallback((col, hidden) => {
    setProjectionCardHiddenColsByTab(current => buildHiddenColumnOverridesByTab({
      currentByTab: current,
      tab,
      col,
      hidden,
      defaultHidden: projectionCardOptionalColumnHiddenByDefault(col, cardDefaultVisibleSet),
    }));
  }, [cardDefaultVisibleSet, tab]);

  const toggleProjectionCardColumn = useCallback(col => {
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
