import { useCallback, useEffect, useMemo, useState } from "react";
import {
  PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY,
  PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY,
  readHiddenColumnOverridesByTab,
  writeHiddenColumnOverridesByTab,
} from "../../../app_state_storage.js";
import {
  normalizeHiddenColumnOverridesByTab,
  projectionCardColumnCatalog,
  projectionCardDefaultVisibleColumns,
  projectionCardOptionalColumnHiddenByDefault,
  projectionTableColumnCatalog,
  projectionTableColumnHiddenByDefault,
  resolveProjectionCardColumns,
} from "../../../projections_view_config.js";

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
    if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
      return Boolean(hiddenOverrides[col]);
    }
    return projectionTableColumnHiddenByDefault(tab, col);
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
    if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
      return Boolean(hiddenOverrides[col]);
    }
    return projectionCardOptionalColumnHiddenByDefault(col, cardDefaultVisibleSet);
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
    setProjectionTableHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      const defaultHidden = projectionTableColumnHiddenByDefault(tab, col);
      if (hidden === defaultHidden) {
        delete nextTab[col];
      } else {
        nextTab[col] = hidden;
      }
      next[tab] = nextTab;
      return next;
    });
  }, [tab]);

  const toggleProjectionTableColumn = useCallback(col => {
    if (requiredProjectionTableCols.has(col)) return;
    const currentlyHidden = isProjectionTableColHidden(col);
    setProjectionTableColumnHidden(col, !currentlyHidden);
  }, [isProjectionTableColHidden, requiredProjectionTableCols, setProjectionTableColumnHidden]);

  const showAllProjectionTableColumns = useCallback(() => {
    setProjectionTableHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      tableColumnCatalog.forEach(col => {
        if (requiredProjectionTableCols.has(col)) return;
        nextTab[col] = false;
      });
      next[tab] = nextTab;
      return next;
    });
  }, [requiredProjectionTableCols, tab, tableColumnCatalog]);

  const setProjectionCardOptionalColumnHidden = useCallback((col, hidden) => {
    setProjectionCardHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      const defaultHidden = projectionCardOptionalColumnHiddenByDefault(col, cardDefaultVisibleSet);
      if (hidden === defaultHidden) {
        delete nextTab[col];
      } else {
        nextTab[col] = hidden;
      }
      next[tab] = nextTab;
      return next;
    });
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
    setProjectionCardHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      cardOptionalCols.forEach(col => {
        nextTab[col] = false;
      });
      next[tab] = nextTab;
      return next;
    });
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
