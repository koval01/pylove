"""Home Assistant MQTT bridge service (LAN Game Mode or direct BLE).

Run with:

    python -m lovensepy.services.mqtt_bridge

Or after ``pip install 'lovensepy[mqtt]'`` (add ``[ble]`` for BLE transport):

    lovensepy-mqtt

Environment variables match the previous ``examples/ha_mqtt_bridge.py`` helper.
"""

from __future__ import annotations

from ._cli import main

__all__ = ["main"]
