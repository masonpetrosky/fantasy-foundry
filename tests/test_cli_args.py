import argparse

import pytest

from backend.valuation.cli_args import (
    discount_arg,
    non_negative_float_arg,
    non_negative_int_arg,
    optional_non_negative_float_arg,
    positive_int_arg,
    validate_ip_bounds,
)


def test_positive_int_arg_accepts_positive_integer_strings():
    assert positive_int_arg("3") == 3


def test_positive_int_arg_rejects_zero():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int_arg(0)


def test_non_negative_int_arg_accepts_zero():
    assert non_negative_int_arg(0) == 0


def test_non_negative_float_arg_rejects_negative_values():
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_float_arg("-0.1")


def test_discount_arg_rejects_out_of_range():
    with pytest.raises(argparse.ArgumentTypeError):
        discount_arg("1.2")


def test_optional_non_negative_float_arg_accepts_disabled_tokens():
    assert optional_non_negative_float_arg("none") is None


def test_optional_non_negative_float_arg_rejects_negative_values():
    with pytest.raises(argparse.ArgumentTypeError):
        optional_non_negative_float_arg("-2")


def test_validate_ip_bounds_rejects_invalid_upper_bound():
    with pytest.raises(ValueError):
        validate_ip_bounds(100.0, 90.0)
