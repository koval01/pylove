"""
Home Assistant MQTT bridge (optional ``paho-mqtt`` dependency).

Usage::

    from lovensepy.integrations.mqtt import HAMqttBridge

Or::

    from lovensepy import HAMqttBridge
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "HAMqttBridge",
    "default_availability_topic",
    "build_discovery_payloads",
    "mqtt_safe_toy_id",
]


def __getattr__(name: str) -> Any:
    if name == "HAMqttBridge":
        from .ha_bridge import HAMqttBridge as _HAMqttBridge

        return _HAMqttBridge
    if name == "build_discovery_payloads":
        from .discovery import build_discovery_payloads as _build

        return _build
    if name == "default_availability_topic":
        from .discovery import default_availability_topic as _da

        return _da
    if name == "mqtt_safe_toy_id":
        from .topics import mqtt_safe_toy_id as _ms

        return _ms
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
