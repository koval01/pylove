# Сервис FastAPI (LAN + BLE) {#fastapi-lan-rest-tutorial}

**HTTP API** для дашбордов, скриптов или мобильных приложений: **FastAPI** + **OpenAPI** на `/docs` и планировщик **asyncio** (слоты `Function` по моторам, сессии preset/pattern, `GET /tasks`). Реализация — **`lovensepy.services.fastapi`** (пакет **`lovensepy.services`**): в **LAN** используется **Game Mode** (`AsyncLANClient`); в **BLE** — **`BleDirectHub`** с ручным сканом/подключением. Оба бэкенда удовлетворяют **`LovenseControlBackend`**, протоколу, согласованному с поверхностью **`LovenseAsyncControlClient`**, которую использует планировщик (см. [Справочник API — LovenseAsyncControlClient](../api-reference.md#lovenseasynccontrolclient)).

## Требования

```bash
pip install 'lovensepy[service]'
# для BLE-режима ещё:
pip install 'lovensepy[ble]'
```

## LAN-режим (по умолчанию)

### Окружение

```bash
export LOVENSE_LAN_IP=192.168.1.100   # хост с Lovense Remote (Game Mode)
export LOVENSE_SERVICE_MODE=lan        # по умолчанию; можно опустить
# опционально: LOVENSE_LAN_PORT=20011 LOVENSE_APP_NAME=... LOVENSE_TOY_IDS=id1,id2
# опционально: LOVENSE_SESSION_MAX_SEC=60  # строка /tasks при time=0 у preset/pattern
```

### Запуск сервера

```bash
uvicorn lovensepy.services.fastapi.app:app --host 0.0.0.0 --port 8000
```

Устаревшая обёртка (предупреждение при импорте):

```bash
uvicorn examples.fastapi_lan_api:app --host 0.0.0.0 --port 8000
```

### Программная настройка

```python
from lovensepy.services import ServiceConfig, create_app

app = create_app(ServiceConfig(mode="lan", lan_ip="192.168.1.100"))
```

Колбэки BLE-рекламы (только BLE-режим, см. ниже): передайте `on_ble_advertisement` и/или `on_ble_advertisement_async` в `create_app(...)`.

## BLE-режим

Вместо Game Mode — прямой BLE. Игрушки **не** подключаются автоматически: скан, затем `POST /ble/connect` (или колбэки для `BleDirectHub.add_toy` / `connect`).

```bash
export LOVENSE_SERVICE_MODE=ble
# опционально: LOVENSE_BLE_SCAN_TIMEOUT=8 LOVENSE_BLE_SCAN_PREFIX=LVS-  (пустой префикс = все имена)
# опционально пассивные обновления RSSI: LOVENSE_BLE_ADVERT_MONITOR=1 LOVENSE_BLE_ADVERT_MONITOR_INTERVAL=2
# опционально пресеты: LOVENSEPY_BLE_PRESET_UART=Pat   (как у BleDirectClient по умолчанию; сервис по умолчанию Preset для /command/preset)
# опционально: LOVENSEPY_BLE_PRESET_EMULATE_PATTERN=1  (pulse/wave/… через паттерн, если UART пресеты игнорируются)
uvicorn lovensepy.services.fastapi.app:app --host 0.0.0.0 --port 8000
```

Дополнительные HTTP-маршруты (только BLE):

- `POST /ble/scan` — скан по запросу; query `timeout` опционально; ответ: `address`, `name`, `rssi`
- `GET /ble/advertisements` — последняя карта рекламы при включённом мониторе
- `POST /ble/connect` — тело: `address`, опционально `toy_id`, `name`, `toy_type`, `replace`
- `POST /ble/disconnect/{toy_id}` — отключение GATT (регистрация игрушки остаётся)
- `DELETE /ble/toys/{toy_id}` — отключение и снятие регистрации

`GET /toys` и командные маршруты совпадают с LAN после подключения игрушек.

## OpenAPI

Откройте `http://127.0.0.1:8000/docs` и попробуйте `GET /toys`, `POST /command/preset`, `GET /tasks` и эндпоинты стопа (`/command/stop/...` и пакетные варианты).

## Замечания по поведению

- **BLE:** паттерны (и зацикленный ``Function``) могут удерживать работу, пока :class:`~lovensepy.ble_direct.client.BleDirectClient` шагает по UART. **Пресеты** в этом сервисе по умолчанию через UART ``Preset:{n};`` (``LOVENSEPY_BLE_PRESET_UART=Pat`` — как у прямого BLE-клиента по умолчанию). С ``LOVENSEPY_BLE_PRESET_EMULATE_PATTERN=1`` четыре имени приложения идут через шаги паттерна (как ``/command/pattern``). Таймированные пресеты при ``wait_for_completion=False`` откладывают удержание + stop burst. У прямого :class:`~lovensepy.ble_direct.client.BleDirectClient` по умолчанию ``wait_for_completion=True``.
- Повторная отправка **того же** пресета или паттерна для той же игрушки **продлевает** сессию и **шлёт ещё одну транспортную команду** с новым `time` (Lovense иначе гасит после `timeSec` каждой команды).
- `GET /tasks` возвращает строки **function** (`kind: function`), **function_loop** при `loop_on_time` / `loop_off_time` у `POST /command/function`, и **preset** / **pattern** (`kind: preset` / `pattern`). В метках времени есть `started_at` (UTC) и `started_monotonic_sec` для стабильного `remaining_sec`.

См. также строку [Примеры](../appendix.md#examples) про HTTP-сервис.
