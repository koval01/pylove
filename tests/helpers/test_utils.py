"""
Shared test utilities to keep integration tests compact.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lovensepy import LovenseError


def call_or_skip[T](func: Callable[[], T]) -> T:
    """Call API function and skip the test on transient network errors."""
    try:
        return func()
    except LovenseError as exc:
        pytest.skip(f"Network error: {exc}")


def assert_has_code(resp: object) -> None:
    code = getattr(resp, "code", None)
    assert code is not None, f"Expected non-empty response code, got: {resp!r}"


def is_success_response(resp: object) -> bool:
    code = getattr(resp, "code", None)
    result = getattr(resp, "result", None)
    return code == 200 or result is True
