from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cmp_to_key, lru_cache
from typing import Any, Literal, Optional

import pandas as pd
from fastapi import HTTPException

ProjectionDataset = Literal["all", "bat", "pitch"]
PROJECTION_HITTER_CORE_EXPORT_COLS: tuple[str, ...] = ("AB", "R", "HR", "RBI", "SB", "AVG", "OPS")
PROJECTION_PITCHER_CORE_EXPORT_COLS: tuple[str, ...] = ("IP", "W", "K", "SV", "ERA", "WHIP", "QS")


@dataclass(slots=True)
class ProjectionServiceContext:
    refresh_data_if_needed: callable
    get_bat_data: callable
    get_pit_data: callable
    get_meta: callable
    normalize_player_key: callable
    resolve_projection_year_filter: callable
    parse_dynasty_years: callable
    attach_dynasty_values: callable
    coerce_meta_years: callable
    tabular_export_response: callable
    player_key_col: str
    player_entity_key_col: str
    position_token_split_re: re.Pattern[str]
    position_display_order: tuple[str, ...]
    projection_text_sort_cols: set[str]
    all_tab_hitter_stat_cols: tuple[str, ...]
    all_tab_pitch_stat_cols: tuple[str, ...]
    projection_query_cache_maxsize: int
    filter_records: callable | None = None


class ProjectionService:
    """Projection query pipeline with cached filtering/sorting/aggregation."""

    def __init__(self, ctx: ProjectionServiceContext):
        self._ctx = ctx

        @lru_cache(maxsize=ctx.projection_query_cache_maxsize)
        def cached_projection_rows(
            dataset: Literal["bat", "pitch"],
            player: str,
            team: str,
            player_keys: str,
            year: int | None,
            years: str,
            pos: str,
            include_dynasty: bool,
            dynasty_years: str,
            career_totals: bool,
        ) -> tuple[dict, ...]:
            valid_years = ctx.coerce_meta_years(ctx.get_meta())
            requested_years = ctx.resolve_projection_year_filter(year, years or None, valid_years=valid_years)
            records = ctx.get_bat_data() if dataset == "bat" else ctx.get_pit_data()
            filter_impl = ctx.filter_records or self.filter_records
            filtered = filter_impl(
                records,
                player or None,
                team or None,
                requested_years,
                pos or None,
                self._parse_player_keys_filter(player_keys),
            )
            if career_totals:
                filtered = self._aggregate_projection_career_rows(filtered, is_hitter=(dataset == "bat"))
            if include_dynasty:
                filtered = ctx.attach_dynasty_values(
                    filtered,
                    ctx.parse_dynasty_years(dynasty_years or None, valid_years=valid_years),
                )
            return tuple(filtered)

        @lru_cache(maxsize=ctx.projection_query_cache_maxsize)
        def cached_all_projection_rows(
            player: str,
            team: str,
            player_keys: str,
            year: int | None,
            years: str,
            pos: str,
            include_dynasty: bool,
            dynasty_years: str,
            career_totals: bool,
        ) -> tuple[dict, ...]:
            valid_years = ctx.coerce_meta_years(ctx.get_meta())
            requested_years = ctx.resolve_projection_year_filter(year, years or None, valid_years=valid_years)
            player_key_filter = self._parse_player_keys_filter(player_keys)
            filter_impl = ctx.filter_records or self.filter_records
            hit_filtered = filter_impl(
                ctx.get_bat_data(),
                player or None,
                team or None,
                requested_years,
                None,
                player_key_filter,
            )
            pit_filtered = filter_impl(
                ctx.get_pit_data(),
                player or None,
                team or None,
                requested_years,
                None,
                player_key_filter,
            )
            merged = (
                self._aggregate_all_projection_career_rows(hit_filtered, pit_filtered)
                if career_totals
                else self._merge_all_projection_rows(hit_filtered, pit_filtered)
            )
            if pos:
                requested_positions = self._position_tokens(pos)
                if requested_positions:
                    merged = [
                        row
                        for row in merged
                        if requested_positions.intersection(self._position_tokens(row.get("Pos", "")))
                    ]
            if include_dynasty:
                merged = ctx.attach_dynasty_values(
                    merged,
                    ctx.parse_dynasty_years(dynasty_years or None, valid_years=valid_years),
                )
            return tuple(merged)

        @lru_cache(maxsize=4)
        def projection_sortable_columns_for_dataset(dataset: ProjectionDataset) -> frozenset[str]:
            if dataset == "bat":
                base_records = ctx.get_bat_data()
            elif dataset == "pitch":
                base_records = ctx.get_pit_data()
            else:
                base_records = list(ctx.get_bat_data()) + list(ctx.get_pit_data())

            cols: set[str] = {
                "Player",
                "Team",
                "Pos",
                "Year",
                "Years",
                "YearStart",
                "YearEnd",
                "Age",
                "ProjectionsUsed",
                "OldestProjectionDate",
                "DynastyValue",
                "DynastyMatchStatus",
                ctx.player_key_col,
                ctx.player_entity_key_col,
            }
            if dataset == "all":
                cols.update({"Type", "PitH", "PitHR", "PitBB"})

            for record in base_records:
                cols.update(record.keys())

            for year in ctx.coerce_meta_years(ctx.get_meta()):
                cols.add(f"Value_{year}")

            return frozenset(cols)

        self._cached_projection_rows = cached_projection_rows
        self._cached_all_projection_rows = cached_all_projection_rows
        self._projection_sortable_columns_for_dataset = projection_sortable_columns_for_dataset

    def clear_caches(self) -> None:
        self._cached_projection_rows.cache_clear()
        self._cached_all_projection_rows.cache_clear()
        self._projection_sortable_columns_for_dataset.cache_clear()

    def _coerce_record_year(self, value: object) -> int | None:
        """Normalize JSON year values from int/float/string to int for robust filtering."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed = float(text)
            except ValueError:
                return None
            return int(parsed) if parsed.is_integer() else None
        return None

    def _position_tokens(self, value: object) -> set[str]:
        text = str(value or "").strip().upper()
        if not text:
            return set()
        return {token for token in self._ctx.position_token_split_re.split(text) if token}

    def _normalize_player_keys_filter(self, value: str | None) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        tokens = sorted({token.strip().lower() for token in re.split(r"[\s,]+", text) if token.strip()})
        return ",".join(tokens)

    def _parse_player_keys_filter(self, value: str | None) -> set[str] | None:
        normalized = self._normalize_player_keys_filter(value)
        if not normalized:
            return None
        return {token for token in normalized.split(",") if token}

    def _row_player_filter_keys(self, row: dict) -> set[str]:
        keys: set[str] = set()
        entity_key = str(row.get(self._ctx.player_entity_key_col) or "").strip().lower()
        if entity_key:
            keys.add(entity_key)
        player_key = str(row.get(self._ctx.player_key_col) or "").strip().lower()
        if player_key:
            keys.add(player_key)
        return keys

    @staticmethod
    def _normalize_filter_value(value: str | None) -> str:
        return (value or "").strip()

    @staticmethod
    def _value_col_sort_key(col: str) -> tuple[int, int | str]:
        suffix = col.split("_", 1)[1] if "_" in col else col
        return (0, int(suffix)) if str(suffix).isdigit() else (1, suffix)

    @staticmethod
    def _ordered_unique(cols: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for col in cols:
            name = str(col or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return out

    def _parse_export_columns(self, value: str | None) -> list[str]:
        if not value:
            return []
        tokens = [token.strip() for token in str(value).split(",")]
        return self._ordered_unique([token for token in tokens if token])

    def _default_projection_export_columns(
        self,
        rows: list[dict],
        *,
        dataset: ProjectionDataset,
        career_totals: bool,
    ) -> list[str]:
        available = self._ordered_unique([str(key) for row in rows if isinstance(row, dict) for key in row.keys()])
        if not available:
            return ["Player", "Team", "Pos", "Age", "DynastyValue"]

        available_set = set(available)
        season_col = "Years" if career_totals else "Year"
        dynasty_cols = sorted(
            [col for col in available if col.startswith("Value_")],
            key=self._value_col_sort_key,
        )
        identity_cols = ["Player", "Team", "Pos", "Age", "DynastyValue"]

        if dataset == "bat":
            desired = self._ordered_unique(
                [
                    *identity_cols,
                    *PROJECTION_HITTER_CORE_EXPORT_COLS,
                    *dynasty_cols,
                    "OBP",
                    "G",
                    "H",
                    "2B",
                    "3B",
                    "BB",
                    "SO",
                    "ProjectionsUsed",
                    "OldestProjectionDate",
                    season_col,
                ]
            )
        elif dataset == "pitch":
            desired = self._ordered_unique(
                [
                    *identity_cols,
                    *PROJECTION_PITCHER_CORE_EXPORT_COLS,
                    *dynasty_cols,
                    "G",
                    "GS",
                    "L",
                    "BB",
                    "H",
                    "HR",
                    "ER",
                    "SVH",
                    "ProjectionsUsed",
                    "OldestProjectionDate",
                    season_col,
                ]
            )
        else:
            desired = self._ordered_unique(
                [
                    *identity_cols,
                    *PROJECTION_HITTER_CORE_EXPORT_COLS,
                    *PROJECTION_PITCHER_CORE_EXPORT_COLS,
                    *dynasty_cols,
                    "OBP",
                    "G",
                    "H",
                    "2B",
                    "3B",
                    "BB",
                    "SO",
                    "GS",
                    "L",
                    "PitBB",
                    "PitH",
                    "PitHR",
                    "ER",
                    "SVH",
                    "ProjectionsUsed",
                    "OldestProjectionDate",
                    season_col,
                    "Type",
                ]
            )

        return [col for col in desired if col in available_set]

    def _position_sort_key(self, token: str) -> tuple[int, str]:
        order_map = {pos: idx for idx, pos in enumerate(self._ctx.position_display_order)}
        return (order_map.get(token, len(order_map)), token)

    @staticmethod
    def _row_team_value(row: dict) -> str:
        return str(row.get("Team") or row.get("MLBTeam") or "").strip()

    def _projection_merge_key(self, row: dict) -> tuple[str, object, str]:
        player = str(
            row.get(self._ctx.player_entity_key_col)
            or row.get(self._ctx.player_key_col)
            or row.get("Player", "")
        ).strip()
        parsed_year = self._coerce_record_year(row.get("Year"))
        merge_year: object = parsed_year if parsed_year is not None else str(row.get("Year", "")).strip()
        team = self._row_team_value(row).upper()
        return player, merge_year, team

    def _merge_position_value(self, hit_pos: object, pit_pos: object) -> str | None:
        tokens = self._position_tokens(hit_pos) | self._position_tokens(pit_pos)
        if tokens:
            return "/".join(sorted(tokens, key=self._position_sort_key))
        hit_text = str(hit_pos or "").strip()
        if hit_text:
            return hit_text
        pit_text = str(pit_pos or "").strip()
        return pit_text or None

    @staticmethod
    def _max_projection_count(*values: object) -> int | None:
        counts: list[int] = []
        for value in values:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if pd.isna(parsed):
                continue
            counts.append(int(round(parsed)))
        return max(counts) if counts else None

    @staticmethod
    def _oldest_projection_date(*values: object) -> str | None:
        oldest_ts: pd.Timestamp | None = None
        oldest_text: str | None = None

        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            parsed = pd.to_datetime(text, errors="coerce")
            if pd.isna(parsed):
                continue
            if oldest_ts is None or parsed < oldest_ts:
                oldest_ts = parsed
                oldest_text = text

        if oldest_text is not None:
            return oldest_text

        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _coerce_numeric(value: object) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(parsed):
            return None
        return parsed

    def _career_group_key(self, row: dict) -> str:
        player_name = str(row.get("Player", "")).strip()
        player_key = str(row.get(self._ctx.player_key_col) or "").strip() or self._ctx.normalize_player_key(player_name)
        return str(row.get(self._ctx.player_entity_key_col) or "").strip() or player_key

    def _rows_year_bounds(self, rows: list[dict]) -> tuple[int | None, int | None]:
        years: list[int] = []
        for row in rows:
            parsed = self._coerce_record_year(row.get("Year"))
            if parsed is not None:
                years.append(parsed)
        if not years:
            return None, None
        return min(years), max(years)

    @staticmethod
    def _format_year_span(start_year: int | None, end_year: int | None) -> str | None:
        if start_year is None or end_year is None:
            return None
        return str(start_year) if start_year == end_year else f"{start_year}-{end_year}"

    @staticmethod
    def _weighted_rate(rows: list[dict], rate_col: str, weight_col: str) -> float | None:
        weighted_total = 0.0
        weight_total = 0.0
        for row in rows:
            rate = ProjectionService._coerce_numeric(row.get(rate_col))
            weight = ProjectionService._coerce_numeric(row.get(weight_col))
            if rate is None or weight is None or weight <= 0:
                continue
            weighted_total += rate * weight
            weight_total += weight
        if weight_total <= 0:
            return None
        return weighted_total / weight_total

    def _aggregate_projection_career_rows(self, rows: list[dict], *, is_hitter: bool) -> list[dict]:
        if not rows:
            return []

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(self._career_group_key(row), []).append(row)

        excluded_from_sum = {
            "Player",
            "Team",
            "MLBTeam",
            "Pos",
            "Type",
            "Year",
            "Age",
            "ProjectionsUsed",
            "OldestProjectionDate",
            "DynastyValue",
            "DynastyMatchStatus",
            "Years",
            "YearStart",
            "YearEnd",
            self._ctx.player_key_col,
            self._ctx.player_entity_key_col,
        }

        aggregated_rows: list[dict] = []
        for entity_key, player_rows in grouped.items():
            latest_row = player_rows[0]
            latest_year = self._coerce_record_year(latest_row.get("Year"))
            for row in player_rows[1:]:
                row_year = self._coerce_record_year(row.get("Year"))
                if row_year is None and latest_year is None:
                    latest_row = row
                    continue
                if row_year is None:
                    continue
                if latest_year is None or row_year >= latest_year:
                    latest_row = row
                    latest_year = row_year

            aggregated = dict(latest_row)
            player_name = str(latest_row.get("Player", "")).strip()
            player_key = str(latest_row.get(self._ctx.player_key_col) or "").strip() or self._ctx.normalize_player_key(player_name)
            aggregated[self._ctx.player_key_col] = player_key
            aggregated[self._ctx.player_entity_key_col] = entity_key or player_key

            team_value = self._row_team_value(latest_row)
            if not team_value:
                for row in player_rows:
                    team_value = self._row_team_value(row)
                    if team_value:
                        break
            if team_value:
                aggregated["Team"] = team_value

            position_tokens: set[str] = set()
            for row in player_rows:
                position_tokens.update(self._position_tokens(row.get("Pos")))
            if position_tokens:
                aggregated["Pos"] = "/".join(sorted(position_tokens, key=self._position_sort_key))

            ages = [age for age in (self._coerce_numeric(row.get("Age")) for row in player_rows) if age is not None]
            if ages:
                aggregated["Age"] = int(round(min(ages)))

            year_start, year_end = self._rows_year_bounds(player_rows)
            aggregated["Year"] = None
            aggregated["YearStart"] = year_start
            aggregated["YearEnd"] = year_end
            aggregated["Years"] = self._format_year_span(year_start, year_end)

            # In career totals mode, ProjectionsUsed should represent the number of
            # projection queries behind each season snapshot (e.g., 1-3), not a sum
            # across every projected year.
            projection_count = self._max_projection_count(*(row.get("ProjectionsUsed") for row in player_rows))
            if projection_count is not None:
                aggregated["ProjectionsUsed"] = projection_count
            aggregated["OldestProjectionDate"] = self._oldest_projection_date(
                *(row.get("OldestProjectionDate") for row in player_rows)
            )

            stat_totals: dict[str, float] = {}
            for row in player_rows:
                for key, value in row.items():
                    if key in excluded_from_sum or key.startswith("Value_"):
                        continue
                    numeric = self._coerce_numeric(value)
                    if numeric is None:
                        continue
                    stat_totals[key] = stat_totals.get(key, 0.0) + numeric

            for key, value in stat_totals.items():
                aggregated[key] = value

            if is_hitter:
                h = self._coerce_numeric(aggregated.get("H"))
                ab = self._coerce_numeric(aggregated.get("AB"))
                if h is not None and ab is not None and ab > 0:
                    aggregated["AVG"] = h / ab
                else:
                    weighted_avg = self._weighted_rate(player_rows, "AVG", "AB")
                    if weighted_avg is not None:
                        aggregated["AVG"] = weighted_avg

                b2 = self._coerce_numeric(aggregated.get("2B"))
                b3 = self._coerce_numeric(aggregated.get("3B"))
                hr = self._coerce_numeric(aggregated.get("HR"))
                bb = self._coerce_numeric(aggregated.get("BB"))
                hbp = self._coerce_numeric(aggregated.get("HBP"))
                sf = self._coerce_numeric(aggregated.get("SF"))
                if (
                    h is not None
                    and b2 is not None
                    and b3 is not None
                    and hr is not None
                    and bb is not None
                    and hbp is not None
                    and ab is not None
                    and sf is not None
                    and ab > 0
                ):
                    tb = h + b2 + 2.0 * b3 + 3.0 * hr
                    obp_den = ab + bb + hbp + sf
                    if obp_den > 0:
                        obp = (h + bb + hbp) / obp_den
                        slg = tb / ab
                        aggregated["OBP"] = obp
                        aggregated["OPS"] = obp + slg
                    else:
                        weighted_obp = self._weighted_rate(player_rows, "OBP", "AB")
                        if weighted_obp is not None:
                            aggregated["OBP"] = weighted_obp
                else:
                    weighted_obp = self._weighted_rate(player_rows, "OBP", "AB")
                    if weighted_obp is not None:
                        aggregated["OBP"] = weighted_obp
                    weighted_ops = self._weighted_rate(player_rows, "OPS", "AB")
                    if weighted_ops is not None:
                        aggregated["OPS"] = weighted_ops
            else:
                svh = self._coerce_numeric(aggregated.get("SVH"))
                if svh is None:
                    sv = self._coerce_numeric(aggregated.get("SV"))
                    hld = self._coerce_numeric(aggregated.get("HLD"))
                    if sv is not None and hld is not None:
                        aggregated["SVH"] = sv + hld
                    elif sv is not None:
                        aggregated["SVH"] = sv

                qs = self._coerce_numeric(aggregated.get("QS"))
                if qs is None:
                    qa3 = self._coerce_numeric(aggregated.get("QA3"))
                    if qa3 is not None:
                        aggregated["QS"] = qa3

                er = self._coerce_numeric(aggregated.get("ER"))
                ip = self._coerce_numeric(aggregated.get("IP"))
                if er is not None and ip is not None and ip > 0:
                    aggregated["ERA"] = (9.0 * er) / ip
                else:
                    weighted_era = self._weighted_rate(player_rows, "ERA", "IP")
                    if weighted_era is not None:
                        aggregated["ERA"] = weighted_era

                h = self._coerce_numeric(aggregated.get("H"))
                bb = self._coerce_numeric(aggregated.get("BB"))
                if h is not None and bb is not None and ip is not None and ip > 0:
                    aggregated["WHIP"] = (h + bb) / ip
                else:
                    weighted_whip = self._weighted_rate(player_rows, "WHIP", "IP")
                    if weighted_whip is not None:
                        aggregated["WHIP"] = weighted_whip

            aggregated_rows.append(aggregated)

        return aggregated_rows

    def _aggregate_all_projection_career_rows(self, hit_rows: list[dict], pit_rows: list[dict]) -> list[dict]:
        if not hit_rows and not pit_rows:
            return []

        hit_aggregated = self._aggregate_projection_career_rows(hit_rows, is_hitter=True)
        pit_aggregated = self._aggregate_projection_career_rows(pit_rows, is_hitter=False)

        hit_by_key = {self._career_group_key(row): row for row in hit_aggregated}
        pit_by_key = {self._career_group_key(row): row for row in pit_aggregated}

        ordered_keys: list[str] = []
        seen: set[str] = set()
        for row in list(hit_rows) + list(pit_rows):
            key = self._career_group_key(row)
            if key in seen:
                continue
            seen.add(key)
            ordered_keys.append(key)
        if not ordered_keys:
            ordered_keys = list(dict.fromkeys(list(hit_by_key.keys()) + list(pit_by_key.keys())))

        merged_rows: list[dict] = []
        for key in ordered_keys:
            hit = hit_by_key.get(key)
            pit = pit_by_key.get(key)
            if not hit and not pit:
                continue

            source = hit or pit or {}
            merged = dict(source)

            merged["Type"] = "H/P" if hit and pit else ("H" if hit else "P")
            merged["Team"] = self._row_team_value(hit or {}) or self._row_team_value(pit or {})
            merged["Pos"] = self._merge_position_value((hit or {}).get("Pos"), (pit or {}).get("Pos"))
            merged["Age"] = (hit or {}).get("Age")
            if merged["Age"] is None:
                merged["Age"] = (pit or {}).get("Age")

            year_start_candidates = [
                parsed
                for value in (
                    (hit or {}).get("YearStart"),
                    (pit or {}).get("YearStart"),
                    (hit or {}).get("Year"),
                    (pit or {}).get("Year"),
                )
                if (parsed := self._coerce_record_year(value)) is not None
            ]
            year_end_candidates = [
                parsed
                for value in (
                    (hit or {}).get("YearEnd"),
                    (pit or {}).get("YearEnd"),
                    (hit or {}).get("Year"),
                    (pit or {}).get("Year"),
                )
                if (parsed := self._coerce_record_year(value)) is not None
            ]
            year_start = min(year_start_candidates) if year_start_candidates else None
            year_end = max(year_end_candidates) if year_end_candidates else None
            merged["Year"] = None
            merged["YearStart"] = year_start
            merged["YearEnd"] = year_end
            merged["Years"] = self._format_year_span(year_start, year_end)

            projection_total = self._max_projection_count(
                (hit or {}).get("ProjectionsUsed"),
                (pit or {}).get("ProjectionsUsed"),
            )
            if projection_total is not None:
                merged["ProjectionsUsed"] = projection_total
            merged["OldestProjectionDate"] = self._oldest_projection_date(
                (hit or {}).get("OldestProjectionDate"),
                (pit or {}).get("OldestProjectionDate"),
            )

            # In the all-rows view, unprefixed hitting fields always represent hitter stats.
            for col in self._ctx.all_tab_hitter_stat_cols:
                merged[col] = (hit or {}).get(col)

            # Pitching fields are kept separately, including prefixed collision stats.
            for col in self._ctx.all_tab_pitch_stat_cols:
                merged[col] = (pit or {}).get(col)
            merged["PitH"] = (pit or {}).get("H")
            merged["PitHR"] = (pit or {}).get("HR")
            merged["PitBB"] = (pit or {}).get("BB")

            merged_rows.append(merged)

        return merged_rows

    @staticmethod
    def _normalize_sort_dir(value: str | None) -> Literal["asc", "desc"]:
        return "asc" if str(value or "").strip().lower() == "asc" else "desc"

    def _validate_sort_col(self, sort_col: str | None, *, dataset: ProjectionDataset) -> str | None:
        normalized = self._normalize_filter_value(sort_col)
        if not normalized:
            return None
        allowed = self._projection_sortable_columns_for_dataset(dataset)
        if normalized not in allowed:
            sample = ", ".join(sorted(list(allowed))[:20])
            raise HTTPException(
                status_code=422,
                detail=f"sort_col '{normalized}' is not supported for {dataset}. Example valid columns: {sample}",
            )
        return normalized

    def _sort_projection_rows(self, rows: list[dict], sort_col: str | None, sort_dir: str | None) -> list[dict]:
        col = str(sort_col or "").strip()
        if not col:
            return rows

        direction = self._normalize_sort_dir(sort_dir)

        text_cols = self._ctx.projection_text_sort_cols | {
            self._ctx.player_key_col,
            self._ctx.player_entity_key_col,
            "DynastyMatchStatus",
        }

        def _cmp_for_col(a: dict, b: dict, compare_col: str, compare_dir: Literal["asc", "desc"]) -> int:
            av = a.get(compare_col)
            bv = b.get(compare_col)

            if compare_col == "OldestProjectionDate":
                av_ts = pd.to_datetime(av, errors="coerce")
                bv_ts = pd.to_datetime(bv, errors="coerce")
                av_missing = pd.isna(av_ts)
                bv_missing = pd.isna(bv_ts)
                if av_missing and bv_missing:
                    return 0
                if av_missing:
                    return 1
                if bv_missing:
                    return -1
                av_num = float(av_ts.value)
                bv_num = float(bv_ts.value)
                if av_num == bv_num:
                    return 0
                cmp = -1 if av_num < bv_num else 1
                return cmp if compare_dir == "asc" else -cmp

            if compare_col in text_cols:
                av_text = str(av or "").strip()
                bv_text = str(bv or "").strip()
                if not av_text and not bv_text:
                    return 0
                if not av_text:
                    return 1
                if not bv_text:
                    return -1
                av_norm = av_text.casefold()
                bv_norm = bv_text.casefold()
                if av_norm == bv_norm:
                    return 0
                cmp = -1 if av_norm < bv_norm else 1
                return cmp if compare_dir == "asc" else -cmp

            try:
                av_num = float(av)
            except (TypeError, ValueError):
                av_num = float("-inf")
            try:
                bv_num = float(bv)
            except (TypeError, ValueError):
                bv_num = float("-inf")
            if pd.isna(av_num):
                av_num = float("-inf")
            if pd.isna(bv_num):
                bv_num = float("-inf")
            if av_num == bv_num:
                return 0
            cmp = -1 if av_num < bv_num else 1
            return cmp if compare_dir == "asc" else -cmp

        def _cmp(a: dict, b: dict) -> int:
            primary = _cmp_for_col(a, b, col, direction)
            if primary != 0:
                return primary

            # Deterministic tie-breakers keep page boundaries stable across requests.
            for tie_col in (self._ctx.player_entity_key_col, "Player", "Year", "Team"):
                tie_result = _cmp_for_col(a, b, tie_col, "asc")
                if tie_result != 0:
                    return tie_result
            return 0

        return sorted(rows, key=cmp_to_key(_cmp))

    def _merge_all_projection_rows(self, hit_rows: list[dict], pit_rows: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, object, str], dict[str, dict | None]] = {}
        ordered_keys: list[tuple[str, object, str]] = []

        for side, rows in (("H", hit_rows), ("P", pit_rows)):
            for row in rows:
                key = self._projection_merge_key(row)
                if key not in grouped:
                    grouped[key] = {"hit": None, "pit": None}
                    ordered_keys.append(key)
                if side == "H":
                    grouped[key]["hit"] = row
                else:
                    grouped[key]["pit"] = row

        merged_rows: list[dict] = []
        for key in ordered_keys:
            bucket = grouped[key]
            hit = bucket.get("hit")
            pit = bucket.get("pit")

            source = hit or pit or {}
            merged = dict(source)

            merged["Type"] = "H/P" if hit and pit else ("H" if hit else "P")
            merged["Team"] = self._row_team_value(hit or {}) or self._row_team_value(pit or {})
            merged["Pos"] = self._merge_position_value((hit or {}).get("Pos"), (pit or {}).get("Pos"))
            merged["Age"] = (hit or {}).get("Age")
            if merged["Age"] is None:
                merged["Age"] = (pit or {}).get("Age")

            max_used = self._max_projection_count((hit or {}).get("ProjectionsUsed"), (pit or {}).get("ProjectionsUsed"))
            if max_used is not None:
                merged["ProjectionsUsed"] = max_used
            merged["OldestProjectionDate"] = self._oldest_projection_date(
                (hit or {}).get("OldestProjectionDate"),
                (pit or {}).get("OldestProjectionDate"),
            )

            # In the all-rows view, unprefixed hitting fields always represent hitter stats.
            for col in self._ctx.all_tab_hitter_stat_cols:
                merged[col] = (hit or {}).get(col)

            # Pitching fields are kept separately, including prefixed collision stats.
            for col in self._ctx.all_tab_pitch_stat_cols:
                merged[col] = (pit or {}).get(col)
            merged["PitH"] = (pit or {}).get("H")
            merged["PitHR"] = (pit or {}).get("HR")
            merged["PitBB"] = (pit or {}).get("BB")

            merged_rows.append(merged)

        return merged_rows

    def filter_records(
        self,
        records: list[dict],
        player: str | None,
        team: str | None,
        years: set[int] | None,
        pos: str | None,
        player_keys: set[str] | None = None,
    ) -> list[dict]:
        out = records
        if player:
            q = player.strip().lower()
            out = [r for r in out if q in str(r.get("Player", "")).lower()]
        if team:
            team_normalized = team.strip().lower()
            out = [
                r
                for r in out
                if str(r.get("Team", "")).strip().lower() == team_normalized
                or str(r.get("MLBTeam", "")).strip().lower() == team_normalized
            ]
        if years is not None:
            out = [r for r in out if self._coerce_record_year(r.get("Year")) in years]
        if pos:
            requested_positions = self._position_tokens(pos)
            if requested_positions:
                out = [
                    r for r in out if requested_positions.intersection(self._position_tokens(r.get("Pos", "")))
                ]
        if player_keys:
            out = [r for r in out if player_keys.intersection(self._row_player_filter_keys(r))]
        return out

    def _get_projection_rows(
        self,
        dataset: Literal["bat", "pitch"],
        *,
        player: str | None,
        team: str | None,
        player_keys: str | None,
        year: int | None,
        years: str | None,
        pos: str | None,
        include_dynasty: bool,
        dynasty_years: str | None,
        career_totals: bool,
        sort_col: str | None,
        sort_dir: str | None,
    ) -> tuple[dict, ...]:
        cached_rows = self._cached_projection_rows(
            dataset,
            self._normalize_filter_value(player),
            self._normalize_filter_value(team),
            self._normalize_player_keys_filter(player_keys),
            year,
            self._normalize_filter_value(years),
            self._normalize_filter_value(pos),
            include_dynasty,
            self._normalize_filter_value(dynasty_years),
            career_totals,
        )
        sorted_rows = self._sort_projection_rows(
            list(cached_rows),
            self._normalize_filter_value(sort_col),
            self._normalize_sort_dir(sort_dir),
        )
        return tuple(sorted_rows)

    def _get_all_projection_rows(
        self,
        *,
        player: str | None,
        team: str | None,
        player_keys: str | None,
        year: int | None,
        years: str | None,
        pos: str | None,
        include_dynasty: bool,
        dynasty_years: str | None,
        career_totals: bool,
        sort_col: str | None,
        sort_dir: str | None,
    ) -> tuple[dict, ...]:
        cached_rows = self._cached_all_projection_rows(
            self._normalize_filter_value(player),
            self._normalize_filter_value(team),
            self._normalize_player_keys_filter(player_keys),
            year,
            self._normalize_filter_value(years),
            self._normalize_filter_value(pos),
            include_dynasty,
            self._normalize_filter_value(dynasty_years),
            career_totals,
        )
        sorted_rows = self._sort_projection_rows(
            list(cached_rows),
            self._normalize_filter_value(sort_col),
            self._normalize_sort_dir(sort_dir),
        )
        return tuple(sorted_rows)

    def projection_response(
        self,
        dataset: ProjectionDataset,
        *,
        player: str | None,
        team: str | None,
        player_keys: str | None,
        year: int | None,
        years: str | None,
        pos: str | None,
        dynasty_years: str | None,
        career_totals: bool,
        include_dynasty: bool,
        sort_col: str | None,
        sort_dir: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        self._ctx.refresh_data_if_needed()
        validated_sort_col = self._validate_sort_col(sort_col, dataset=dataset)
        filter_kwargs = dict(
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            include_dynasty=include_dynasty,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            sort_col=validated_sort_col,
            sort_dir=sort_dir,
        )
        if dataset == "all":
            filtered = self._get_all_projection_rows(**filter_kwargs)
        else:
            filtered = self._get_projection_rows(dataset, **filter_kwargs)
        total = len(filtered)
        page = list(filtered[offset : offset + limit])
        return {"total": total, "offset": offset, "limit": limit, "data": page}

    def export_projections(
        self,
        dataset: ProjectionDataset,
        file_format: Literal["csv", "xlsx"] = "csv",
        player: Optional[str] = None,
        team: Optional[str] = None,
        player_keys: Optional[str] = None,
        year: Optional[int] = None,
        years: Optional[str] = None,
        pos: Optional[str] = None,
        dynasty_years: Optional[str] = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        sort_col: Optional[str] = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        columns: Optional[str] = None,
    ):
        self._ctx.refresh_data_if_needed()
        validated_sort_col = self._validate_sort_col(sort_col, dataset=dataset)
        if dataset == "all":
            rows = list(
                self._get_all_projection_rows(
                    player=player,
                    team=team,
                    player_keys=player_keys,
                    year=year,
                    years=years,
                    pos=pos,
                    include_dynasty=include_dynasty,
                    dynasty_years=dynasty_years,
                    career_totals=career_totals,
                    sort_col=validated_sort_col,
                    sort_dir=sort_dir,
                )
            )
        else:
            rows = list(
                self._get_projection_rows(
                    dataset,
                    player=player,
                    team=team,
                    player_keys=player_keys,
                    year=year,
                    years=years,
                    pos=pos,
                    include_dynasty=include_dynasty,
                    dynasty_years=dynasty_years,
                    career_totals=career_totals,
                    sort_col=validated_sort_col,
                    sort_dir=sort_dir,
                )
            )

        requested_export_columns = self._parse_export_columns(columns)
        default_export_columns = self._default_projection_export_columns(
            rows,
            dataset=dataset,
            career_totals=career_totals,
        )
        return self._ctx.tabular_export_response(
            rows,
            filename_base=f"projections-{dataset}",
            file_format=file_format,
            selected_columns=requested_export_columns,
            default_columns=default_export_columns,
            required_columns=["Player"],
            disallowed_columns=[
                self._ctx.player_key_col,
                self._ctx.player_entity_key_col,
                "DynastyMatchStatus",
                "RawDynastyValue",
                "minor_eligible",
            ],
        )
