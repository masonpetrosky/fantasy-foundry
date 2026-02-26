# Projections Feature Contract

## Projection View Model
The projections UI consumes rows from `/api/projections/*` and treats each row as a projection view model with these commonly accessed fields:
- `Player`, `Team`, `Pos`, `Type`
- `Year` or `Years` (depending on rest-of-career mode)
- `DynastyValue` and optional `Value_<year>` dynasty overlays
- stat/value columns resolved by `projectionTableColumnCatalog` / `projectionCardColumnCatalog`

## Stability Rules
- Keep request query semantics unchanged for filters, sorting, and exports.
- Preserve local storage keys used by layout and column visibility preferences.
- Keep `container.jsx` focused on orchestration/rendering; place stateful logic in hooks under `hooks/`.
- Keep reusable presentation blocks under `components/` to avoid re-growing the container module.

## Hook Ownership
- `useProjectionExportPipeline` owns export request assembly + export in-flight/error state.
- `useProjectionWatchlistComposition` owns watchlist workspace composition and view-model shaping.
- `useProjectionComparisonComposition` owns comparison workspace composition, share-link copy behavior, and tab-specific compare columns.
- `useProjectionTelemetry` owns projections empty-state telemetry and last-refresh label state.
- `useProjectionRowsMarkup` owns card/table row markup rendering and projection-cell formatting.
- `useProjectionColumnVisibility`, `useProjectionLayoutState`, and `useProjectionFilterPresets` expose pure helper utilities that are covered by focused unit tests.

## Component Ownership
- `ProjectionCollectionsWorkspace` owns watchlist/compare toolbar and workspace panel composition.
- `ProjectionLayoutControls` owns table/card toggle controls and card-column chooser rendering.
- `ProjectionResultsShell` owns table/card results rendering states (loading/error/empty/pagination/swipe hint).
- `ProjectionSectionTabs` owns the all/hitters/pitchers tab controls.
- `ProjectionStatusMessages` owns page-reset/export/refresh status banner rendering plus shared-compare copy/hydration notices.
- `ProjectionEmptyStateActions` owns empty-state CTA composition.
