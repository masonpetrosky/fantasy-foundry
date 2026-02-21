import pandas as pd

from backend.core.runtime_projection_helpers import (
    coerce_meta_years,
    position_tokens,
    projection_freshness_payload,
    value_col_sort_key,
    with_player_identity_keys,
)


def test_coerce_meta_years_filters_invalid_entries():
    assert coerce_meta_years({"years": [2027, "2026", "oops", None, 2027]}) == [2026, 2027]


def test_value_col_sort_key_prefers_numeric_value_suffixes():
    keys = ["Value_2030", "Value_total", "Value_2027"]
    assert sorted(keys, key=value_col_sort_key) == ["Value_2027", "Value_2030", "Value_total"]


def test_position_tokens_splits_multiple_delimiters():
    assert position_tokens("1B/3B, OF") == {"1B", "3B", "OF"}


def test_projection_freshness_payload_counts_valid_dates():
    payload = projection_freshness_payload(
        bat_rows=[
            {"OldestProjectionDate": "2025-01-01"},
            {"OldestProjectionDate": ""},
        ],
        pit_rows=[
            {"OldestProjectionDate": "2024-12-31"},
        ],
    )
    assert payload["oldest_projection_date"] == "2024-12-31"
    assert payload["newest_projection_date"] == "2025-01-01"
    assert payload["rows_with_projection_date"] == 2
    assert payload["total_rows"] == 3
    assert payload["date_coverage_pct"] == 66.7


def test_with_player_identity_keys_adds_expected_fields():
    bat, pit = with_player_identity_keys(
        bat_records=[{"Player": "John Doe", "Team": "NYY", "Year": 2026}],
        pit_records=[{"Player": "Jane Doe", "Team": "BOS", "Year": 2027}],
    )

    assert bat[0]["PlayerKey"] == "john-doe"
    assert bat[0]["PlayerEntityKey"] == "john-doe"
    assert pit[0]["PlayerKey"] == "jane-doe"
    assert pit[0]["PlayerEntityKey"] == "jane-doe"


def test_projection_date_parsing_adapter_returns_datetime_series():
    from backend.core.runtime_projection_helpers import parse_projection_dates

    parsed = parse_projection_dates(pd.Series(["2025-01-01", "not-a-date"]))
    assert str(parsed.iloc[0].date()) == "2025-01-01"
    assert pd.isna(parsed.iloc[1])
