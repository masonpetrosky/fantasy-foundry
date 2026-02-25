from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.core.runtime_facade import (
    REQUIRED_RUNTIME_FACADE_ALIAS_KEYS,
    apply_runtime_facade_aliases,
    build_runtime_facade_alias_map,
    missing_runtime_facade_alias_keys,
    unexpected_runtime_facade_alias_keys,
    validate_runtime_facade_alias_map,
)


def test_runtime_facade_alias_map_matches_required_contract() -> None:
    alias_map = build_runtime_facade_alias_map(state_module=SimpleNamespace())

    assert set(alias_map.keys()) == set(REQUIRED_RUNTIME_FACADE_ALIAS_KEYS)
    assert missing_runtime_facade_alias_keys(alias_map) == set()
    assert unexpected_runtime_facade_alias_keys(alias_map) == set()


def test_apply_runtime_facade_aliases_sets_attributes() -> None:
    state = SimpleNamespace()
    alias_map = {"_sentinel": object()}

    apply_runtime_facade_aliases(state_module=state, alias_map=alias_map)

    assert getattr(state, "_sentinel") is alias_map["_sentinel"]


def test_validate_runtime_facade_alias_map_rejects_missing_keys() -> None:
    incomplete = {
        key: object()
        for key in REQUIRED_RUNTIME_FACADE_ALIAS_KEYS
        if key != "_validate_runtime_configuration"
    }

    with pytest.raises(RuntimeError, match="Invalid runtime facade alias map contract"):
        validate_runtime_facade_alias_map(incomplete)
