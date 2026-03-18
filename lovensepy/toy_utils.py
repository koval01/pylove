"""
Toy utilities: feature detection, stop actions.

Use with toy dict from GetToys / basicapi_update_device_info_tc.
"""

from typing import Any

__all__ = ["features_for_toy", "stop_actions"]

SHORT_TO_FULL: dict[str, str] = {
    "v": "Vibrate",
    "v1": "Vibrate1",
    "v2": "Vibrate2",
    "r": "Rotate",
    "p": "Pump",
    "t": "Thrusting",
    "f": "Fingering",
    "s": "Suction",
    "d": "Depth",
    "st": "Stroke",
    "o": "Oscillate",
}
KNOWN_FEATURES = frozenset(SHORT_TO_FULL.values())


def features_for_toy(toy: dict[str, Any]) -> list[str]:
    """
    Get ordered list of features (Vibrate1, Vibrate2, Rotate, etc.) for toy.

    Uses API shortFunctionNames/fullFunctionNames when available.
    Edge/Diamo: API often returns only 'v'/'Vibrate' — override to Vibrate1, Vibrate2.
    """
    if toy is None:
        raise TypeError("toy must not be None")
    toy_type = (toy.get("toyType") or toy.get("name") or "").lower()
    full = toy.get("fullFunctionNames") or []
    short = toy.get("shortFunctionNames") or []
    seen: set[str] = set()
    result: list[str] = []
    for name in full + [SHORT_TO_FULL.get(str(s).lower(), str(s)) for s in short]:
        if not isinstance(name, str):
            continue
        n = name.strip()
        mapped = SHORT_TO_FULL.get(n.lower(), n) if len(n) <= 3 else n
        if mapped in KNOWN_FEATURES and mapped not in seen:
            seen.add(mapped)
            result.append(mapped)
    if result:
        if ("edge" in toy_type or "diamo" in toy_type) and result == ["Vibrate"]:
            return ["Vibrate1", "Vibrate2"]
        return result
    if "edge" in toy_type or "diamo" in toy_type:
        return ["Vibrate1", "Vibrate2"]
    if "nora" in toy_type:
        return ["Vibrate", "Rotate"]
    if "max" in toy_type:
        return ["Vibrate", "Rotate", "Pump"]
    return ["Vibrate"]


def stop_actions(toy: dict[str, Any]) -> dict[str, int]:
    """Build actions dict to stop all motors: {Vibrate1: 0, Vibrate2: 0, ...}."""
    feats = features_for_toy(toy)
    return {f: 0 for f in feats}
