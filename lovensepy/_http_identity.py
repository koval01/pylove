"""
HTTP identification: User-Agent with package version and support links.

Version: ``importlib.metadata`` when the package is installed (matches ``pyproject.toml``
at build time). Fallback: read ``pyproject.toml`` next to the repo root when running
from a source checkout without metadata.

Repository URLs are kept in sync with ``[project.urls]`` in ``pyproject.toml``.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_PACKAGE_NAME = "lovensepy"
_REPO_URL = "https://github.com/koval01/lovensepy"
_CONTACT_EMAIL = "git@koval-dev.org"


@lru_cache
def package_version() -> str:
    """Installed distribution version, or version from ``pyproject.toml`` as fallback."""
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject.is_file():
            with pyproject.open("rb") as fp:
                data = tomllib.load(fp)
            return str(data["project"]["version"])
        return "0.0.0"


def user_agent_string() -> str:
    """Value for the ``User-Agent`` header (Lovense can identify this library in logs)."""
    return f"{_PACKAGE_NAME}/{package_version()} (+{_REPO_URL}; contact={_CONTACT_EMAIL})"


def default_http_headers() -> dict[str, str]:
    """Headers applied to outbound HTTP unless overridden (see :func:`merge_http_headers`)."""
    return {"User-Agent": user_agent_string()}


def merge_http_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Merge caller headers over defaults; explicit ``User-Agent`` replaces the default."""
    merged = default_http_headers()
    if headers:
        merged.update(headers)
    return merged
