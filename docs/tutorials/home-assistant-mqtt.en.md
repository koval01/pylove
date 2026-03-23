# Home Assistant MQTT bridge

Run a small **bridge process**: it publishes **MQTT Discovery** entities to Home Assistant and forwards commands over **LAN** (Lovense Remote Game Mode) or **direct BLE** (this machine’s Bluetooth radio to `LVS-…` peripherals).

## Requirements

- MQTT broker reachable from the machine running the bridge (for example Mosquitto on `192.168.1.2:1883`)
- Home Assistant **MQTT** integration using the same broker
- **LAN mode:** Lovense **Remote** with **Game Mode** enabled (not Lovense Connect for Toy Events)
- **BLE mode:** Bluetooth adapter on the host running the bridge; toys must be connectable from the OS (often **exclusive** with Lovense Remote’s BLE link). Install `pip install 'lovensepy[mqtt,ble]'` (or `[mqtt]` + `[ble]`).
- `pip install 'lovensepy[mqtt]'` (add `ble` for BLE transport)

### Step 1: Environment variables

**LAN (default):**

```bash
export LOVENSE_TRANSPORT=lan          # default; omit or set explicitly
export LOVENSE_LAN_IP=192.168.1.100   # host running Lovense Remote (Game Mode)
export MQTT_HOST=192.168.1.2
export MQTT_PORT=1883
# optional: MQTT_USER, MQTT_PASSWORD, MQTT_TOPIC_PREFIX=lovensepy
```

**BLE:**

```bash
export LOVENSE_TRANSPORT=ble
# LOVENSE_LAN_IP not required; Toy Events are not used in BLE mode
export MQTT_HOST=192.168.1.2
# optional: LOVENSE_BLE_DISCOVER_TIMEOUT (seconds, default 15), LOVENSE_BLE_NAME_PREFIX (default LVS-)
```

### Step 2: Example bridge

```bash
python examples/ha_mqtt_bridge.py
```

### Step 3: Home Assistant

In Home Assistant, open **Settings**, then **Devices & Services**, then **MQTT**. New devices should appear under MQTT discovery (per-toy controls for supported motors, **Stop**, **Preset**, **Battery**, and similar).

### Step 4: Toy Events permission

Grant Toy Events access when Lovense Remote prompts (same flow as the [Toy Events](toy-events.md#toy-events-tutorial) tutorial).

## Topic layout

Default prefix `lovensepy`: command topics look like `lovensepy/<safe_toy_id>/<feature>/set` (for example `vibrate`, `rotate`, `preset`, `stop`). The bridge publishes retained availability on `lovensepy/bridge/status` (`online` / `offline`) and, per toy, on `lovensepy/<safe_toy_id>/device_availability`, so Home Assistant marks entities unavailable when the BLE link drops or GetToys reports `status` off (updated on each refresh; shorten `refresh_interval` if you want faster transitions).

![Home Assistant dashboard: Lovense toys via MQTT Discovery](../images/ha_mqtt_dashboard.png)

## Programmatic use

**LAN:**

```python
import asyncio
from lovensepy import HAMqttBridge

async def main():
    bridge = HAMqttBridge(
        "192.168.1.2",
        1883,
        lan_ip="192.168.1.100",
        mqtt_username=None,
        mqtt_password=None,
    )
    await bridge.start()
    # ... keep running ...
    await bridge.stop()

asyncio.run(main())
```

**BLE** (scan, connect, then same MQTT topics; state is refreshed via periodic `get_toys`):

```python
import asyncio
from lovensepy import HAMqttBridge

async def main():
    bridge = HAMqttBridge(
        "192.168.1.2",
        1883,
        transport="ble",
        ble_discover_timeout=15.0,
    )
    await bridge.start()
    try:
        await asyncio.Event().wait()
    finally:
        await bridge.stop()

asyncio.run(main())
```

**Advanced:** pass a pre-configured :class:`~lovensepy.ble_direct.hub.BleDirectHub` with `transport="ble"` and `ble_hub=hub` (after `add_toy` / `connect` or your own `discover_and_connect`). The bridge will call :meth:`~lovensepy.ble_direct.hub.BleDirectHub.aclose` on :meth:`~lovensepy.integrations.mqtt.ha_bridge.HAMqttBridge.stop`.
