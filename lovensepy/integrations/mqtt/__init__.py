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
    "HAMqttBridge",  # pylint: disable=undefined-all-variable
    "default_availability_topic",  # pylint: disable=undefined-all-variable
    "build_discovery_payloads",  # pylint: disable=undefined-all-variable
    "mqtt_safe_toy_id",  # pylint: disable=undefined-all-variable
]


def __getattr__(name: str) -> Any:
    if name == "HAMqttBridge":
        from .ha_bridge import (  # pylint: disable=import-outside-toplevel
            HAMqttBridge as _HAMqttBridge,
        )

        return _HAMqttBridge
    if name == "build_discovery_payloads":
        from .discovery import (  # pylint: disable=import-outside-toplevel
            build_discovery_payloads as _build,
        )

        return _build
    if name == "default_availability_topic":
        from .discovery import (  # pylint: disable=import-outside-toplevel
            default_availability_topic as _da,
        )

        return _da
    if name == "mqtt_safe_toy_id":
        from .topics import mqtt_safe_toy_id as _ms  # pylint: disable=import-outside-toplevel

        return _ms
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
