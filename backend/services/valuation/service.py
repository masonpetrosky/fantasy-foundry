"""Service boundary around legacy dynasty valuation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd


@dataclass(slots=True)
class ValuationService:
    """Facade for loading and invoking legacy valuation primitives."""

    ensure_backend_module_path_fn: Callable[[], None]

    def _legacy_symbols(self) -> tuple[Any, Callable[..., pd.DataFrame]]:
        self.ensure_backend_module_path_fn()
        from dynasty_roto_values import CommonDynastyRotoSettings, calculate_common_dynasty_values

        return CommonDynastyRotoSettings, calculate_common_dynasty_values

    def build_common_roto_settings(self, **kwargs: Any) -> Any:
        common_settings_cls, _ = self._legacy_symbols()
        return common_settings_cls(**kwargs)

    def calculate_common_dynasty_values(
        self,
        excel_path: Path | str,
        league_settings: Any,
        *,
        start_year: int,
        recent_projections: int,
    ) -> pd.DataFrame:
        _, calculator_fn = self._legacy_symbols()
        return calculator_fn(
            str(excel_path),
            league_settings,
            start_year=start_year,
            verbose=False,
            return_details=False,
            seed=0,
            recent_projections=recent_projections,
        )
