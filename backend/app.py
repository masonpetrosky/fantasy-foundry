"""Compatibility entrypoint for the FastAPI app.

Runtime implementation lives in `backend.runtime`.
This module aliases itself to that runtime module so existing imports from
`backend.app` keep working (including private helpers used in tests).
"""

from __future__ import annotations

import sys

from backend import runtime as _runtime

sys.modules[__name__] = _runtime
