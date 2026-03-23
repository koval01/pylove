"""
Build ``(advertised_type_slug, DeviceType_letter) -> marketing showName`` from ToyConfig V3-style
JSON (toy list + marketing metadata).

Ship ``toy_config_ble_marketing.json`` next to this module. Regenerate it when updating bundled
marketing maps (see repository maintainer tooling for the export format). If the file is missing,
fall back to a minimal built-in map.

Toy-code branches that map several marketing names to the same UART prefix (e.g.
Lush 2/3/4 via ``s_*``) are skipped so we do not mislabel firmware; those stay
on the base ``showName``. ``domi|W`` → ``Domi 2`` follows a single-name toyCode
branch and may label original Domi — refine later with firmware if needed.

Some toys list **two** UART letters in ``symbol[]`` but every ``fversionDiff``
``toyCode`` uses **one** prefix (e.g. Gush: ``ed`` + ``ez`` in ``symbol``, only
``ed_*`` in ``toyCode``). The merge step would refresh only the prefix letter;
``_TOYCODE_PREFIX_UART_ALIASES`` copies the resolved name onto the sibling letter
so regeneration matches hardware. Add rows here only for that pattern.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Final

_FALLBACK: Final[dict[tuple[str, str], str]] = {}

# (advertised slug, UART letter) -> UART letter whose marketing name was updated from toyCode.
_TOYCODE_PREFIX_UART_ALIASES: Final[dict[tuple[str, str], str]] = {
    ("gush", "EZ"): "ED",
}


def _type_to_slug(t: str) -> str:
    s = (t or "").strip().lower().split("-")[0].split(":")[0]
    s = re.sub(r"\d+$", "", s).strip()
    return s


def _build_from_toy_list(info: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    base: dict[tuple[str, str], str] = {}
    # (slug, toycode_prefix_lower) -> set of distinct marketing names from fversionDiff
    tc_names: dict[tuple[str, str], set[str]] = {}

    def add_base(slug: str, letter: str, name: str) -> None:
        if not slug or not letter or not name:
            return
        letter = str(letter).strip().upper()
        if not letter:
            return
        base[(slug, letter)] = str(name).strip()

    def note_tc(slug: str, prefix: str, name: str) -> None:
        p = str(prefix).strip().lower()
        n = str(name).strip()
        if not slug or not p or not n:
            return
        tc_names.setdefault((slug, p), set()).add(n)

    for toy in info:
        typ = toy.get("type") or ""
        slug = _type_to_slug(typ)
        if not slug:
            continue
        base_name = (toy.get("showName") or toy.get("fullName") or typ).strip()
        syms = [str(s).strip() for s in (toy.get("symbol") or []) if str(s).strip()]
        for sym in syms:
            add_base(slug, sym, base_name)
        for diff in toy.get("fversionDiff") or []:
            name = diff.get("showName")
            if not name:
                continue
            name = str(name).strip()
            tc = diff.get("toyCode") or ""
            if not tc or "_" not in tc:
                continue
            pref = tc.split("_", 1)[0].strip().lower()
            if not pref:
                continue
            note_tc(slug, pref, name)

    out = dict(base)
    for (slug, pref), names in tc_names.items():
        if len(names) != 1:
            # Ambiguous: e.g. Lush 2/3/4/Pro all use toyCode prefix "s".
            continue
        (only,) = tuple(names)
        letter = pref.upper()
        out[(slug, letter)] = only

    for (slug, alias_letter), canonical_letter in _TOYCODE_PREFIX_UART_ALIASES.items():
        if (v := out.get((slug, canonical_letter))) is not None:
            out[(slug, alias_letter)] = v
    return out


def _parse_ble_marketing_json(raw: str) -> dict[tuple[str, str], str]:
    data = json.loads(raw)
    out: dict[tuple[str, str], str] = {}
    for k, v in data.items():
        if "|" not in k or not isinstance(v, str):
            continue
        a, b = k.split("|", 1)
        out[(a.strip().lower(), b.strip().upper())] = v.strip()
    return out


def _load_packaged_json() -> dict[tuple[str, str], str] | None:
    try:
        raw = (
            resources.files("lovensepy.ble_direct")
            .joinpath("toy_config_ble_marketing.json")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return None
    try:
        out = _parse_ble_marketing_json(raw)
    except json.JSONDecodeError:
        return None
    return out or None


@lru_cache(maxsize=1)
def ble_marketing_name_overrides() -> dict[tuple[str, str], str]:
    loaded = _load_packaged_json()
    if loaded is not None:
        return loaded
    path = Path(__file__).resolve().parent / "toy_config_ble_marketing.json"
    if path.is_file():
        try:
            return _parse_ble_marketing_json(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return dict(_FALLBACK)


def rebuild_marketing_map_from_toy_config_export(path: Path) -> dict[tuple[str, str], str]:
    """For maintainers: parse a ToyConfig V3-style bundle JSON and return the marketing map."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    info = json.loads(raw["data"]["info"])
    return _build_from_toy_list(info)


def marketing_map_to_json_dict(m: dict[tuple[str, str], str]) -> dict[str, str]:
    return {f"{a}|{b}": name for (a, b), name in sorted(m.items())}
