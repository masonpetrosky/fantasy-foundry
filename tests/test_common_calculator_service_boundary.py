import pandas as pd

from backend.core import common_calculator


def test_common_calculator_delegates_to_valuation_service(monkeypatch):
    calls: dict[str, object] = {}

    class FakeValuationService:
        def __init__(self, ensure_backend_module_path_fn):
            calls["ensure_backend_module_path_fn"] = ensure_backend_module_path_fn

        def build_common_roto_settings(self, **kwargs):
            calls["settings_kwargs"] = kwargs
            return {"kind": "fake-settings"}

        def calculate_common_dynasty_values(self, excel_path, league_settings, *, start_year, recent_projections):
            calls["calculate_args"] = {
                "excel_path": excel_path,
                "league_settings": league_settings,
                "start_year": start_year,
                "recent_projections": recent_projections,
            }
            return pd.DataFrame([{"Player": "Test Player", "DynastyValue": 12.3}])

    monkeypatch.setattr(common_calculator, "ValuationService", FakeValuationService)

    out = common_calculator.calculate_common_dynasty_frame(
        ensure_backend_module_path_fn=lambda: None,
        excel_path="data/Dynasty Baseball Projections.xlsx",
        teams=12,
        sims=300,
        horizon=20,
        discount=0.94,
        hit_c=1,
        hit_1b=1,
        hit_2b=1,
        hit_3b=1,
        hit_ss=1,
        hit_ci=1,
        hit_mi=1,
        hit_of=5,
        hit_ut=1,
        pit_p=9,
        pit_sp=0,
        pit_rp=0,
        bench=6,
        minors=0,
        ir=0,
        ip_min=0.0,
        ip_max=None,
        two_way="sum",
        start_year=2026,
        recent_projections=3,
        roto_category_settings={
            "roto_hit_hr": True,
            "roto_hit_sb": False,
            "roto_pit_k": True,
            "roto_pit_sv": False,
        },
        roto_hitter_fields=(
            ("roto_hit_hr", "HR", True),
            ("roto_hit_sb", "SB", True),
        ),
        roto_pitcher_fields=(
            ("roto_pit_k", "K", True),
            ("roto_pit_sv", "SV", True),
        ),
        coerce_bool_fn=lambda value, default=False: bool(default if value is None else value),
    )

    assert list(out["Player"]) == ["Test Player"]
    settings_kwargs = calls["settings_kwargs"]
    assert isinstance(settings_kwargs, dict)
    assert settings_kwargs["hitter_categories"] == ("HR",)
    assert settings_kwargs["pitcher_categories"] == ("K",)

    calculate_args = calls["calculate_args"]
    assert isinstance(calculate_args, dict)
    assert calculate_args["league_settings"] == {"kind": "fake-settings"}
    assert calculate_args["start_year"] == 2026
    assert calculate_args["recent_projections"] == 3
