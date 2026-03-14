"""Property-based tests for CalculateRequest validation using Hypothesis."""

import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

from pydantic import ValidationError

from backend.services.calculator.service import CalculateRequest

pytestmark = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")


# Strategy that generates valid CalculateRequest payloads with randomized fields.
def calculate_request_strategy():
    return st.fixed_dictionaries(
        {
            "mode": st.sampled_from(["common", "league"]),
            "scoring_mode": st.sampled_from(["roto", "points"]),
            "two_way": st.sampled_from(["sum", "max"]),
            "teams": st.integers(min_value=2, max_value=30),
            "sims": st.integers(min_value=1, max_value=5000),
            "horizon": st.integers(min_value=1, max_value=20),
            "discount": st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
            "hit_c": st.integers(min_value=0, max_value=5),
            "hit_1b": st.integers(min_value=0, max_value=5),
            "hit_2b": st.integers(min_value=0, max_value=5),
            "hit_3b": st.integers(min_value=0, max_value=5),
            "hit_ss": st.integers(min_value=0, max_value=5),
            "hit_ci": st.integers(min_value=0, max_value=5),
            "hit_mi": st.integers(min_value=0, max_value=5),
            "hit_of": st.integers(min_value=1, max_value=10),
            "hit_ut": st.integers(min_value=0, max_value=5),
            "pit_p": st.integers(min_value=1, max_value=10),
            "pit_sp": st.integers(min_value=0, max_value=5),
            "pit_rp": st.integers(min_value=0, max_value=5),
            "bench": st.integers(min_value=0, max_value=15),
            "minors": st.integers(min_value=0, max_value=15),
            "ir": st.integers(min_value=0, max_value=10),
            "ip_min": st.floats(min_value=0.0, max_value=200.0, allow_nan=False),
            "roto_hit_r": st.booleans(),
            "roto_hit_rbi": st.booleans(),
            "roto_hit_hr": st.booleans(),
            "roto_hit_sb": st.booleans(),
            "roto_hit_avg": st.booleans(),
            "roto_pit_w": st.booleans(),
            "roto_pit_k": st.booleans(),
            "roto_pit_sv": st.booleans(),
            "roto_pit_era": st.booleans(),
            "roto_pit_whip": st.booleans(),
        },
    )


if HAS_HYPOTHESIS:

    @given(data=calculate_request_strategy())
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_calculate_request_never_crashes(data):
        """CalculateRequest must either validate successfully or raise ValidationError — never crash."""
        try:
            req = CalculateRequest(**data)
            # If validation passes, basic invariants must hold
            assert req.teams >= 2
            assert req.sims >= 1
            assert req.horizon >= 1
        except ValidationError:
            pass  # Expected for invalid combinations (e.g., no roto categories enabled)

    @given(
        teams=st.integers(min_value=-100, max_value=100),
        sims=st.integers(min_value=-100, max_value=10000),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_calculate_request_rejects_out_of_bounds(teams, sims):
        """Out-of-bounds values for teams/sims must raise ValidationError."""
        if teams < 2 or teams > 30 or sims < 1 or sims > 5000:
            with pytest.raises(ValidationError):
                CalculateRequest(teams=teams, sims=sims)
