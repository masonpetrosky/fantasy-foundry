"""Custom exception hierarchy for Fantasy Foundry domain errors."""

from __future__ import annotations


class FantasyFoundryError(Exception):
    """Base exception for all Fantasy Foundry domain errors."""


class ExternalServiceError(FantasyFoundryError):
    """Error communicating with an external service (Fantrax, Supabase, Stripe)."""


class CalculationError(FantasyFoundryError):
    """Error during dynasty value calculation."""


class DataLoadError(FantasyFoundryError):
    """Error loading or refreshing projection data."""
