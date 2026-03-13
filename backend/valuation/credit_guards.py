"""Playing-time and low-volume credit guard functions for valuation."""

from __future__ import annotations

from typing import Dict, List, Set

import pandas as pd

COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}


def _coerce_non_negative_float(value: object) -> float:
    """Best-effort numeric coercion for IP/share guards."""
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return 0.0
    return float(max(number, 0.0))


def _positive_credit_scale(
    *,
    player_volume: float,
    slot_volume_reference: float,
    min_share_for_positive_credit: float = 0.35,
    full_share_for_positive_credit: float = 1.00,
) -> float:
    """Return a [0, 1] positive-credit scale based on projected workload share."""
    slot_volume = _coerce_non_negative_float(slot_volume_reference)
    player_workload = _coerce_non_negative_float(player_volume)
    if slot_volume <= 0.0:
        return 1.0

    share = player_workload / slot_volume
    min_share = float(min_share_for_positive_credit)
    full_share = float(full_share_for_positive_credit)

    if full_share <= min_share:
        return 1.0 if share >= full_share else 0.0
    if share <= min_share:
        return 0.0
    if share >= full_share:
        return 1.0
    return float((share - min_share) / (full_share - min_share))


def _low_volume_positive_credit_scale(
    *,
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> float:
    """Return a [0, 1] positive-credit scale based on projected innings share."""
    return _positive_credit_scale(
        player_volume=pitcher_ip,
        slot_volume_reference=slot_ip_reference,
        min_share_for_positive_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_credit=full_share_for_positive_ratio_credit,
    )


def _apply_low_volume_non_ratio_positive_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    """Scale positive non-ratio pitching category credit for tiny workloads."""
    scale = _low_volume_positive_credit_scale(
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )
    if scale >= 1.0:
        return

    for cat in pit_categories:
        if cat in COMMON_REVERSED_PITCH_CATS:
            continue
        if float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


def _apply_low_volume_ratio_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    """Scale positive ERA/WHIP credit based on projected innings share."""
    scale = _low_volume_positive_credit_scale(
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )
    if scale >= 1.0:
        return

    for cat in COMMON_REVERSED_PITCH_CATS:
        if cat in pit_categories and float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


def _apply_hitter_playing_time_reliability_guard(
    delta: Dict[str, float],
    *,
    hit_categories: List[str],
    hitter_ab: float,
    slot_ab_reference: float,
    min_share_for_positive_credit: float = 0.35,
    full_share_for_positive_credit: float = 1.00,
) -> None:
    """Scale positive hitter category credit for low projected AB workloads."""
    scale = _positive_credit_scale(
        player_volume=hitter_ab,
        slot_volume_reference=slot_ab_reference,
        min_share_for_positive_credit=min_share_for_positive_credit,
        full_share_for_positive_credit=full_share_for_positive_credit,
    )
    if scale >= 1.0:
        return
    for cat in hit_categories:
        if float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


def _apply_pitcher_playing_time_reliability_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_credit: float = 0.35,
    full_share_for_positive_credit: float = 1.00,
) -> None:
    """Scale positive pitching category credit for low projected IP workloads."""
    scale = _positive_credit_scale(
        player_volume=pitcher_ip,
        slot_volume_reference=slot_ip_reference,
        min_share_for_positive_credit=min_share_for_positive_credit,
        full_share_for_positive_credit=full_share_for_positive_credit,
    )
    if scale >= 1.0:
        return
    for cat in pit_categories:
        if float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale
