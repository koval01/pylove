# Прямой BLE {#direct-ble}

!!! warning "Совместимость"
    Lovense не публикует стабильный BLE-контракт для сторонних приложений. Поведение UART по умолчанию работает на многих устройствах, но **не гарантируется** для каждой модели или прошивки.

`BleDirectHubSync` / `BleDirectHub` рассчитаны **рядом с** `LANClient` / `AsyncLANClient` и `ServerClient` / `AsyncServerClient`: тот же поток `get_toys`, `function_request`, `play`, `preset_request`, `pattern_request`, `stop` после подключения. Асинхронный хаб и :class:`~lovensepy.ble_direct.client.BleDirectClient` реализуют **`LovenseAsyncControlClient`** вместе с другими асинхронными транспортами. См. [Способы подключения — Один код управления, разный транспорт](connection-methods.md#same-control-code-different-transport) и [Справочник API — LovenseAsyncControlClient](api-reference.md#lovenseasynccontrolclient).

## Установка

```bash
pip install 'lovensepy[ble]'
```

Нужен рабочий Bluetooth-адаптер и права ОС. Многие игрушки допускают **только один BLE central** — отключите **Lovense Remote** (или другое приложение) перед подключением с вашей машины.

## Быстрый старт (как у LAN)

Используйте **`BleDirectHubSync`** для обычных скриптов: блокирующие вызовы, те же имена методов, что у **`LANClient`**, где BLE поддерживает (`get_toys`, `play`, `function_request`, `preset_request`, `pattern_request`, `stop`, …).

```python
import time
from lovensepy import BleDirectHubSync, Actions, Presets, features_for_toy

with BleDirectHubSync() as client:
    client.discover_and_connect(timeout=10.0)

    response = client.get_toys()
    toys = {toy.id: toy.model_dump() for toy in response.data.toys} if response.data else {}

    # Как в LAN-руководстве: вибрация на время блока, затем авто-stop.
    # На BLE при time>0 время соблюдается внутри function_request (блокирует), а LAN
    # отправляет timeSec в приложение и сразу возвращается — time=0 + time.sleep как у LAN.
    with client.play({Actions.VIBRATE: 10}, time=0):
        time.sleep(5)

    client.preset_request(Presets.PULSE, time=5)
    time.sleep(5)

    client.pattern_request([5, 10, 15, 20], time=4)
    time.sleep(4)

    client.stop()
```

**Таймер одной строкой (специфика BLE):** `client.function_request({Actions.VIBRATE: 10}, time=5)` уже ждёт удержание и внутреннюю остановку мотора — без лишнего `time.sleep` и без `play`.

**Одна игрушка или все:** передавайте `toy_id` из `get_toys()` в `play`, `function_request`, `preset_request` или `pattern_request`. Не указывайте (по умолчанию `None`), чтобы адресовать все игрушки на хабе.

### По игрушке и по мотору (двойные вибраторы) {: #per-toy-and-per-motor-dual-vibrators}

Тот же `toy_id` и **`Actions.VIBRATE1`** / **`Actions.VIBRATE2`**, что в LAN. По каждой строке смотрите каналы через **`features_for_toy`** на `model_dump()`.

Если вставляете только этот фрагмент в REPL, один раз выполните: `from lovensepy import features_for_toy` (уже есть в импорте быстрого старта выше).

```python
import time
from lovensepy import Actions, Presets, features_for_toy  # можно опустить, если импорт из быстрого старта

# `client` — BleDirectHubSync после discover_and_connect; `toys` из get_toys() как выше

for tid, row in toys.items():
    client.function_request({Actions.VIBRATE: 8}, time=2, toy_id=tid)
    time.sleep(0.3)

first_id, first_row = next(iter(toys.items()))
if "Vibrate1" in features_for_toy(first_row) and "Vibrate2" in features_for_toy(first_row):
    client.function_request({Actions.VIBRATE1: 12}, time=2, toy_id=first_id)
    time.sleep(0.25)
    client.function_request({Actions.VIBRATE2: 6}, time=2, toy_id=first_id)

client.preset_request(Presets.WAVE, time=4, toy_id=first_id)
client.pattern_request([4, 8, 12], time=3, toy_id=first_id, actions=[Actions.VIBRATE2])
```

На BLE лучше короткие паузы между подряд идущими командами на двухмоторных игрушках, если стек хоста теряет записи (см. устранение неполадок ниже).

## Асинхронный код

Внутри `async def` используйте **`BleDirectHub`** и `await` (те же методы с префиксом `await`):

```python
import asyncio
from lovensepy import BleDirectHub, Actions

async def main() -> None:
    hub = BleDirectHub()
    try:
        await hub.discover_and_connect(timeout=10.0)
        response = await hub.get_toys()
        _ = response
        await hub.function_request({Actions.VIBRATE: 10}, time=5, toy_id=None)
    finally:
        await hub.disconnect_all()

asyncio.run(main())
```

Поддерживается `async with hub:` как контекстный менеджер.

## Замечания

- **Встроенные пресеты** (`pulse`, `wave`, `fireworks`, `earthquake`): по BLE клиент шлёт **`Pat:{n};`** или **`Preset:{n};`** (целое **`n`**). :class:`~lovensepy.ble_direct.client.BleDirectClient` по умолчанию **`Pat`**; часть прошивок / публичной UART-доки ждёт **`Preset`**. Префикс задаётся конструктором **`ble_preset_uart_keyword`**. Имена мапятся через :data:`~lovensepy.PRESET_BLE_PAT_INDEX` (по умолчанию **1–4**); можно передать **`name`** только из цифр (0–20) для сырого слота. Если игрушка **игнорирует Pat/Preset**, но **шаги паттерна работают**, используйте **`ble_preset_emulate_with_pattern=True`** или FastAPI **`LOVENSEPY_BLE_PRESET_EMULATE_PATTERN=1`** (переподключитесь после смены). Иначе — **`/command/pattern`**. **FastAPI BLE** по умолчанию **`Preset`** на **`/ble/connect`**; **`LOVENSEPY_BLE_PRESET_UART=Pat`** переключает на тот же **`Pat`**, что у прямого BLE-клиента по умолчанию.
- **Несколько игрушек:** `discover_and_connect` регистрирует каждого подходящего рекламодателя (префикс имени по умолчанию **`LVS-`**) и открывает по одному `BleDirectClient` на адрес.
- **macOS:** `connect` / discovery периферии **сериализованы** между клиентами, чтобы снизить нестабильность CoreBluetooth.
- **Таймауты в sync:** `BleDirectHubSync` крутит BLE на фоновом цикле asyncio. Каждый вызов ждёт до **`LOVENSEPY_BLE_SYNC_TIMEOUT`** секунд (по умолчанию **300**; `0`, `none` или `inf` = без ограничения). **Не** используйте `BleDirectHubSync` из кода, где уже крутится asyncio-цикл — берите `BleDirectHub` и `await`.
- **Потеря связи:** по умолчанию клиент может переподключиться и послать UART stop burst; остановятся ли моторы без UART — **зависит от прошивки**. См. **`silence_on_link_loss`** у `BleDirectClient` в справочнике.
- **Ошибки и повторы GATT:** различие [`LovenseBLEError`](api-reference.md#exceptions-and-error-handling) и HTTP (авторизация, таймауты) — в [справочнике](api-reference.md#exceptions-and-error-handling). При **кратковременных** сбоях радио/GATT передайте **`gatt_write_max_attempts`** &gt; `1` и при необходимости **`gatt_write_retry_*`** в **`add_toy` / `discover_and_connect`** через `**client_kwargs` — повторяются отдельные записи TX с backoff (это не полный цикл сессии как **`auto_reconnect`** у Socket; при жёстком обрыве снова **`connect`** или **`discover_and_connect`**).

## Где читать дальше

- **Конструкторы, настройка UART, двухмоторное поведение:** [Справочник API — BleDirectClient / хаб](api-reference.md#bledirectclient).
- **Типы исключений и порядок обработки:** [Исключения и обработка ошибок](api-reference.md#exceptions-and-error-handling).
- **Интерактивное сканирование / CLI с множественным выбором:** `python examples/ble_direct_scan_and_two.py`.
- **Интеграционный тест железа** (реальное радио): `uv run --extra ble pytest tests/test_ble_direct_integration.py -v -s`.

## Устранение неполадок (в логах всё хорошо, моторы тихие)

- **Два мотора (Edge / Diamo):** два GATT write на обновление; попробуйте `write_with_response=True` в `client_kwargs` у `add_toy` / `discover_and_connect` или увеличьте `uart_inter_command_delay_s`. После таймированного `function_request` клиент ненадолго ждёт перед следующей командой (`post_timed_function_silence_cooldown_s`).
- **Стек хоста (особенно macOS):** увеличьте паузы между шагами; интеграционный сценарий учитывает `LOVENSE_BLE_INTER_STEP_SEC` и связанные `LOVENSE_BLE_DUAL_PROBE_*`.
