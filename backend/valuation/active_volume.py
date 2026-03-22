"""Shared active-volume allocation helpers for hitter and pitcher usage."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from hashlib import blake2b

_SEASON_CAPACITY_PER_SLOT = 162.0
_SYNTHETIC_SEASON_DAYS = 182
_SYNTHETIC_PERIOD_DAYS = 7
_VOLUME_SCALE = 10.0
_QUALITY_SCALE = 1000.0
_EPSILON = 1e-9
SYNTHETIC_SEASON_DAYS = _SYNTHETIC_SEASON_DAYS
SYNTHETIC_PERIOD_DAYS = _SYNTHETIC_PERIOD_DAYS


@dataclass(slots=True)
class _FlowEdge:
    to: int
    rev: int
    capacity: int
    cost: int


@dataclass(slots=True)
class VolumeEntry:
    player_id: str
    projected_volume: float
    quality: float
    slots: set[str]
    year: int | None = None


@dataclass(slots=True)
class UsageAllocation:
    usage_share_by_player: dict[str, float]
    assigned_volume_by_player: dict[str, float]
    assigned_volume_by_player_slot: dict[str, dict[str, float]]
    slot_capacity: dict[str, float]
    slot_assigned_volume: dict[str, float]
    total_requested_volume: float
    total_assigned_volume: float
    total_capacity: float


@dataclass(slots=True)
class DailyUsageDetail:
    allocation: UsageAllocation
    assigned_by_day_slot: dict[int, dict[str, float]]
    day_membership_by_player: dict[str, set[int]]


@dataclass(slots=True)
class PitcherUsageAllocation:
    usage_share_by_player: dict[str, float]
    assigned_appearances_by_player: dict[str, float]
    assigned_starts_by_player: dict[str, float]
    assigned_non_start_appearances_by_player: dict[str, float]
    slot_capacity: dict[str, float]
    slot_assigned_starts: dict[str, float]
    slot_assigned_non_starts: dict[str, float]
    total_requested_appearances: float
    total_assigned_appearances: float
    total_requested_starts: float
    total_assigned_starts: float
    total_assigned_non_start_appearances: float
    capped_start_budget: float | None
    selected_held_starts: float | None = None
    selected_streamed_starts: float | None = None
    selected_overflow_starts: float | None = None
    effective_period_start_cap: float | None = None
    streaming_adds_per_period: int | None = None


@dataclass(slots=True)
class PitcherInningsAllocation:
    ip_usage_share_by_player: dict[str, float]
    assigned_ip_by_player: dict[str, float]
    total_requested_ip: float
    total_assigned_ip: float
    ip_budget: float | None
    ip_cap_binding: bool
    unused_ip: float | None
    trimmed_ip: float


@dataclass(slots=True)
class _DailyAllocationResult:
    allocation: UsageAllocation
    assigned_by_day_slot: dict[int, dict[str, float]]


@dataclass(slots=True)
class _CappedStartSelectionResult:
    selected_start_days_by_player: dict[str, set[int]]
    selected_held_starts: float | None
    selected_streamed_starts: float | None
    selected_overflow_starts: float | None
    effective_period_start_cap: float | None


def annual_slot_capacity(
    slot_counts: dict[str, int],
    *,
    teams: int,
    season_capacity_per_slot: float = _SEASON_CAPACITY_PER_SLOT,
) -> dict[str, float]:
    teams_count = max(int(teams), 1)
    per_slot = max(float(season_capacity_per_slot), 0.0)
    return {
        str(slot): float(max(int(count), 0) * teams_count) * per_slot
        for slot, count in sorted(slot_counts.items())
        if int(count) > 0
    }


def allocate_hitter_usage_daily(
    entries: list[VolumeEntry],
    *,
    slot_capacity: dict[str, float],
    total_days: int = _SYNTHETIC_SEASON_DAYS,
) -> UsageAllocation:
    return allocate_hitter_usage_daily_detail(
        entries,
        slot_capacity=slot_capacity,
        total_days=total_days,
    ).allocation


def allocate_hitter_usage_daily_detail(
    entries: list[VolumeEntry],
    *,
    slot_capacity: dict[str, float],
    total_days: int = _SYNTHETIC_SEASON_DAYS,
) -> DailyUsageDetail:
    normalized_entries = _normalize_entries(entries)
    day_membership_by_player = _build_day_membership_by_player(
        normalized_entries,
        tag="hit-active",
        total_days=total_days,
    )
    allocation_result = _allocate_daily_entries(
        normalized_entries,
        slot_capacity=slot_capacity,
        day_membership_by_player=day_membership_by_player,
        total_days=total_days,
        side="hitter",
    )
    return DailyUsageDetail(
        allocation=allocation_result.allocation,
        assigned_by_day_slot=allocation_result.assigned_by_day_slot,
        day_membership_by_player=day_membership_by_player,
    )


def allocate_hitter_usage_daily_to_day_slot_capacity(
    entries: list[VolumeEntry],
    *,
    day_slot_capacity: dict[int, dict[str, int]],
    total_days: int = _SYNTHETIC_SEASON_DAYS,
) -> DailyUsageDetail:
    normalized_entries = _normalize_entries(entries)
    day_membership_by_player = _build_day_membership_by_player(
        normalized_entries,
        tag="hit-active",
        total_days=total_days,
    )
    allocation_result = _allocate_daily_entries(
        normalized_entries,
        slot_capacity={},
        day_membership_by_player=day_membership_by_player,
        total_days=total_days,
        side="hitter",
        day_slot_capacity=day_slot_capacity,
    )
    return DailyUsageDetail(
        allocation=allocation_result.allocation,
        assigned_by_day_slot=allocation_result.assigned_by_day_slot,
        day_membership_by_player=day_membership_by_player,
    )


def allocate_pitcher_usage_daily(
    entries: list[VolumeEntry],
    *,
    start_volume_by_player: dict[str, float],
    slot_capacity: dict[str, float],
    capped_start_budget: float | None,
    held_player_ids: set[str] | None = None,
    streaming_adds_per_period: int | None = None,
    allow_same_day_starts_overflow: bool = False,
    total_days: int = _SYNTHETIC_SEASON_DAYS,
    period_days: int = _SYNTHETIC_PERIOD_DAYS,
) -> PitcherUsageAllocation:
    normalized_entries = _normalize_entries(entries)
    held_ids = {str(player_id).strip() for player_id in (held_player_ids or set()) if str(player_id).strip()}
    start_days_by_player: dict[str, set[int]] = {}
    non_start_days_by_player: dict[str, set[int]] = {}
    total_requested_starts = 0.0

    for entry in normalized_entries:
        appearance_count = _coerce_daily_event_count(entry.projected_volume, total_days=total_days)
        start_count = min(
            _coerce_daily_event_count(start_volume_by_player.get(entry.player_id, 0.0), total_days=total_days),
            appearance_count,
        )
        year = entry.year
        start_days = set(
            _generate_synthetic_days(
                player_id=entry.player_id,
                year=year,
                count=start_count,
                tag="pit-start",
                total_days=total_days,
            )
        )
        non_start_days = set(
            _generate_synthetic_days(
                player_id=entry.player_id,
                year=year,
                count=max(appearance_count - start_count, 0),
                tag="pit-appearance",
                total_days=total_days,
                reserved_days=start_days,
            )
        )
        start_days_by_player[entry.player_id] = start_days
        non_start_days_by_player[entry.player_id] = non_start_days
        total_requested_starts += float(start_count)

    selected_start_days_result = (
        _cap_start_days_by_period(
            normalized_entries,
            start_days_by_player=start_days_by_player,
            capped_start_budget=capped_start_budget,
            slot_capacity=slot_capacity,
            held_player_ids=held_ids,
            streaming_adds_per_period=streaming_adds_per_period,
            allow_same_day_starts_overflow=allow_same_day_starts_overflow,
            total_days=total_days,
            period_days=period_days,
        )
        if capped_start_budget is not None
        or streaming_adds_per_period is not None
        or held_ids
        else _CappedStartSelectionResult(
            selected_start_days_by_player={player_id: set(days) for player_id, days in start_days_by_player.items()},
            selected_held_starts=None,
            selected_streamed_starts=None,
            selected_overflow_starts=None,
            effective_period_start_cap=None,
        )
    )
    selected_start_days_by_player = selected_start_days_result.selected_start_days_by_player
    selected_held_starts = selected_start_days_result.selected_held_starts
    selected_streamed_starts = selected_start_days_result.selected_streamed_starts
    selected_overflow_starts = selected_start_days_result.selected_overflow_starts
    effective_period_start_cap = selected_start_days_result.effective_period_start_cap

    start_entries = [
        VolumeEntry(
            player_id=entry.player_id,
            projected_volume=float(len(selected_start_days_by_player.get(entry.player_id, set()))),
            quality=float(entry.quality),
            slots=set(entry.slots),
            year=entry.year,
        )
        for entry in normalized_entries
        if selected_start_days_by_player.get(entry.player_id)
    ]
    start_allocation = _allocate_daily_entries(
        start_entries,
        slot_capacity=slot_capacity,
        day_membership_by_player=selected_start_days_by_player,
        total_days=total_days,
        side="pitcher",
    )

    non_start_entries = [
        VolumeEntry(
            player_id=entry.player_id,
            projected_volume=float(len(non_start_days_by_player.get(entry.player_id, set()))),
            quality=float(entry.quality),
            slots=set(entry.slots),
            year=entry.year,
        )
        for entry in normalized_entries
        if non_start_days_by_player.get(entry.player_id)
    ]
    non_start_allocation = _allocate_daily_entries(
        non_start_entries,
        slot_capacity=slot_capacity,
        day_membership_by_player=non_start_days_by_player,
        total_days=total_days,
        side="pitcher",
        preassigned_by_day_slot=start_allocation.assigned_by_day_slot,
    )

    usage_share_by_player: dict[str, float] = {}
    assigned_appearances_by_player: dict[str, float] = {}
    assigned_starts_by_player: dict[str, float] = {}
    assigned_non_start_appearances_by_player: dict[str, float] = {}

    for entry in normalized_entries:
        projected_volume = max(float(entry.projected_volume), 0.0)
        assigned_starts = float(start_allocation.allocation.assigned_volume_by_player.get(entry.player_id, 0.0))
        assigned_non_starts = float(non_start_allocation.allocation.assigned_volume_by_player.get(entry.player_id, 0.0))
        assigned_total = assigned_starts + assigned_non_starts
        assigned_starts_by_player[entry.player_id] = assigned_starts
        assigned_non_start_appearances_by_player[entry.player_id] = assigned_non_starts
        assigned_appearances_by_player[entry.player_id] = assigned_total
        usage_share_by_player[entry.player_id] = (
            min(assigned_total / projected_volume, 1.0) if projected_volume > _EPSILON else 0.0
        )

    return PitcherUsageAllocation(
        usage_share_by_player=usage_share_by_player,
        assigned_appearances_by_player=assigned_appearances_by_player,
        assigned_starts_by_player=assigned_starts_by_player,
        assigned_non_start_appearances_by_player=assigned_non_start_appearances_by_player,
        slot_capacity={slot: float(capacity) for slot, capacity in slot_capacity.items()},
        slot_assigned_starts=dict(start_allocation.allocation.slot_assigned_volume),
        slot_assigned_non_starts=dict(non_start_allocation.allocation.slot_assigned_volume),
        total_requested_appearances=float(sum(float(entry.projected_volume) for entry in normalized_entries)),
        total_assigned_appearances=float(sum(assigned_appearances_by_player.values())),
        total_requested_starts=float(total_requested_starts),
        total_assigned_starts=float(start_allocation.allocation.total_assigned_volume),
        total_assigned_non_start_appearances=float(non_start_allocation.allocation.total_assigned_volume),
        capped_start_budget=None if capped_start_budget is None else float(max(capped_start_budget, 0.0)),
        selected_held_starts=selected_held_starts,
        selected_streamed_starts=selected_streamed_starts,
        selected_overflow_starts=selected_overflow_starts,
        effective_period_start_cap=effective_period_start_cap,
        streaming_adds_per_period=(
            None if streaming_adds_per_period is None else max(int(streaming_adds_per_period), 0)
        ),
    )


def allocate_hitter_usage(
    entries: list[VolumeEntry],
    *,
    slot_capacity: dict[str, float],
) -> UsageAllocation:
    return _allocate_volume(entries, slot_capacity=slot_capacity, total_capacity=None)


def allocate_pitcher_usage(
    entries: list[VolumeEntry],
    *,
    start_volume_by_player: dict[str, float],
    slot_capacity: dict[str, float],
    capped_start_budget: float | None,
) -> PitcherUsageAllocation:
    normalized_entries = {
        entry.player_id: entry
        for entry in entries
        if entry.player_id and float(entry.projected_volume) > _EPSILON
    }

    start_entries: list[VolumeEntry] = []
    non_start_entries: list[VolumeEntry] = []
    total_requested_starts = 0.0
    for player_id, entry in normalized_entries.items():
        projected_volume = max(float(entry.projected_volume), 0.0)
        projected_starts = min(max(float(start_volume_by_player.get(player_id, 0.0)), 0.0), projected_volume)
        projected_non_starts = max(projected_volume - projected_starts, 0.0)
        total_requested_starts += projected_starts
        if projected_starts > _EPSILON:
            start_entries.append(
                VolumeEntry(
                    player_id=player_id,
                    projected_volume=projected_starts,
                    quality=float(entry.quality),
                    slots=set(entry.slots),
                )
            )
        if projected_non_starts > _EPSILON:
            non_start_entries.append(
                VolumeEntry(
                    player_id=player_id,
                    projected_volume=projected_non_starts,
                    quality=float(entry.quality),
                    slots=set(entry.slots),
                )
            )

    start_allocation = _allocate_volume(
        start_entries,
        slot_capacity=slot_capacity,
        total_capacity=capped_start_budget,
    )
    remaining_slot_capacity = {
        slot: max(float(slot_capacity.get(slot, 0.0)) - float(start_allocation.slot_assigned_volume.get(slot, 0.0)), 0.0)
        for slot in slot_capacity
    }
    non_start_allocation = _allocate_volume(
        non_start_entries,
        slot_capacity=remaining_slot_capacity,
        total_capacity=None,
    )

    usage_share_by_player: dict[str, float] = {}
    assigned_appearances_by_player: dict[str, float] = {}
    assigned_starts_by_player: dict[str, float] = {}
    assigned_non_start_appearances_by_player: dict[str, float] = {}

    for player_id, entry in normalized_entries.items():
        projected_volume = max(float(entry.projected_volume), 0.0)
        assigned_starts = float(start_allocation.assigned_volume_by_player.get(player_id, 0.0))
        assigned_non_starts = float(non_start_allocation.assigned_volume_by_player.get(player_id, 0.0))
        assigned_total = assigned_starts + assigned_non_starts
        assigned_starts_by_player[player_id] = assigned_starts
        assigned_non_start_appearances_by_player[player_id] = assigned_non_starts
        assigned_appearances_by_player[player_id] = assigned_total
        usage_share_by_player[player_id] = assigned_total / projected_volume if projected_volume > _EPSILON else 0.0

    return PitcherUsageAllocation(
        usage_share_by_player=usage_share_by_player,
        assigned_appearances_by_player=assigned_appearances_by_player,
        assigned_starts_by_player=assigned_starts_by_player,
        assigned_non_start_appearances_by_player=assigned_non_start_appearances_by_player,
        slot_capacity={slot: float(capacity) for slot, capacity in slot_capacity.items()},
        slot_assigned_starts=dict(start_allocation.slot_assigned_volume),
        slot_assigned_non_starts=dict(non_start_allocation.slot_assigned_volume),
        total_requested_appearances=float(sum(float(entry.projected_volume) for entry in normalized_entries.values())),
        total_assigned_appearances=float(sum(assigned_appearances_by_player.values())),
        total_requested_starts=float(total_requested_starts),
        total_assigned_starts=float(start_allocation.total_assigned_volume),
        total_assigned_non_start_appearances=float(non_start_allocation.total_assigned_volume),
        capped_start_budget=None if capped_start_budget is None else float(max(capped_start_budget, 0.0)),
    )


def allocate_pitcher_innings_budget(
    entries: list[VolumeEntry],
    *,
    ip_budget: float | None,
) -> PitcherInningsAllocation:
    normalized_entries = _normalize_entries(entries)
    total_requested_ip = float(sum(float(entry.projected_volume) for entry in normalized_entries))
    effective_budget = None if ip_budget is None else max(float(ip_budget), 0.0)
    slot_capacity = {"IP_CAP": max(total_requested_ip, effective_budget or 0.0)}
    allocation = _allocate_volume(
        [
            VolumeEntry(
                player_id=entry.player_id,
                projected_volume=float(entry.projected_volume),
                quality=float(entry.quality),
                slots={"IP_CAP"},
                year=entry.year,
            )
            for entry in normalized_entries
        ],
        slot_capacity=slot_capacity,
        total_capacity=effective_budget,
    )
    unused_ip = None
    if effective_budget is not None:
        unused_ip = max(effective_budget - float(allocation.total_assigned_volume), 0.0)
    return PitcherInningsAllocation(
        ip_usage_share_by_player=dict(allocation.usage_share_by_player),
        assigned_ip_by_player=dict(allocation.assigned_volume_by_player),
        total_requested_ip=total_requested_ip,
        total_assigned_ip=float(allocation.total_assigned_volume),
        ip_budget=effective_budget,
        ip_cap_binding=bool(
            effective_budget is not None and total_requested_ip > (effective_budget + _EPSILON)
        ),
        unused_ip=unused_ip,
        trimmed_ip=max(total_requested_ip - float(allocation.total_assigned_volume), 0.0),
    )


def _normalize_entries(entries: list[VolumeEntry]) -> list[VolumeEntry]:
    return [
        VolumeEntry(
            player_id=str(entry.player_id).strip(),
            projected_volume=max(float(entry.projected_volume), 0.0),
            quality=float(entry.quality),
            slots={str(slot) for slot in entry.slots if str(slot).strip()},
            year=int(entry.year) if entry.year is not None else None,
        )
        for entry in entries
        if str(entry.player_id).strip() and float(entry.projected_volume) > _EPSILON and entry.slots
    ]


def _coerce_daily_event_count(value: float, *, total_days: int) -> int:
    return max(0, min(int(round(max(float(value), 0.0))), int(total_days)))


def _stable_hash_int(*parts: object) -> int:
    digest = blake2b(
        "|".join(str(part) for part in parts).encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big", signed=False)


def _generate_synthetic_days(
    *,
    player_id: str,
    year: int | None,
    count: int,
    tag: str,
    total_days: int,
    reserved_days: set[int] | None = None,
) -> list[int]:
    reserved = set(reserved_days or set())
    available_days = max(int(total_days) - len(reserved), 0)
    target = max(0, min(int(count), available_days))
    if target <= 0:
        return []

    used = set(reserved)
    days: list[int] = []
    phase = _stable_hash_int(player_id, year or 0, tag) % max(int(total_days), 1)
    step = float(total_days) / float(target)

    for idx in range(target):
        candidate = int((float(phase) + (idx * step)) % float(total_days))
        probes = 0
        while candidate in used and probes < total_days:
            candidate = (candidate + 1) % total_days
            probes += 1
        if candidate in used:
            break
        used.add(candidate)
        days.append(candidate)

    if len(days) < target:
        for candidate in range(total_days):
            if candidate in used:
                continue
            used.add(candidate)
            days.append(candidate)
            if len(days) >= target:
                break

    return sorted(days)


def _build_day_membership_by_player(
    entries: list[VolumeEntry],
    *,
    tag: str,
    total_days: int,
) -> dict[str, set[int]]:
    day_membership_by_player: dict[str, set[int]] = {}
    for entry in entries:
        day_membership_by_player[entry.player_id] = set(
            _generate_synthetic_days(
                player_id=entry.player_id,
                year=entry.year,
                count=_coerce_daily_event_count(entry.projected_volume, total_days=total_days),
                tag=tag,
                total_days=total_days,
            )
        )
    return day_membership_by_player


def _slot_daily_capacity(
    slot_capacity: dict[str, float],
    *,
    total_days: int,
) -> dict[str, int]:
    per_day_capacity: dict[str, int] = {}
    for slot, capacity in slot_capacity.items():
        daily_capacity = int(round(float(capacity) / max(float(total_days), 1.0)))
        if daily_capacity > 0:
            per_day_capacity[str(slot)] = daily_capacity
    return per_day_capacity


def _slot_sort_key(
    slot: str,
    *,
    side: str,
    daily_capacity: dict[str, int],
    remaining_capacity: dict[str, int],
) -> tuple[int, int, int, int]:
    hitter_flex = {"UT", "CI", "MI"}
    pitcher_flex = {"P"}
    slot_order_hitter = {"C": 0, "1B": 1, "2B": 2, "3B": 3, "SS": 4, "OF": 5, "DH": 6, "CI": 7, "MI": 8, "UT": 9}
    slot_order_pitcher = {"SP": 0, "RP": 1, "P": 2}
    flex_set = hitter_flex if side == "hitter" else pitcher_flex
    slot_order = slot_order_hitter if side == "hitter" else slot_order_pitcher
    return (
        1 if slot in flex_set else 0,
        daily_capacity.get(slot, 0),
        remaining_capacity.get(slot, 0),
        slot_order.get(slot, 99),
    )


def _allocate_daily_entries(
    entries: list[VolumeEntry],
    *,
    slot_capacity: dict[str, float],
    day_membership_by_player: dict[str, set[int]],
    total_days: int,
    side: str,
    preassigned_by_day_slot: dict[int, dict[str, float]] | None = None,
    day_slot_capacity: dict[int, dict[str, int]] | None = None,
) -> _DailyAllocationResult:
    normalized_day_slot_capacity: dict[int, dict[str, int]] | None = None
    if day_slot_capacity is not None:
        normalized_day_slot_capacity = {}
        for day, slot_map in day_slot_capacity.items():
            normalized_slots = {
                str(slot): max(int(capacity), 0)
                for slot, capacity in slot_map.items()
                if int(capacity) > 0
            }
            if normalized_slots:
                normalized_day_slot_capacity[int(day)] = normalized_slots
        normalized_slot_capacity: dict[str, float] = {}
        for slot_map in normalized_day_slot_capacity.values():
            for slot, capacity in slot_map.items():
                normalized_slot_capacity[slot] = float(normalized_slot_capacity.get(slot, 0.0) + float(capacity))
    else:
        normalized_slot_capacity = {
            str(slot): max(float(capacity), 0.0)
            for slot, capacity in slot_capacity.items()
            if float(capacity) > _EPSILON
        }
    normalized_entries = [
        entry
        for entry in _normalize_entries(entries)
        if entry.slots & set(normalized_slot_capacity.keys())
    ]
    uniform_per_day_capacity = (
        None
        if normalized_day_slot_capacity is not None
        else _slot_daily_capacity(normalized_slot_capacity, total_days=total_days)
    )

    if not normalized_entries or not normalized_slot_capacity:
        return _DailyAllocationResult(
            allocation=UsageAllocation(
                usage_share_by_player={},
                assigned_volume_by_player={},
                assigned_volume_by_player_slot={},
                slot_capacity=normalized_slot_capacity,
                slot_assigned_volume={slot: 0.0 for slot in normalized_slot_capacity},
                total_requested_volume=float(sum(float(entry.projected_volume) for entry in normalized_entries)),
                total_assigned_volume=0.0,
                total_capacity=float(sum(normalized_slot_capacity.values())),
            ),
            assigned_by_day_slot={},
        )

    if normalized_day_slot_capacity is None and not uniform_per_day_capacity:
        return _DailyAllocationResult(
            allocation=UsageAllocation(
                usage_share_by_player={},
                assigned_volume_by_player={},
                assigned_volume_by_player_slot={},
                slot_capacity=normalized_slot_capacity,
                slot_assigned_volume={slot: 0.0 for slot in normalized_slot_capacity},
                total_requested_volume=float(sum(float(entry.projected_volume) for entry in normalized_entries)),
                total_assigned_volume=0.0,
                total_capacity=float(sum(normalized_slot_capacity.values())),
            ),
            assigned_by_day_slot={},
        )

    sorted_entries = sorted(
        normalized_entries,
        key=lambda entry: (-float(entry.quality), str(entry.player_id)),
    )
    day_to_entries: dict[int, list[VolumeEntry]] = {day: [] for day in range(int(total_days))}
    for entry in sorted_entries:
        days = day_membership_by_player.get(entry.player_id, set())
        for day in sorted(days):
            if 0 <= int(day) < int(total_days):
                day_to_entries[int(day)].append(entry)

    preassigned = {int(day): {str(slot): float(value) for slot, value in slot_map.items()} for day, slot_map in (preassigned_by_day_slot or {}).items()}
    assigned_volume_by_player: dict[str, float] = {}
    assigned_volume_by_player_slot: dict[str, dict[str, float]] = {}
    slot_assigned_volume: dict[str, float] = {slot: 0.0 for slot in normalized_slot_capacity}
    assigned_by_day_slot: dict[int, dict[str, float]] = {}

    for day in range(int(total_days)):
        day_preassigned = preassigned.get(day, {})
        day_capacity = (
            normalized_day_slot_capacity.get(day, {})
            if normalized_day_slot_capacity is not None
            else uniform_per_day_capacity or {}
        )
        remaining_capacity = {
            slot: max(int(day_capacity.get(slot, 0) - int(round(day_preassigned.get(slot, 0.0)))), 0)
            for slot in day_capacity
        }
        if not any(remaining_capacity.values()):
            continue

        for entry in day_to_entries.get(day, []):
            eligible_slots = [
                slot
                for slot in entry.slots
                if remaining_capacity.get(slot, 0) > 0
            ]
            if not eligible_slots:
                continue
            chosen_slot = min(
                eligible_slots,
                key=lambda slot: _slot_sort_key(
                    slot,
                    side=side,
                    daily_capacity=day_capacity,
                    remaining_capacity=remaining_capacity,
                ),
            )
            remaining_capacity[chosen_slot] -= 1
            assigned_volume_by_player[entry.player_id] = float(assigned_volume_by_player.get(entry.player_id, 0.0) + 1.0)
            assigned_volume_by_player_slot.setdefault(entry.player_id, {})
            assigned_volume_by_player_slot[entry.player_id][chosen_slot] = float(
                assigned_volume_by_player_slot[entry.player_id].get(chosen_slot, 0.0) + 1.0
            )
            slot_assigned_volume[chosen_slot] = float(slot_assigned_volume.get(chosen_slot, 0.0) + 1.0)
            assigned_by_day_slot.setdefault(day, {})
            assigned_by_day_slot[day][chosen_slot] = float(assigned_by_day_slot[day].get(chosen_slot, 0.0) + 1.0)

    usage_share_by_player = {
        entry.player_id: min(
            float(assigned_volume_by_player.get(entry.player_id, 0.0)) / max(float(entry.projected_volume), _EPSILON),
            1.0,
        )
        for entry in normalized_entries
    }

    return _DailyAllocationResult(
        allocation=UsageAllocation(
            usage_share_by_player=usage_share_by_player,
            assigned_volume_by_player=assigned_volume_by_player,
            assigned_volume_by_player_slot=assigned_volume_by_player_slot,
            slot_capacity=normalized_slot_capacity,
            slot_assigned_volume=slot_assigned_volume,
            total_requested_volume=float(sum(float(entry.projected_volume) for entry in normalized_entries)),
            total_assigned_volume=float(sum(assigned_volume_by_player.values())),
            total_capacity=float(sum(normalized_slot_capacity.values())),
        ),
        assigned_by_day_slot=assigned_by_day_slot,
    )


def _cap_start_days_by_period(
    entries: list[VolumeEntry],
    *,
    start_days_by_player: dict[str, set[int]],
    capped_start_budget: float | None,
    slot_capacity: dict[str, float],
    held_player_ids: set[str] | None,
    streaming_adds_per_period: int | None,
    allow_same_day_starts_overflow: bool,
    total_days: int,
    period_days: int,
) -> _CappedStartSelectionResult:
    if capped_start_budget is None and streaming_adds_per_period is None and not held_player_ids:
        return _CappedStartSelectionResult(
            selected_start_days_by_player={player_id: set(days) for player_id, days in start_days_by_player.items()},
            selected_held_starts=None,
            selected_streamed_starts=None,
            selected_overflow_starts=None,
            effective_period_start_cap=None,
        )

    held_ids = {str(player_id).strip() for player_id in (held_player_ids or set()) if str(player_id).strip()}
    periods = max(int(math.ceil(float(total_days) / max(int(period_days), 1))), 1)
    budget_per_period = (
        None
        if capped_start_budget is None
        else float(max(capped_start_budget, 0.0)) / float(periods)
    )
    streaming_limit_per_period = None if streaming_adds_per_period is None else max(int(streaming_adds_per_period), 0)
    selected: dict[str, set[int]] = {player_id: set() for player_id in start_days_by_player}
    sorted_entries = sorted(entries, key=lambda entry: (-float(entry.quality), str(entry.player_id)))
    daily_start_capacity = _daily_start_slot_capacity(slot_capacity, total_days=total_days)
    selected_held_starts = 0
    selected_streamed_starts = 0
    selected_overflow_starts = 0

    assigned_so_far = 0
    for period_idx in range(periods):
        allowed_this_period: int | None = None
        if capped_start_budget is not None:
            cumulative_budget = float((period_idx + 1) * float(budget_per_period or 0.0))
            allowed_this_period = max(int(math.floor(cumulative_budget + 1e-9)) - assigned_so_far, 0)
        if daily_start_capacity <= 0:
            continue
        if allowed_this_period is not None and allowed_this_period <= 0:
            continue
        period_start = period_idx * max(int(period_days), 1)
        period_end = min(period_start + max(int(period_days), 1), int(total_days))
        held_events: list[tuple[float, str, int]] = []
        stream_events: list[tuple[float, str, int]] = []
        held_events_by_day: dict[int, list[tuple[float, str, int]]] = {}
        stream_events_by_day: dict[int, list[tuple[float, str, int]]] = {}
        for entry in sorted_entries:
            player_days = start_days_by_player.get(entry.player_id, set())
            for day in sorted(day for day in player_days if period_start <= int(day) < period_end):
                event = (float(entry.quality), str(entry.player_id), int(day))
                if entry.player_id in held_ids:
                    held_events.append(event)
                    held_events_by_day.setdefault(int(day), []).append(event)
                else:
                    stream_events.append(event)
                    stream_events_by_day.setdefault(int(day), []).append(event)
        held_events.sort(key=lambda item: (-item[0], item[1], item[2]))
        stream_events.sort(key=lambda item: (-item[0], item[1], item[2]))
        for event_list in held_events_by_day.values():
            event_list.sort(key=lambda item: (-item[0], item[1], item[2]))
        for event_list in stream_events_by_day.values():
            event_list.sort(key=lambda item: (-item[0], item[1], item[2]))

        period_selected = 0
        period_streamed = 0
        day_selected_counts: dict[int, int] = {}
        selected_event_keys: set[tuple[str, str, int]] = set()

        def _try_select_event(
            source: str,
            player_id: str,
            event_day: int,
            *,
            enforce_weekly_cap: bool,
        ) -> bool:
            nonlocal period_selected, period_streamed, selected_held_starts, selected_streamed_starts
            if day_selected_counts.get(event_day, 0) >= daily_start_capacity:
                return False
            if allowed_this_period is not None and enforce_weekly_cap and period_selected >= allowed_this_period:
                return False
            if source == "stream" and streaming_limit_per_period is not None and period_streamed >= streaming_limit_per_period:
                return False
            event_key = (source, player_id, event_day)
            if event_key in selected_event_keys:
                return False
            selected_event_keys.add(event_key)
            selected.setdefault(player_id, set()).add(event_day)
            day_selected_counts[event_day] = int(day_selected_counts.get(event_day, 0) + 1)
            period_selected += 1
            if source == "held":
                selected_held_starts += 1
            else:
                selected_streamed_starts += 1
                period_streamed += 1
            return True

        for _quality, player_id, event_day in held_events:
            _try_select_event("held", player_id, event_day, enforce_weekly_cap=True)
        for _quality, player_id, event_day in stream_events:
            _try_select_event("stream", player_id, event_day, enforce_weekly_cap=True)

        if allow_same_day_starts_overflow and allowed_this_period is not None and period_selected >= allowed_this_period:
            stream_slots_remaining = (
                None
                if streaming_limit_per_period is None
                else max(int(streaming_limit_per_period) - int(period_streamed), 0)
            )
            best_overflow_day: int | None = None
            best_overflow_events: list[tuple[str, str, int]] = []
            best_overflow_quality = float("-inf")
            for day in range(period_start, period_end):
                if int(day_selected_counts.get(day, 0)) <= 0:
                    continue
                remaining_day_capacity = max(int(daily_start_capacity) - int(day_selected_counts.get(day, 0)), 0)
                if remaining_day_capacity <= 0:
                    continue
                day_overflow_events: list[tuple[str, str, int]] = []
                day_overflow_quality = 0.0
                for quality, player_id, event_day in held_events_by_day.get(day, []):
                    if remaining_day_capacity <= 0:
                        break
                    event_key = ("held", player_id, event_day)
                    if event_key in selected_event_keys:
                        continue
                    day_overflow_events.append(("held", player_id, event_day))
                    day_overflow_quality += float(quality)
                    remaining_day_capacity -= 1
                stream_slots_for_day = stream_slots_remaining
                for quality, player_id, event_day in stream_events_by_day.get(day, []):
                    if remaining_day_capacity <= 0:
                        break
                    if stream_slots_for_day is not None and stream_slots_for_day <= 0:
                        break
                    event_key = ("stream", player_id, event_day)
                    if event_key in selected_event_keys:
                        continue
                    day_overflow_events.append(("stream", player_id, event_day))
                    day_overflow_quality += float(quality)
                    remaining_day_capacity -= 1
                    if stream_slots_for_day is not None:
                        stream_slots_for_day -= 1
                if day_overflow_events and day_overflow_quality > best_overflow_quality:
                    best_overflow_day = int(day)
                    best_overflow_events = day_overflow_events
                    best_overflow_quality = float(day_overflow_quality)
            if best_overflow_day is not None:
                overflow_added = 0
                for source, player_id, event_day in best_overflow_events:
                    if _try_select_event(source, player_id, event_day, enforce_weekly_cap=False):
                        overflow_added += 1
                selected_overflow_starts += int(overflow_added)

        if allowed_this_period is not None:
            assigned_so_far += min(period_selected, allowed_this_period)

    total_selected_starts = selected_held_starts + selected_streamed_starts
    return _CappedStartSelectionResult(
        selected_start_days_by_player=selected,
        selected_held_starts=float(selected_held_starts),
        selected_streamed_starts=float(selected_streamed_starts),
        selected_overflow_starts=float(selected_overflow_starts),
        effective_period_start_cap=float(total_selected_starts) / float(periods),
    )


def _daily_start_slot_capacity(
    slot_capacity: dict[str, float],
    *,
    total_days: int,
) -> int:
    return max(
        int(
            sum(
                _slot_daily_capacity(
                    {
                        slot: capacity
                        for slot, capacity in slot_capacity.items()
                        if str(slot) in {"P", "SP"}
                    },
                    total_days=total_days,
                ).values()
            )
        ),
        0,
    )


def _allocate_volume(
    entries: list[VolumeEntry],
    *,
    slot_capacity: dict[str, float],
    total_capacity: float | None,
) -> UsageAllocation:
    normalized_slot_capacity = {
        str(slot): max(float(capacity), 0.0)
        for slot, capacity in slot_capacity.items()
        if float(capacity) > _EPSILON
    }
    normalized_entries = [
        VolumeEntry(
            player_id=str(entry.player_id).strip(),
            projected_volume=max(float(entry.projected_volume), 0.0),
            quality=float(entry.quality),
            slots={str(slot) for slot in entry.slots if str(slot) in normalized_slot_capacity},
        )
        for entry in entries
        if str(entry.player_id).strip() and float(entry.projected_volume) > _EPSILON
    ]
    normalized_entries = [
        entry
        for entry in normalized_entries
        if entry.projected_volume > _EPSILON and entry.slots
    ]

    total_requested_volume = float(sum(entry.projected_volume for entry in normalized_entries))
    total_slot_capacity = float(sum(normalized_slot_capacity.values()))
    capped_total_capacity = total_slot_capacity
    if total_capacity is not None:
        capped_total_capacity = min(capped_total_capacity, max(float(total_capacity), 0.0))

    if not normalized_entries or not normalized_slot_capacity or capped_total_capacity <= _EPSILON:
        return UsageAllocation(
            usage_share_by_player={},
            assigned_volume_by_player={},
            assigned_volume_by_player_slot={},
            slot_capacity=normalized_slot_capacity,
            slot_assigned_volume={slot: 0.0 for slot in normalized_slot_capacity},
            total_requested_volume=total_requested_volume,
            total_assigned_volume=0.0,
            total_capacity=capped_total_capacity,
        )

    min_quality = min(float(entry.quality) for entry in normalized_entries)
    effective_quality = {
        entry.player_id: max(float(entry.quality) - min_quality, 0.0) + 1.0
        for entry in normalized_entries
    }

    player_ids = sorted(entry.player_id for entry in normalized_entries)
    entry_by_player = {entry.player_id: entry for entry in normalized_entries}
    slot_names = sorted(normalized_slot_capacity.keys())
    source = 0
    first_player_node = 1
    first_slot_node = first_player_node + len(player_ids)
    budget_node = first_slot_node + len(slot_names)
    sink = budget_node + 1
    node_count = sink + 1
    graph: list[list[_FlowEdge]] = [[] for _ in range(node_count)]

    def add_edge(from_node: int, to_node: int, capacity: int, cost: int) -> None:
        forward = _FlowEdge(to=to_node, rev=len(graph[to_node]), capacity=capacity, cost=cost)
        backward = _FlowEdge(to=from_node, rev=len(graph[from_node]), capacity=0, cost=-cost)
        graph[from_node].append(forward)
        graph[to_node].append(backward)

    player_node_by_id = {
        player_id: first_player_node + idx
        for idx, player_id in enumerate(player_ids)
    }
    slot_node_by_name = {
        slot: first_slot_node + idx
        for idx, slot in enumerate(slot_names)
    }

    slot_edge_indices: dict[str, int] = {}
    for slot in slot_names:
        slot_node = slot_node_by_name[slot]
        edge_idx = len(graph[slot_node])
        add_edge(
            slot_node,
            budget_node,
            _scaled_capacity(normalized_slot_capacity[slot]),
            0,
        )
        slot_edge_indices[slot] = edge_idx
    add_edge(
        budget_node,
        sink,
        _scaled_capacity(capped_total_capacity),
        0,
    )

    player_edge_indices: dict[str, tuple[int, int]] = {}
    assignment_edges: dict[str, list[tuple[str, int]]] = {}
    for player_id in player_ids:
        entry = entry_by_player[player_id]
        player_node = player_node_by_id[player_id]
        source_edge_idx = len(graph[source])
        add_edge(source, player_node, _scaled_capacity(entry.projected_volume), 0)
        player_edge_indices[player_id] = (source, source_edge_idx)
        scaled_quality = int(round(effective_quality[player_id] * _QUALITY_SCALE))
        for slot in sorted(entry.slots):
            edge_idx = len(graph[player_node])
            add_edge(
                player_node,
                slot_node_by_name[slot],
                _scaled_capacity(entry.projected_volume),
                -scaled_quality,
            )
            assignment_edges.setdefault(player_id, []).append((slot, edge_idx))

    inf = 10**18
    potentials = [0] * node_count

    while True:
        dist = [inf] * node_count
        parent_node = [-1] * node_count
        parent_edge_idx = [-1] * node_count
        dist[source] = 0
        pq: list[tuple[int, int]] = [(0, source)]

        while pq:
            cur_dist, node = heapq.heappop(pq)
            if cur_dist != dist[node]:
                continue
            for edge_idx, edge in enumerate(graph[node]):
                if edge.capacity <= 0:
                    continue
                next_node = edge.to
                next_dist = cur_dist + edge.cost + potentials[node] - potentials[next_node]
                if next_dist < dist[next_node]:
                    dist[next_node] = next_dist
                    parent_node[next_node] = node
                    parent_edge_idx[next_node] = edge_idx
                    heapq.heappush(pq, (next_dist, next_node))

        if dist[sink] == inf:
            break

        path_cost = dist[sink] + potentials[sink] - potentials[source]
        if path_cost >= 0:
            break

        for node_idx, node_dist in enumerate(dist):
            if node_dist < inf:
                potentials[node_idx] += node_dist

        augment = inf
        cursor = sink
        while cursor != source:
            prev = parent_node[cursor]
            if prev < 0:
                augment = 0
                break
            edge = graph[prev][parent_edge_idx[cursor]]
            augment = min(augment, edge.capacity)
            cursor = prev
        if augment <= 0 or augment == inf:
            break

        cursor = sink
        while cursor != source:
            prev = parent_node[cursor]
            edge_idx = parent_edge_idx[cursor]
            edge = graph[prev][edge_idx]
            edge.capacity -= augment
            reverse = graph[cursor][edge.rev]
            reverse.capacity += augment
            cursor = prev

    assigned_volume_by_player: dict[str, float] = {}
    assigned_volume_by_player_slot: dict[str, dict[str, float]] = {}
    for player_id in player_ids:
        player_node = player_node_by_id[player_id]
        player_slot_assignments: dict[str, float] = {}
        for slot, edge_idx in assignment_edges.get(player_id, []):
            edge = graph[player_node][edge_idx]
            sent_units = graph[edge.to][edge.rev].capacity
            sent_volume = sent_units / _VOLUME_SCALE
            if sent_volume <= _EPSILON:
                continue
            player_slot_assignments[slot] = sent_volume
        assigned_total = float(sum(player_slot_assignments.values()))
        if assigned_total > _EPSILON:
            assigned_volume_by_player[player_id] = assigned_total
            assigned_volume_by_player_slot[player_id] = player_slot_assignments

    slot_assigned_volume: dict[str, float] = {}
    for slot in slot_names:
        slot_node = slot_node_by_name[slot]
        edge_idx = slot_edge_indices[slot]
        edge = graph[slot_node][edge_idx]
        sent_units = graph[edge.to][edge.rev].capacity
        slot_assigned_volume[slot] = sent_units / _VOLUME_SCALE

    usage_share_by_player = {}
    for player_id in player_ids:
        requested = float(entry_by_player[player_id].projected_volume)
        assigned = float(assigned_volume_by_player.get(player_id, 0.0))
        usage_share_by_player[player_id] = assigned / requested if requested > _EPSILON else 0.0

    return UsageAllocation(
        usage_share_by_player=usage_share_by_player,
        assigned_volume_by_player=assigned_volume_by_player,
        assigned_volume_by_player_slot=assigned_volume_by_player_slot,
        slot_capacity=normalized_slot_capacity,
        slot_assigned_volume=slot_assigned_volume,
        total_requested_volume=total_requested_volume,
        total_assigned_volume=float(sum(assigned_volume_by_player.values())),
        total_capacity=capped_total_capacity,
    )


def _scaled_capacity(value: float) -> int:
    return max(int(round(max(float(value), 0.0) * _VOLUME_SCALE)), 0)


__all__ = [
    "PitcherInningsAllocation",
    "PitcherUsageAllocation",
    "SYNTHETIC_PERIOD_DAYS",
    "SYNTHETIC_SEASON_DAYS",
    "UsageAllocation",
    "VolumeEntry",
    "allocate_hitter_usage",
    "allocate_hitter_usage_daily",
    "allocate_pitcher_innings_budget",
    "allocate_pitcher_usage",
    "allocate_pitcher_usage_daily",
    "annual_slot_capacity",
]
