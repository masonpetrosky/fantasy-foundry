import asyncio
import os
from pathlib import Path

import pytest

try:
    import uvloop
except ImportError:  # pragma: no cover - uvloop is unavailable on some platforms
    uvloop = None

E2E_ENV_VAR = "FF_RUN_E2E"
E2E_ENABLED_TOKENS = {"1", "true", "yes", "on"}
E2E_FILE_PREFIX = "test_e2e_"


def _configure_test_event_loop_policy() -> None:
    if uvloop is None:
        return
    if isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy):
        return
    # TestClient and AnyIO's thread bridge can hang on the default asyncio loop here.
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


_configure_test_event_loop_policy()


def _is_e2e_enabled() -> bool:
    return os.getenv(E2E_ENV_VAR, "").strip().lower() in E2E_ENABLED_TOKENS


def _is_e2e_item(item: pytest.Item) -> bool:
    marker = item.get_closest_marker("e2e")
    if marker is not None:
        return True
    filename = Path(str(getattr(item, "fspath", ""))).name
    return filename.startswith(E2E_FILE_PREFIX)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _is_e2e_enabled():
        return

    skip_reason = f"E2E tests are disabled by default. Set {E2E_ENV_VAR}=1 to include them."
    skip_e2e = pytest.mark.skip(reason=skip_reason)
    for item in items:
        if _is_e2e_item(item):
            item.add_marker(skip_e2e)
