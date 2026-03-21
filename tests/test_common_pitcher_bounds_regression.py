import unittest

import pytest

from backend.dynasty_roto_values import (
    CommonDynastyRotoSettings,
    _active_common_pitch_categories,
    _apply_low_volume_non_ratio_positive_guard,
    _apply_low_volume_ratio_guard,
    common_apply_pitching_bounds,
)
from backend.runtime import _calculate_common_dynasty_frame_cached

pytestmark = pytest.mark.valuation


class CommonPitcherBoundsRegressionTests(unittest.TestCase):
    def test_active_common_pitch_categories_includes_native_qa3(self) -> None:
        lg = CommonDynastyRotoSettings(pitcher_categories=("W", "K", "ERA", "WHIP", "QA3", "SVH"))
        active = _active_common_pitch_categories(lg)
        self.assertEqual(active, ["W", "K", "ERA", "WHIP", "QA3", "SVH"])

    def test_active_common_pitch_categories_allows_qs_and_qa3_together(self) -> None:
        lg = CommonDynastyRotoSettings(pitcher_categories=("W", "K", "ERA", "WHIP", "QS", "QA3", "SVH"))
        active = _active_common_pitch_categories(lg)
        self.assertEqual(active, ["W", "K", "ERA", "WHIP", "QS", "QA3", "SVH"])

    def test_common_apply_pitching_bounds_does_not_backfill_under_cap(self) -> None:
        lg = CommonDynastyRotoSettings(ip_min=0.0, ip_max=200.0)
        totals = {
            "IP": 100.0,
            "W": 10.0,
            "QS": 8.0,
            "QA3": 9.0,
            "K": 120.0,
            "SV": 2.0,
            "SVH": 7.0,
            "ER": 40.0,
            "H": 92.0,
            "BB": 28.0,
        }
        rep_rates = {
            "W": 0.05,
            "QS": 0.04,
            "QA3": 0.045,
            "K": 0.9,
            "SV": 0.01,
            "SVH": 0.02,
            "ER": 0.5,
            "H": 0.95,
            "BB": 0.3,
        }

        filled = common_apply_pitching_bounds(totals, lg, rep_rates, fill_to_ip_max=True, enforce_ip_min=True)
        unfilled = common_apply_pitching_bounds(totals, lg, rep_rates, fill_to_ip_max=False, enforce_ip_min=True)

        self.assertAlmostEqual(float(filled["IP"]), 100.0, places=6)
        self.assertAlmostEqual(float(unfilled["IP"]), 100.0, places=6)
        self.assertAlmostEqual(float(filled["W"]), float(unfilled["W"]), places=6)
        self.assertAlmostEqual(float(filled["QA3"]), float(unfilled["QA3"]), places=6)

    def test_low_volume_ratio_guard_scales_positive_ratio_credit(self) -> None:
        delta = {"ERA": 1.2, "WHIP": 0.6, "K": 0.4}
        _apply_low_volume_ratio_guard(
            delta,
            pit_categories=["W", "K", "ERA", "WHIP"],
            pitcher_ip=20.0,
            slot_ip_reference=80.0,
        )
        self.assertEqual(float(delta["ERA"]), 0.0)
        self.assertEqual(float(delta["WHIP"]), 0.0)
        self.assertEqual(float(delta["K"]), 0.4)

        mid_volume_delta = {"ERA": 1.3, "WHIP": 0.65, "K": 0.3}
        _apply_low_volume_ratio_guard(
            mid_volume_delta,
            pit_categories=["W", "K", "ERA", "WHIP"],
            pitcher_ip=44.0,
            slot_ip_reference=80.0,
        )
        expected_scale = (0.55 - 0.35) / (1.0 - 0.35)
        self.assertAlmostEqual(float(mid_volume_delta["ERA"]), 1.3 * expected_scale, places=6)
        self.assertAlmostEqual(float(mid_volume_delta["WHIP"]), 0.65 * expected_scale, places=6)
        self.assertEqual(float(mid_volume_delta["K"]), 0.3)

        high_volume_delta = {"ERA": 1.2, "WHIP": 0.6}
        _apply_low_volume_ratio_guard(
            high_volume_delta,
            pit_categories=["ERA", "WHIP"],
            pitcher_ip=80.0,
            slot_ip_reference=80.0,
        )
        self.assertEqual(float(high_volume_delta["ERA"]), 1.2)
        self.assertEqual(float(high_volume_delta["WHIP"]), 0.6)

    def test_low_volume_non_ratio_guard_scales_positive_counting_credit(self) -> None:
        delta = {"W": 1.4, "K": 2.1, "SVH": 0.8, "ERA": 1.2, "WHIP": 0.4}
        _apply_low_volume_non_ratio_positive_guard(
            delta,
            pit_categories=["W", "K", "SVH", "ERA", "WHIP"],
            pitcher_ip=20.0,
            slot_ip_reference=80.0,
        )
        self.assertEqual(float(delta["W"]), 0.0)
        self.assertEqual(float(delta["K"]), 0.0)
        self.assertEqual(float(delta["SVH"]), 0.0)
        self.assertEqual(float(delta["ERA"]), 1.2)
        self.assertEqual(float(delta["WHIP"]), 0.4)

    @pytest.mark.full_regression
    def test_low_ip_regression_kollar_does_not_rank_above_lodolo(self) -> None:
        _calculate_common_dynasty_frame_cached.cache_clear()
        settings = {
            "roto_hit_r": True,
            "roto_hit_rbi": True,
            "roto_hit_hr": True,
            "roto_hit_sb": True,
            "roto_hit_avg": True,
            "roto_hit_obp": False,
            "roto_hit_slg": False,
            "roto_hit_ops": True,
            "roto_hit_h": False,
            "roto_hit_bb": False,
            "roto_hit_2b": False,
            "roto_hit_tb": False,
            "roto_pit_w": True,
            "roto_pit_k": True,
            "roto_pit_sv": False,
            "roto_pit_era": True,
            "roto_pit_whip": True,
            "roto_pit_qs": False,
            "roto_pit_qa3": True,
            "roto_pit_svh": True,
        }
        out = _calculate_common_dynasty_frame_cached(
            teams=12,
            sims=40,
            horizon=10,
            discount=0.94,
            hit_c=2,
            hit_1b=1,
            hit_2b=1,
            hit_3b=1,
            hit_ss=1,
            hit_ci=1,
            hit_mi=1,
            hit_of=5,
            hit_ut=1,
            pit_p=3,
            pit_sp=3,
            pit_rp=3,
            bench=15,
            minors=20,
            ir=8,
            ip_min=1000.0,
            ip_max=1500.0,
            two_way="sum",
            start_year=2026,
            **settings,
        )
        rows = out.set_index("PlayerEntityKey")
        kollar_value = float(rows.loc["jared-kollar", "DynastyValue"])
        lodolo_value = float(rows.loc["nick-lodolo", "DynastyValue"])
        self.assertLessEqual(kollar_value, lodolo_value)

    @pytest.mark.full_regression
    def test_low_ip_regression_kollar_does_not_rank_above_reynaldo_lopez(self) -> None:
        _calculate_common_dynasty_frame_cached.cache_clear()
        settings = {
            "roto_hit_r": True,
            "roto_hit_rbi": True,
            "roto_hit_hr": True,
            "roto_hit_sb": True,
            "roto_hit_avg": True,
            "roto_hit_obp": False,
            "roto_hit_slg": False,
            "roto_hit_ops": True,
            "roto_hit_h": False,
            "roto_hit_bb": False,
            "roto_hit_2b": False,
            "roto_hit_tb": False,
            "roto_pit_w": True,
            "roto_pit_k": True,
            "roto_pit_sv": False,
            "roto_pit_era": True,
            "roto_pit_whip": True,
            "roto_pit_qs": False,
            "roto_pit_qa3": True,
            "roto_pit_svh": True,
        }
        out = _calculate_common_dynasty_frame_cached(
            teams=12,
            sims=300,
            horizon=20,
            discount=0.94,
            hit_c=2,
            hit_1b=1,
            hit_2b=1,
            hit_3b=1,
            hit_ss=1,
            hit_ci=1,
            hit_mi=1,
            hit_of=5,
            hit_ut=1,
            pit_p=3,
            pit_sp=3,
            pit_rp=3,
            bench=15,
            minors=20,
            ir=8,
            ip_min=1000.0,
            ip_max=1500.0,
            two_way="sum",
            start_year=2026,
            **settings,
        )
        rows = out.set_index("PlayerEntityKey")
        kollar_value = float(rows.loc["jared-kollar", "DynastyValue"])
        lopez_value = float(rows.loc["reynaldo-lopez", "DynastyValue"])
        self.assertLessEqual(kollar_value, lopez_value)


if __name__ == "__main__":
    unittest.main()
