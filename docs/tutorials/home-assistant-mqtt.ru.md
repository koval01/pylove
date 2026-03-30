# MQTT-мост Home Assistant

Запустите небольшой **процесс-мост**: он публикует сущности **MQTT Discovery** в Home Assistant и пересылает команды по **LAN** (Game Mode Lovense Remote) или **прямому BLE** (Bluetooth этой машины к периферии `LVS-…`).

## Требования

- Доступный с машины с мостом MQTT-брокер (например Mosquitto на `192.168.1.2:1883`)
- Интеграция **MQTT** в Home Assistant на том же брокере
- **LAN-режим:** Lovense **Remote** с включённым **Game Mode** (не Connect для Toy Events)
- **BLE-режим:** Bluetooth-адаптер на хосте с мостом; игрушки должны быть доступны ОС (часто **эксклюзивно** с BLE-связью Remote). Установите `pip install 'lovensepy[mqtt,ble]'` (или `[mqtt]` + `[ble]`).
- `pip install 'lovensepy[mqtt]'` (добавьте `ble` для BLE-транспорта)

## Home Assistant с BLE (полная схема)

BLE идёт через **Bleak** и стек Bluetooth ОС. Процесс моста нужно запускать **нативно на машине с рабочим Bluetooth** (ноутбук, Raspberry Pi и т.д.). **Не запускайте BLE-мост в стандартном Docker-образе моста** — у контейнера обычно нет доступа к Bluetooth.

**Home Assistant** и **Mosquitto** при этом могут быть в Docker (или установлены иначе), главное — чтобы **брокер MQTT был доступен** с хоста, где крутится мост. Типичная раскладка:

| Компонент | Где работает |
|-----------|----------------|
| Mosquitto | Docker или пакет ОС (порт 1883 доступен с хоста моста) |
| Home Assistant | Docker, HA OS и т.д. — интеграция MQTT на **тот же брокер** |
| LovensePy `HAMqttBridge` | **На хосте** с `transport="ble"`, `pip install 'lovensepy[mqtt,ble]'` |

### A) Docker Compose только HA + Mosquitto, мост на хосте (BLE)

Из корня репозитория (Compose поднимает **только Mosquitto и Home Assistant**; мост всегда на хосте):

```bash
cp .env.example .env

docker compose up -d
```

(Можно явно: `docker compose up -d mqtt homeassistant` — те же два сервиса.)

Брокер проброшен на хост (по умолчанию `MQTT_PUBLISH_PORT=1883`). На **той же машине** ставим мост и указываем localhost:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install 'lovensepy[mqtt,ble]'

export LOVENSE_TRANSPORT=ble
export MQTT_HOST=127.0.0.1
export MQTT_PORT=1883
# опционально: LOVENSE_BLE_DISCOVER_TIMEOUT, LOVENSE_BLE_NAME_PREFIX, MQTT_TOPIC_PREFIX

python -m lovensepy.services.mqtt_bridge
```

В Home Assistant добавьте интеграцию **MQTT**: **Настройки → Устройства и службы → Добавить интеграцию → MQTT** — брокер **`mqtt`**, порт **1883**, без TLS (как в `compose/mosquitto.conf`). HA и Mosquitto в одной Docker-сети; мост на хосте ходит в брокер через `127.0.0.1` на опубликованный порт.

Если HA или брокер на **другой машине**, задайте `MQTT_HOST` как **LAN-IP брокера** (и откройте порт в файрволе), а не `127.0.0.1`.

### B) Без Docker: брокер + HA + мост на одном ПК

Поставьте Mosquitto и Home Assistant своим способом ([официальная установка HA](https://www.home-assistant.io/installation/)). Установите `lovensepy[mqtt,ble]`, выставьте `LOVENSE_TRANSPORT=ble` и `MQTT_HOST` на адрес брокера, запустите `python -m lovensepy.services.mqtt_bridge` (или `lovensepy-mqtt`). Дальше то же: один MQTT-брокер, интеграция MQTT в HA, мост публикует Discovery на этот брокер.

### Bluetooth и доступ

- **macOS:** разрешите **Bluetooth** для терминала/IDE, из которого запускаете Python (**Системные настройки → Конфиденциальность и безопасность → Bluetooth**).
- **Linux:** часто нужна группа `bluetooth` и работающий BlueZ.
- **Windows:** Bleak через WinRT; Bluetooth должен быть включён.

### Lovense Remote и BLE

У многих игрушек **одно BLE-подключение**. Если телефон с Remote уже держит BLE, мост с ПК может не подключиться — отключите игрушку в Remote или используйте **LAN** для моста.

### Toy Events

**Toy Events** (живые батарея/сила по WebSocket) относятся к **LAN**-режиму. В **BLE** Toy Events не используются; состояние обновляется опросом `get_toys` по интервалу refresh.

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

### Шаг 2: Запуск сервиса моста

```bash
python -m lovensepy.services.mqtt_bridge
```

Эквивалент: `lovensepy-mqtt` после `pip install 'lovensepy[mqtt]'`. Файл `examples/ha_mqtt_bridge.py` — тонкая обёртка к той же точке входа.

### Шаг 3: Home Assistant

В Home Assistant: **Settings** → **Devices & Services** → **MQTT**. Новые устройства должны появиться через MQTT discovery (управление поддерживаемыми моторами на игрушку, **Stop**, **Preset**, **Battery** и т.п.).

### Шаг 4: Разрешение Toy Events (только LAN)

Для **LAN** и при желании Toy Events выдайте доступ, когда Remote запросит (как в [События игрушек](toy-events.md#toy-events-tutorial)). В **BLE** Toy Events не используются.

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
