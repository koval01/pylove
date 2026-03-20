"""
MQTT topic layout for Home Assistant bridge.

Topics (default prefix ``lovensepy``):

- ``{prefix}/bridge/status`` — bridge availability (``online`` / ``offline``), retained.
- ``{prefix}/{safe_toy_id}/{feature}/set`` — HA command topics.
- ``{prefix}/{safe_toy_id}/{feature}/state`` — HA state topics.
- ``homeassistant/{component}/{object_id}/config`` — MQTT Discovery.
"""

from __future__ import annotations

import re

__all__ = [
    "mqtt_safe_toy_id",
    "bridge_status_topic",
    "command_topic",
    "state_topic",
    "discovery_topic",
    "feature_topic_segment",
    "topic_segment_to_action_name",
]

# Map topic segment (lowercase) -> Lovense API action key (PascalCase)
_SEGMENT_TO_ACTION: dict[str, str] = {
    "vibrate": "Vibrate",
    "vibrate1": "Vibrate1",
    "vibrate2": "Vibrate2",
    "vibrate3": "Vibrate3",
    "rotate": "Rotate",
    "pump": "Pump",
    "thrusting": "Thrusting",
    "fingering": "Fingering",
    "suction": "Suction",
    "depth": "Depth",
    "stroke": "Stroke",
    "oscillate": "Oscillate",
}

_ACTION_TO_SEGMENT = {v: k for k, v in _SEGMENT_TO_ACTION.items()}


def mqtt_safe_toy_id(toy_id: str, max_len: int = 64) -> str:
    """Make toy id safe for MQTT topic levels (no ``/``, ``+``, ``#``)."""
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(toy_id).strip())
    s = s.strip("_") or "toy"
    return s[:max_len]


def bridge_status_topic(prefix: str) -> str:
    p = prefix.strip("/")
    return f"{p}/bridge/status"


def command_topic(prefix: str, safe_toy_id: str, feature_segment: str) -> str:
    p = prefix.strip("/")
    return f"{p}/{safe_toy_id}/{feature_segment}/set"


def state_topic(prefix: str, safe_toy_id: str, feature_segment: str) -> str:
    p = prefix.strip("/")
    return f"{p}/{safe_toy_id}/{feature_segment}/state"


def discovery_topic(component: str, object_id: str) -> str:
    """``component``: number, button, sensor, select."""
    return f"homeassistant/{component}/{object_id}/config"


def feature_topic_segment(action_name: str) -> str:
    """Lovense action name -> lowercase MQTT segment."""
    return _ACTION_TO_SEGMENT.get(action_name, action_name.lower())


def topic_segment_to_action_name(segment: str) -> str | None:
    """MQTT segment -> Lovense action key, or None if unknown."""
    return _SEGMENT_TO_ACTION.get(segment.lower())


def subscribe_wildcard(prefix: str) -> str:
    p = prefix.strip("/")
    return f"{p}/+/+/set"
