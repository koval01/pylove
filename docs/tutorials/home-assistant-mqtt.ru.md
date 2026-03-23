# MQTT-мост Home Assistant

Запустите небольшой **процесс-мост**: он публикует сущности **MQTT Discovery** в Home Assistant и пересылает команды по **LAN** (Game Mode Lovense Remote) или **прямому BLE** (Bluetooth этой машины к периферии `LVS-…`).

## Требования

- Доступный с машины с мостом MQTT-брокер (например Mosquitto на `192.168.1.2:1883`)
- Интеграция **MQTT** в Home Assistant на том же брокере
- **LAN-режим:** Lovense **Remote** с включённым **Game Mode** (не Connect для Toy Events)
- **BLE-режим:** Bluetooth-адаптер на хосте с мостом; игрушки должны быть доступны ОС (часто **эксклюзивно** с BLE-связью Remote). Установите `pip install 'lovensepy[mqtt,ble]'` (или `[mqtt]` + `[ble]`).
- `pip install 'lovensepy[mqtt]'` (добавьте `ble` для BLE-транспорта)

### Шаг 1: Переменные окружения

**LAN (по умолчанию):**

```bash
export LOVENSE_TRANSPORT=lan          # по умолчанию; можно явно
export LOVENSE_LAN_IP=192.168.1.100   # хост с Lovense Remote (Game Mode)
export MQTT_HOST=192.168.1.2
export MQTT_PORT=1883
# опционально: MQTT_USER, MQTT_PASSWORD, MQTT_TOPIC_PREFIX=lovensepy
```

**BLE:**

```bash
export LOVENSE_TRANSPORT=ble
# LOVENSE_LAN_IP не нужен; Toy Events в BLE-режиме не используются
export MQTT_HOST=192.168.1.2
# опционально: LOVENSE_BLE_DISCOVER_TIMEOUT (сек, по умолчанию 15), LOVENSE_BLE_NAME_PREFIX (по умолчанию LVS-)
```

### Шаг 2: Пример моста

```bash
python examples/ha_mqtt_bridge.py
```

### Шаг 3: Home Assistant

В Home Assistant: **Settings** → **Devices & Services** → **MQTT**. Новые устройства должны появиться через MQTT discovery (управление поддерживаемыми моторами на игрушку, **Stop**, **Preset**, **Battery** и т.п.).

### Шаг 4: Разрешение Toy Events

Выдайте доступ Toy Events, когда Remote запросит (как в руководстве [События игрушек](toy-events.md#toy-events-tutorial)).

## Раскладка топиков

Префикс по умолчанию `lovensepy`: командные топики вида `lovensepy/<safe_toy_id>/<feature>/set` (например `vibrate`, `rotate`, `preset`, `stop`). Мост публикует удерживаемую доступность на `lovensepy/bridge/status` (`online` / `offline`) и по игрушке на `lovensepy/<safe_toy_id>/device_availability`, чтобы Home Assistant помечал сущности недоступными при обрыве BLE или когда GetToys даёт `status` off (обновляется при каждом refresh; уменьшите `refresh_interval` для более быстрых переходов).

![Панель Home Assistant: игрушки Lovense через MQTT Discovery](../images/ha_mqtt_dashboard.png)

## Программный запуск

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
    # ... держим работу ...
    await bridge.stop()

asyncio.run(main())
```

**BLE** (скан, подключение, те же MQTT-топики; состояние обновляется периодическим `get_toys`):

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

**Продвинутый вариант:** заранее собранный :class:`~lovensepy.ble_direct.hub.BleDirectHub` с `transport="ble"` и `ble_hub=hub` (после `add_toy` / `connect` или своего `discover_and_connect`). При :meth:`~lovensepy.integrations.mqtt.ha_bridge.HAMqttBridge.stop` мост вызовет :meth:`~lovensepy.ble_direct.hub.BleDirectHub.aclose`.
