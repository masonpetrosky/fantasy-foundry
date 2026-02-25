import unittest

import backend.app as app_module


class DynastyYearParsingTests(unittest.TestCase):
    def test_parse_dynasty_years_supports_ranges(self) -> None:
        parsed = app_module._parse_dynasty_years("2028, 2026-2027, bad, 2030-2029")
        self.assertEqual(parsed, [2026, 2027, 2028, 2029, 2030])

    def test_parse_dynasty_years_filters_unknown_years(self) -> None:
        parsed = app_module._parse_dynasty_years("2025-2028,2030", valid_years=[2026, 2028, 2029])
        self.assertEqual(parsed, [2026, 2028])

    def test_resolve_projection_year_filter_accepts_years_only(self) -> None:
        resolved = app_module._resolve_projection_year_filter(
            year=None,
            years="2026,2028-2029",
            valid_years=[2026, 2027, 2028, 2029],
        )
        self.assertSetEqual(resolved or set(), {2026, 2028, 2029})

    def test_resolve_projection_year_filter_intersects_with_single_year(self) -> None:
        resolved = app_module._resolve_projection_year_filter(
            year=2028,
            years="2026-2027,2028",
            valid_years=[2026, 2027, 2028],
        )
        self.assertSetEqual(resolved or set(), {2028})

    def test_resolve_projection_year_filter_returns_empty_set_for_invalid_years_token(self) -> None:
        resolved = app_module._resolve_projection_year_filter(
            year=None,
            years="bad-token",
            valid_years=[2026, 2027, 2028],
        )
        self.assertEqual(resolved, set())


class YearCoercionTests(unittest.TestCase):
    def test_coerce_record_year_handles_numeric_types(self) -> None:
        self.assertEqual(app_module._coerce_record_year(2026), 2026)
        self.assertEqual(app_module._coerce_record_year(2026.0), 2026)
        self.assertEqual(app_module._coerce_record_year("2026"), 2026)
        self.assertEqual(app_module._coerce_record_year("2026.0"), 2026)

    def test_coerce_record_year_rejects_invalid_values(self) -> None:
        self.assertIsNone(app_module._coerce_record_year("2026.5"))
        self.assertIsNone(app_module._coerce_record_year("not-a-year"))
        self.assertIsNone(app_module._coerce_record_year(True))


