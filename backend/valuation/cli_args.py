"""Argument parsing helpers for dynasty valuation CLIs."""

from __future__ import annotations

import argparse
from typing import Optional, Union


def positive_int_arg(value: Union[str, int]) -> int:
    """argparse type: integer >= 1."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected an integer, got: {value!r}") from exc
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"Expected an integer >= 1, got: {ivalue}")
    return ivalue


def non_negative_int_arg(value: Union[str, int]) -> int:
    """argparse type: integer >= 0."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected an integer, got: {value!r}") from exc
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"Expected an integer >= 0, got: {ivalue}")
    return ivalue


def non_negative_float_arg(value: Union[str, float]) -> float:
    """argparse type: float >= 0."""
    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a float, got: {value!r}") from exc
    if fvalue < 0.0:
        raise argparse.ArgumentTypeError(f"Expected a float >= 0, got: {fvalue}")
    return fvalue


def discount_arg(value: Union[str, float]) -> float:
    """argparse type: annual discount factor in the interval (0, 1]."""
    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a float, got: {value!r}") from exc
    if not (0.0 < fvalue <= 1.0):
        raise argparse.ArgumentTypeError(f"Expected discount in (0, 1], got: {fvalue}")
    return fvalue


def optional_non_negative_float_arg(value: Union[str, float]) -> Optional[float]:
    """argparse type: float >= 0, or None for disabled limits."""
    if value is None:
        return None

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"none", "null", "off", "no", "disabled"}:
            return None

    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a float or 'none', got: {value!r}") from exc

    if fvalue < 0.0:
        raise argparse.ArgumentTypeError(f"Expected a float >= 0 or 'none', got: {fvalue}")
    return fvalue


def validate_ip_bounds(ip_min: float, ip_max: Optional[float]) -> None:
    """Ensure optional IP bounds are internally consistent."""
    if ip_min < 0:
        raise ValueError(f"ip_min must be >= 0, got {ip_min}")
    if ip_max is not None and ip_max < ip_min:
        raise ValueError(f"ip_max ({ip_max}) must be >= ip_min ({ip_min})")
