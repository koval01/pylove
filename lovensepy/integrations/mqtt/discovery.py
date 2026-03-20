"""
Home Assistant MQTT Discovery payload builders.

See https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
"""

from __future__ import annotations

import json
from typing import Any

from ..._constants import FUNCTION_RANGES, Presets
from ...toy_utils import features_for_toy
from .topics import (
    bridge_status_topic,
    command_topic,
    discovery_topic,
    feature_topic_segment,
    mqtt_safe_toy_id,
    state_topic,
)

__all__ = [
    "discovery_object_id",
    "build_discovery_payloads",
]


def discovery_object_id(prefix: str, safe_toy_id: str, kind: str) -> str:
    """Stable MQTT discovery object_id (topic segment)."""
    p = re_safe_prefix(prefix)
    return f"{p}_{safe_toy_id}_{kind}"


def re_safe_prefix(prefix: str) -> str:
    """Convert topic prefix into a stable discovery-safe object id prefix."""
    return prefix.strip("/").replace("/", "_").replace(" ", "_")


def build_discovery_payloads(
    *,
    topic_prefix: str,
    toy_dict: dict[str, Any],
    availability_topic: str,
) -> list[tuple[str, str]]:
    """
    Return list of (discovery_topic, json_config_string).

    ``toy_dict`` is a plain dict (e.g. from ``ToyInfo.model_dump()`` or toy-list).
    """
    toy_id = str(toy_dict.get("id") or "")
    if not toy_id:
        return []
    safe = mqtt_safe_toy_id(toy_id)
    display = toy_dict.get("nickName") or toy_dict.get("name") or toy_dict.get("toyType") or toy_id
    model = str(toy_dict.get("toyType") or toy_dict.get("name") or "")

    device: dict[str, Any] = {
        "identifiers": [f"lovensepy_{safe}"],
        "name": str(display),
        "manufacturer": "Lovense",
    }
    if model:
        device["model"] = model

    pfx = topic_prefix.strip("/")
    out: list[tuple[str, str]] = []

    # --- Feature numbers (vibration, rotate, etc.) ---
    for action in features_for_toy(toy_dict):
        seg = feature_topic_segment(action)
        lo, hi = FUNCTION_RANGES.get(action, (0, 20))
        step = 1 if isinstance(lo, int) and isinstance(hi, int) else 0.1
        kind = f"num_{seg}"
        oid = discovery_object_id(pfx, safe, kind)
        cfg: dict[str, Any] = {
            "name": action,
            "command_topic": command_topic(pfx, safe, seg),
            "state_topic": state_topic(pfx, safe, seg),
            "min": lo,
            "max": hi,
            "step": step,
            "mode": "box",
            "availability_topic": availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "unique_id": f"lovensepy_{safe}_{seg}",
            "device": device,
        }
        out.append((discovery_topic("number", oid), json.dumps(cfg, separators=(",", ":"))))

    # --- Stop button ---
    oid_stop = discovery_object_id(pfx, safe, "stop")
    cfg_stop = {
        "name": "Stop",
        "command_topic": command_topic(pfx, safe, "stop"),
        "payload_press": "PRESS",
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
        "unique_id": f"lovensepy_{safe}_stop",
        "device": device,
    }
    out.append((discovery_topic("button", oid_stop), json.dumps(cfg_stop, separators=(",", ":"))))

    # --- Preset select ---
    options = [str(p) for p in Presets]
    oid_preset = discovery_object_id(pfx, safe, "preset")
    cfg_preset = {
        "name": "Preset",
        "command_topic": command_topic(pfx, safe, "preset"),
        "state_topic": state_topic(pfx, safe, "preset"),
        "options": options,
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
        "unique_id": f"lovensepy_{safe}_preset",
        "device": device,
    }
    preset_payload = json.dumps(cfg_preset, separators=(",", ":"))
    out.append((discovery_topic("select", oid_preset), preset_payload))

    # --- Battery sensor ---
    oid_bat = discovery_object_id(pfx, safe, "battery")
    cfg_bat = {
        "name": "Battery",
        "state_topic": state_topic(pfx, safe, "battery"),
        "unit_of_measurement": "%",
        "device_class": "battery",
        "state_class": "measurement",
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
        "unique_id": f"lovensepy_{safe}_battery",
        "device": device,
    }
    out.append((discovery_topic("sensor", oid_bat), json.dumps(cfg_bat, separators=(",", ":"))))

    return out


def default_availability_topic(topic_prefix: str) -> str:
    """Return default bridge availability topic for Home Assistant entities."""
    return bridge_status_topic(topic_prefix)
