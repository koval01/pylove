"""CLI entry for the Home Assistant MQTT bridge (env-driven, like the FastAPI service).

Environment (same as before the ``examples/ha_mqtt_bridge.py`` script):

- ``LOVENSE_TRANSPORT`` — ``lan`` (default) or ``ble``
- ``LOVENSE_LAN_IP`` — Lovense Remote Game Mode host; required for ``lan``
- ``MQTT_HOST``, ``MQTT_PORT`` — broker (defaults ``192.168.1.2``, ``1883``)
- ``MQTT_USER``, ``MQTT_PASSWORD``, ``MQTT_TOPIC_PREFIX`` — optional
- ``LOVENSE_LAN_PORT``, ``LOVENSE_TOY_EVENTS_PORT`` — HTTP / Toy Events ports (LAN)
- ``LOVENSE_BLE_DISCOVER_TIMEOUT``, ``LOVENSE_BLE_NAME_PREFIX`` — BLE scan (``ble``)
- ``LOVENSE_HA_APP_NAME`` — app name string for the bridge
- ``LOVENSEPY_BLE_PRESET_UART``, ``LOVENSEPY_BLE_PRESET_EMULATE_PATTERN`` — BLE preset
  (see BleDirect)
"""

from __future__ import annotations

import asyncio
import os
import sys

from lovensepy.integrations.mqtt.ha_bridge import HAMqttBridge


async def _async_main() -> None:
    transport = (os.environ.get("LOVENSE_TRANSPORT") or "lan").strip().lower()
    if transport not in ("lan", "ble"):
        print("LOVENSE_TRANSPORT must be 'lan' or 'ble'.", file=sys.stderr)
        raise SystemExit(1)

    lan_ip = os.environ.get("LOVENSE_LAN_IP")
    if transport == "lan" and not lan_ip:
        print("Set LOVENSE_LAN_IP (Lovense Remote Game Mode host).", file=sys.stderr)
        raise SystemExit(1)

    mqtt_host = os.environ.get("MQTT_HOST", "192.168.1.2")
    mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
    lan_port = int(os.environ.get("LOVENSE_LAN_PORT", "20011"))
    toy_events_port = int(os.environ.get("LOVENSE_TOY_EVENTS_PORT", str(lan_port)))
    user = os.environ.get("MQTT_USER") or None
    password = os.environ.get("MQTT_PASSWORD") or None
    prefix = os.environ.get("MQTT_TOPIC_PREFIX", "lovensepy")
    ble_timeout = float(os.environ.get("LOVENSE_BLE_DISCOVER_TIMEOUT", "15"))
    ble_prefix_raw = os.environ.get("LOVENSE_BLE_NAME_PREFIX")
    ble_name_prefix: str | None
    if ble_prefix_raw is not None:
        ble_name_prefix = ble_prefix_raw if ble_prefix_raw != "" else None
    else:
        ble_name_prefix = "LVS-"

    app_name = os.environ.get("LOVENSE_HA_APP_NAME", "lovensepy_ha")
    if transport == "lan":
        bridge = HAMqttBridge(
            mqtt_host,
            mqtt_port,
            lan_ip=lan_ip,
            lan_port=lan_port,
            toy_events_port=toy_events_port,
            app_name=app_name,
            topic_prefix=prefix,
            mqtt_username=user,
            mqtt_password=password,
        )
    else:
        bridge = HAMqttBridge(
            mqtt_host,
            mqtt_port,
            transport="ble",
            lan_port=lan_port,
            toy_events_port=toy_events_port,
            app_name=app_name,
            topic_prefix=prefix,
            mqtt_username=user,
            mqtt_password=password,
            ble_discover_timeout=ble_timeout,
            ble_name_prefix=ble_name_prefix,
        )

    await bridge.start()
    print(f"Bridge online. Availability: {bridge.availability_topic}", flush=True)
    print("Press Ctrl+C to exit.", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await bridge.stop()


def main() -> int:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass
    return 0
