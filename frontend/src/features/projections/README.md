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
- `useProjectionComparisonComposition` owns comparison workspace composition and tab-specific compare columns.
- `useProjectionColumnVisibility`, `useProjectionLayoutState`, and `useProjectionFilterPresets` expose pure helper utilities that are covered by focused unit tests.
