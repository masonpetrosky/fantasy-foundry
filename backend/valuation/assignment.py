"""Assignment helpers for valuation slot assignment."""

from __future__ import annotations

import re
from importlib.util import find_spec
from typing import Callable, Dict, List, Set, Tuple

import numpy as np
import pandas as pd

from .positions import (
    eligible_hit_slots,
    parse_hit_positions,
    parse_pit_positions,
)

# NOTE: probing a submodule via find_spec("scipy.optimize") raises when scipy
# itself is not installed, so we guard on the package first.
if find_spec("scipy") is not None and find_spec("scipy.optimize") is not None:
    from scipy.optimize import linear_sum_assignment  # type: ignore

    HAVE_SCIPY = True
else:
    HAVE_SCIPY = False
    linear_sum_assignment = None


def expand_slot_counts(per_team: Dict[str, int], n_teams: int) -> Dict[str, int]:
    return {slot: cnt * n_teams for slot, cnt in per_team.items()}


def build_slot_list(slot_counts: Dict[str, int]) -> List[str]:
    slots: List[str] = []
    for slot, count in slot_counts.items():
        slots.extend([slot] * count)
    return slots


def build_team_slot_template(per_team: Dict[str, int]) -> List[str]:
    slots: List[str] = []
    for slot, count in per_team.items():
        slots.extend([slot] * count)
    return slots


def validate_assigned_slots(
    assigned: pd.DataFrame,
    slot_counts: Dict[str, int],
    elig_sets: List[Set[str]],
    mode_label: str,
) -> None:
    """Ensure slot assignment is complete and eligibility-valid with clear diagnostics."""
    if assigned.empty and sum(slot_counts.values()) == 0:
        return

    idx_col = "_assign_idx"
    if idx_col not in assigned.columns:
        raise ValueError(f"{mode_label} assignment missing internal index column '{idx_col}'.")

    bad_rows: List[Tuple[str, str]] = []
    for player_idx, slot, player in zip(
        assigned[idx_col].to_numpy(dtype=int),
        assigned["AssignedSlot"].astype(str).to_numpy(),
        assigned.get("Player", pd.Series(["<unknown>"] * len(assigned))).astype(str).to_numpy(),
    ):
        if player_idx < 0 or player_idx >= len(elig_sets) or slot not in elig_sets[player_idx]:
            bad_rows.append((player, slot))

    if bad_rows:
        preview = ", ".join([f"{player}->{slot}" for player, slot in bad_rows[:5]])
        raise ValueError(
            f"{mode_label} assignment produced ineligible player-slot mappings. "
            f"Examples: {preview}. Check position eligibility and slot settings."
        )

    actual_counts = assigned["AssignedSlot"].value_counts().to_dict()
    missing = {
        slot: need - int(actual_counts.get(slot, 0))
        for slot, need in slot_counts.items()
        if int(actual_counts.get(slot, 0)) < need
    }
    if missing:
        details = ", ".join([f"{slot}: short {short}" for slot, short in sorted(missing.items())])
        raise ValueError(f"{mode_label} assignment cannot fill required slots ({details}).")


def assign_players_to_slots(
    df: pd.DataFrame,
    slot_counts: Dict[str, int],
    eligible_func: Callable[[Set[str]], Set[str]],
    weight_col: str = "weight",
) -> pd.DataFrame:
    """
    Choose exactly (sum slot_counts) distinct players and assign each to a slot
    to maximize total weight.
    - Uses Hungarian algorithm if scipy is available.
    - Falls back to a reasonable greedy method if not.
    """
    df = df.copy().reset_index(drop=True)
    df["_assign_idx"] = np.arange(len(df))

    slots = build_slot_list(slot_counts)
    n_slots = len(slots)
    if n_slots == 0:
        return df.iloc[0:0].copy()

    weights = df[weight_col].to_numpy(dtype=float)
    n_players = len(df)

    if n_players < n_slots:
        raise ValueError(f"Not enough players ({n_players}) to fill required slots ({n_slots}).")

    elig_sets: List[Set[str]] = []
    parse_func = parse_hit_positions if eligible_func == eligible_hit_slots else parse_pit_positions
    for pos_str in df["Pos"]:
        elig_sets.append(eligible_func(parse_func(pos_str)))

    for slot, req in slot_counts.items():
        elig_count = sum(1 for eligible in elig_sets if slot in eligible)
        if elig_count < req:
            raise ValueError(
                f"Cannot fill slot '{slot}': need {req} eligible players but only found {elig_count}."
            )

    if HAVE_SCIPY:
        BIG = 1e6
        cost = np.full((n_slots, n_players), BIG, dtype=float)
        for slot_idx, slot in enumerate(slots):
            for player_idx in range(n_players):
                if slot in elig_sets[player_idx]:
                    cost[slot_idx, player_idx] = -weights[player_idx]
        row_ind, col_ind = linear_sum_assignment(cost)  # type: ignore

        chosen_cost = cost[row_ind, col_ind]
        infeasible_rows = row_ind[chosen_cost >= (BIG / 2.0)]
        if len(infeasible_rows) > 0:
            missing: Dict[str, int] = {}
            for row_idx in infeasible_rows:
                slot = slots[int(row_idx)]
                missing[slot] = missing.get(slot, 0) + 1
            details = ", ".join([f"{slot}: short {short}" for slot, short in sorted(missing.items())])
            raise ValueError(f"Common mode assignment cannot fill required slots ({details}).")

        assigned = df.loc[col_ind].copy()
        assigned["AssignedSlot"] = [slots[i] for i in row_ind]
        validate_assigned_slots(assigned, slot_counts, elig_sets, mode_label="Common mode")
        return assigned.drop(columns=["_assign_idx"])

    # Greedy fallback (works, but not globally optimal).
    remaining = set(range(n_players))

    # Fill scarcer slots first (fewer eligible players).
    slot_order = sorted(
        range(n_slots),
        key=lambda i: sum(1 for player_idx in remaining if slots[i] in elig_sets[player_idx]),
    )

    chosen: List[Tuple[int, str]] = []
    for i in slot_order:
        slot = slots[i]
        candidates = [player_idx for player_idx in remaining if slot in elig_sets[player_idx]]
        if not candidates:
            continue
        best = max(candidates, key=lambda player_idx: weights[player_idx])
        remaining.remove(best)
        chosen.append((best, slot))

    assigned = df.loc[[player_idx for player_idx, _ in chosen]].copy()
    assigned["AssignedSlot"] = [slot for _, slot in chosen]
    validate_assigned_slots(assigned, slot_counts, elig_sets, mode_label="Common mode")
    return assigned.drop(columns=["_assign_idx"])


SLOT_SHORTAGE_RE = re.compile(r"Cannot fill slot '([^']+)': need (\d+) eligible players but only found (\d+)\.")
ASSIGN_SHORT_RE = re.compile(r"([A-Za-z0-9]+): short (\d+)")
NOT_ENOUGH_PLAYERS_RE = re.compile(r"Not enough players \((\d+)\) to fill required slots \((\d+)\)\.")
VACANCY_WEIGHT = -1e5


def _infer_slot_shortages_from_assignment_error(message: str, slot_counts: Dict[str, int]) -> Dict[str, int]:
    shortages: Dict[str, int] = {}

    slot_match = SLOT_SHORTAGE_RE.search(message)
    if slot_match:
        slot = slot_match.group(1)
        need = int(slot_match.group(2))
        found = int(slot_match.group(3))
        if slot in slot_counts and need > found:
            shortages[slot] = need - found
        return shortages

    if "cannot fill required slots" in message.lower():
        for slot, short_text in ASSIGN_SHORT_RE.findall(message):
            short = int(short_text)
            if slot in slot_counts and short > 0:
                shortages[slot] = shortages.get(slot, 0) + short
        if shortages:
            return shortages

    count_match = NOT_ENOUGH_PLAYERS_RE.search(message)
    if count_match:
        available = int(count_match.group(1))
        required = int(count_match.group(2))
        short = max(required - available, 0)
        if short > 0:
            if slot_counts.get("UT", 0) > 0:
                shortages["UT"] = short
            elif slot_counts.get("P", 0) > 0:
                shortages["P"] = short
            else:
                fallback_slot = max(slot_counts.items(), key=lambda item: int(item[1]))[0]
                shortages[fallback_slot] = short

    return shortages


def _build_vacancy_rows(
    *,
    year: int,
    side_label: str,
    shortages: Dict[str, int],
    stat_cols: List[str],
    weight_col: str,
    existing_cols: List[str],
    existing_count: int,
    attempt: int,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for slot, short in shortages.items():
        for _ in range(int(short)):
            idx = existing_count + len(rows) + 1
            row: Dict[str, object] = {
                "Player": f"__VACANT_{side_label.upper()}_{year}_{slot}_{attempt}_{idx}",
                "Year": year,
                "Team": "VAC",
                "Age": 0,
                "Pos": slot,
                weight_col: VACANCY_WEIGHT,
            }
            for stat_col in stat_cols:
                row[stat_col] = 0.0
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=existing_cols)

    out = pd.DataFrame(rows)
    for col in existing_cols:
        if col not in out.columns:
            out[col] = np.nan
    return out[existing_cols]


def assign_players_to_slots_with_vacancy_fill(
    df: pd.DataFrame,
    slot_counts: Dict[str, int],
    eligible_func: Callable[[Set[str]], Set[str]],
    *,
    stat_cols: List[str],
    year: int,
    side_label: str,
    weight_col: str = "weight",
    max_attempts: int = 8,
) -> pd.DataFrame:
    """Assign players, auto-filling unfillable slots with zero-value vacancy rows."""
    working = df.copy()
    if weight_col not in working.columns:
        working[weight_col] = 0.0

    for attempt in range(1, max_attempts + 1):
        try:
            return assign_players_to_slots(
                working,
                slot_counts,
                eligible_func,
                weight_col=weight_col,
            )
        except ValueError as exc:
            shortages = _infer_slot_shortages_from_assignment_error(str(exc), slot_counts)
            if not shortages:
                raise
            vacancy_rows = _build_vacancy_rows(
                year=year,
                side_label=side_label,
                shortages=shortages,
                stat_cols=stat_cols,
                weight_col=weight_col,
                existing_cols=list(working.columns),
                existing_count=len(working),
                attempt=attempt,
            )
            if vacancy_rows.empty:
                raise
            vacancy_rows = vacancy_rows.dropna(axis=1, how="all")
            working = pd.concat([working, vacancy_rows], ignore_index=True, sort=False)

    return assign_players_to_slots(
        working,
        slot_counts,
        eligible_func,
        weight_col=weight_col,
    )


__all__ = [
    "HAVE_SCIPY",
    "expand_slot_counts",
    "build_slot_list",
    "build_team_slot_template",
    "validate_assigned_slots",
    "assign_players_to_slots",
    "assign_players_to_slots_with_vacancy_fill",
]
