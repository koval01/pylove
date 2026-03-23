#!/usr/bin/env python3
"""
Home Assistant MQTT bridge for Lovense (LAN Game Mode or direct BLE).

Publishes MQTT Discovery entities (numbers, stop button, presets, battery) and
forwards commands to the Lovense HTTP API (LAN) or BleDirectHub (BLE). In LAN
mode, optionally subscribes to Toy Events for live battery / strength updates.

Requires:
    pip install 'lovensepy[mqtt]'
    For BLE: pip install 'lovensepy[ble]' (or lovensepy[mqtt,ble])

Environment:
    LOVENSE_TRANSPORT    — lan (default) or ble
    LOVENSE_LAN_IP       — phone running Lovense Remote (Game Mode); required for lan
    MQTT_HOST            — MQTT broker host (default: 192.168.1.2)
    MQTT_PORT            — broker port (default: 1883)
    MQTT_USER / MQTT_PASSWORD — optional broker auth
    LOVENSE_LAN_PORT     — HTTP command port (default: 20011)
    LOVENSE_TOY_EVENTS_PORT — WebSocket events port (default: same as LOVENSE_LAN_PORT)
    LOVENSE_BLE_DISCOVER_TIMEOUT — BLE scan seconds (default: 15)
    LOVENSE_BLE_NAME_PREFIX — advertiser prefix (default: LVS-); empty string scans all names
    LOVENSEPY_BLE_PRESET_UART — BLE preset UART prefix: Preset (default, public docs) or Pat
        (same default keyword as BleDirectClient); aligns with FastAPI when set explicitly
    LOVENSEPY_BLE_PRESET_EMULATE_PATTERN — set to 1/true to drive pulse/wave/… via pattern
        stepping if the toy ignores Pat/Preset lines

Home Assistant: enable the MQTT integration pointing at the same broker. Entities
appear automatically under MQTT discovery.
"""

from __future__ import annotations

import asyncio
import os
import sys

from lovensepy import HAMqttBridge


async def _main() -> None:
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
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
