"""Tests for CSV/XLSX formula injection prevention in export_utils."""

from backend.core.export_utils import sanitize_cell_value


def test_formula_prefix_equals():
    assert sanitize_cell_value("=SUM(A1)") == "'=SUM(A1)"


def test_formula_prefix_plus():
    assert sanitize_cell_value("+1+2") == "'+1+2"


def test_formula_prefix_at():
    assert sanitize_cell_value("@SUM(A1)") == "'@SUM(A1)"


def test_formula_prefix_tab():
    assert sanitize_cell_value("\tdata") == "'\tdata"


def test_formula_prefix_carriage_return():
    assert sanitize_cell_value("\rdata") == "'\rdata"


def test_formula_prefix_minus():
    assert sanitize_cell_value("-cmd|'/C calc'!A0") == "'-cmd|'/C calc'!A0"


def test_normal_string_unchanged():
    assert sanitize_cell_value("Mike Trout") == "Mike Trout"


def test_empty_string_unchanged():
    assert sanitize_cell_value("") == ""


def test_valid_negative_number_unchanged():
    assert sanitize_cell_value(-3.14) == -3.14


def test_integer_passthrough():
    assert sanitize_cell_value(42) == 42


def test_none_passthrough():
    assert sanitize_cell_value(None) is None


def test_bool_passthrough():
    assert sanitize_cell_value(True) is True
