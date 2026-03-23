"""
Firmware-aware marketing ``showName`` using ToyConfig-style ``fversionDiff`` rules.

Walks ``fversionDiff`` in **array order**, uses the **first** entry whose ``fversion``
ranges contain the integer firmware, and takes ``showName`` from that diff when set;
otherwise the toy's base ``showName``.

Packaged data: ``toy_config_ble_marketing_firmware.json``. Regenerate it when updating
bundled marketing maps (see repository maintainer tooling for the JSON export format).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Final

from ._ble_marketing_map import _type_to_slug

_FW_INT_MAX: Final[int] = 10_000_000


def parse_firmware_int(raw: str | None) -> int | None:
    """Parse UART ``DeviceType`` firmware field to a non-negative int, or None."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw).strip())
    if not digits:
        return None
    try:
        v = int(digits, 10)
    except ValueError:
        return None
    if v < 0 or v > _FW_INT_MAX:
        return None
    return v


def _build_firmware_rules(info: list[dict[str, Any]]) -> dict[str, Any]:
    """Build slug -> {letters, base, diffs} for JSON serialization."""
    out: dict[str, Any] = {}
    for toy in info:
        typ = toy.get("type") or ""
        slug = _type_to_slug(typ)
        if not slug:
            continue
        letters = sorted(
            {str(s).strip().upper() for s in (toy.get("symbol") or []) if str(s).strip()}
        )
        if not letters:
            continue
        base = (toy.get("showName") or toy.get("fullName") or typ).strip()
        diffs_out: list[dict[str, Any]] = []
        for diff in toy.get("fversionDiff") or []:
            ranges: list[list[int]] = []
            for rng in diff.get("fversion") or []:
                minv = rng.get("minv")
                maxv = rng.get("maxv")
                if minv is None or maxv is None:
                    continue
                try:
                    lo, hi = int(minv), int(maxv)
                except (TypeError, ValueError):
                    continue
                ranges.append([lo, hi])
            if not ranges:
                continue
            entry: dict[str, Any] = {"ranges": ranges}
            sn = diff.get("showName")
            if sn is not None and str(sn).strip():
                entry["showName"] = str(sn).strip()
            diffs_out.append(entry)
        if not diffs_out:
            continue
        out[slug] = {"letters": letters, "base": base, "diffs": diffs_out}
    return out


def rebuild_firmware_rules_from_toy_config_export(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    info = json.loads(raw["data"]["info"])
    return _build_firmware_rules(info)


def marketing_firmware_rules_to_json_dict(rules: dict[str, Any]) -> dict[str, Any]:
    return dict(sorted(rules.items()))


def _load_packaged_firmware_json() -> dict[str, Any] | None:
    try:
        raw = (
            resources.files("lovensepy.ble_direct")
            .joinpath("toy_config_ble_marketing_firmware.json")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


@lru_cache(maxsize=1)
def ble_marketing_firmware_rules() -> dict[str, Any]:
    loaded = _load_packaged_firmware_json()
    if loaded is not None:
        return loaded
    path = Path(__file__).resolve().parent / "toy_config_ble_marketing_firmware.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def marketing_show_name_for_firmware(
    toy_type_slug: str,
    model_letter: str,
    firmware_raw: str | None,
) -> str | None:
    """Resolve display name when rules exist and firmware parses.

    Returns ``None`` if the slug has no packaged rules, the letter is not in
    ``symbol[]`` for that toy, or firmware cannot be parsed (caller may fall
    back to the flat marketing map).
    """
    slug = (toy_type_slug or "").strip().lower()
    letter = (model_letter or "").strip().upper()
    if not slug or not letter:
        return None
    fw = parse_firmware_int(firmware_raw)
    if fw is None:
        return None
    toy = ble_marketing_firmware_rules().get(slug)
    if not toy or not isinstance(toy, dict):
        return None
    letters = toy.get("letters") or []
    allowed = {str(x).strip().upper() for x in letters if str(x).strip()}
    if letter not in allowed:
        return None
    base = str(toy.get("base") or "").strip() or None
    if base is None:
        return None
    for diff in toy.get("diffs") or []:
        if not isinstance(diff, dict):
            continue
        for pair in diff.get("ranges") or []:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            try:
                lo, hi = int(pair[0]), int(pair[1])
            except (TypeError, ValueError):
                continue
            if lo <= fw <= hi:
                sn = diff.get("showName")
                if sn is not None and str(sn).strip():
                    return str(sn).strip()
                return base
    return base
