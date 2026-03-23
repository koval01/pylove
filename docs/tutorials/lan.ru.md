# LAN Game Mode и прямой BLE-хаб

Вызовы в стиле **Standard** ниже (`get_toys`, `play`, `preset_request`, `pattern_request`, `stop`) общие с [**Standard Server**](../api-reference.md#serverclient) (`ServerClient` / `AsyncServerClient` с token + `uid`) и [**прямым BLE**](../direct-ble.md) (`BleDirectHubSync` / `BleDirectHub` после `discover_and_connect`). Меняйте класс клиента и настройку подключения; середина скрипта остаётся.

Для кода с **`async def`** клиент можно аннотировать как **`LovenseAsyncControlClient`**, чтобы одно тело функции работало с `AsyncLANClient`, `AsyncServerClient`, `BleDirectHub` или `BleDirectClient` — см. [LovenseAsyncControlClient](../api-reference.md#lovenseasynccontrolclient).

## Game Mode (LAN)

### Шаг 1: Включите Game Mode

- Lovense Remote: **Discover** → **Game Mode** → **Enable LAN**
- Lovense Connect: **Scan QR** → **Other connection modes** → **IP Address**

### Шаг 2: Запишите IP и порт

- Lovense Remote: обычно **20011** (HTTP) или **30011** (HTTPS)
- Lovense Connect: обычно **34567**

### Шаг 3: Создайте клиента

```python
from lovensepy import LANClient

client = LANClient("MyApp", "192.168.1.100", port=20011)
```

### Шаг 4: Список подключённых игрушек

```python
response = client.get_toys()
toys = {toy.id: toy.model_dump() for toy in response.data.toys} if response.data else {}
# toys — {toy_id: toy_info}
```

### Шаг 5: Одна игрушка или один мотор {: #step-5-one-toy-at-a-time-or-one-motor-at-a-time}

Передавайте **`toy_id`** (строка из `get_toys` или список id) в `function_request`, `play`, `preset_request`, `pattern_request` и `stop`. Не указывайте — команда пойдёт на **все** игрушки, которые видит приложение.

Двухмоторные модели (например Edge) отдают **`Vibrate1`** и **`Vibrate2`** как отдельные каналы. В словаре действий используйте **`Actions.VIBRATE1`** / **`Actions.VIBRATE2`**. Поддержку каналов смотрите в **`features_for_toy`** (тот же словарь, что `toy.model_dump()`).

Если вставляете только фрагмент ниже (например в REPL), выполните: `from lovensepy import Actions, Presets, features_for_toy` — или расширьте импорты шагов 3–4.

```python
import time
from lovensepy import Actions, Presets, features_for_toy

# Каждая подключённая игрушка — та же команда по очереди
for tid, row in toys.items():
    client.function_request({Actions.VIBRATE: 8}, time=2, toy_id=tid)
    time.sleep(0.3)

# Одна игрушка, два мотора по отдельности (если у игрушки оба канала)
edge_id = next(iter(toys))  # в реальном коде выберите нужный id
if "Vibrate1" in features_for_toy(toys[edge_id]) and "Vibrate2" in features_for_toy(toys[edge_id]):
    client.function_request({Actions.VIBRATE1: 12}, time=2, toy_id=edge_id)
    time.sleep(0.2)
    client.function_request({Actions.VIBRATE2: 6}, time=2, toy_id=edge_id)

# Пресет / паттерн на одной игрушке
client.preset_request(Presets.PULSE, time=4, toy_id=edge_id)
client.pattern_request([5, 10, 15], time=3, toy_id=edge_id, actions=[Actions.VIBRATE1])
```

Паттерны по умолчанию идут на общий канал **Vibrate**; передайте **`actions=[Actions.VIBRATE1]`** (или список каналов), чтобы крутить конкретный мотор, если API позволяет.

### Шаг 6: Function с авто-остановкой

```python
import time
from lovensepy import Actions

# Вибрация уровня 10 на 5 с; при выходе из контекста игрушка останавливается.
with client.play({Actions.VIBRATE: 10}, time=5):
    time.sleep(5)
```

### Шаг 7: Пресеты и паттерны (опционально)

```python
from lovensepy import Presets

client.preset_request(Presets.PULSE, time=5)
time.sleep(5)

# Пользовательский паттерн: список уровней силы (0–20)
client.pattern_request([5, 10, 15, 20], time=4)
time.sleep(4)

client.stop()
```

## Прямой BLE

LAN Game Mode не обязателен: машина говорит с игрушкой по Bluetooth. Установите `pip install 'lovensepy[ble]'`, отключите Lovense Remote от игрушек и следуйте **[Прямому BLE](../direct-ble.md)** — тот же поток **`get_toys` → `play` / `function_request` → пресеты / паттерны → `stop`**, с **`BleDirectHubSync`** в скриптах или **`BleDirectHub`** с `await` в async-коде.

## Полный пример LAN

```python
import time
from lovensepy import LANClient, Actions, Presets, features_for_toy

client = LANClient("MyApp", "192.168.1.100", port=20011)

# Список игрушек
toys_response = client.get_toys()
toys = {toy.id: toy.model_dump() for toy in toys_response.data.toys} if toys_response.data else {}
print("Toys:", toys)

# Пресет
client.preset_request(Presets.PULSE, time=5)
time.sleep(5)

# Function
client.function_request({Actions.ALL: 5}, time=3)
time.sleep(3)

# Паттерн
client.pattern_request([5, 10, 15, 20], time=4)
time.sleep(4)

# Вибрация по игрушкам, затем по моторам первой, если два вибратора
for tid, row in toys.items():
    client.function_request({Actions.VIBRATE: 7}, time=2, toy_id=tid)
    time.sleep(0.25)
if toys:
    tid0, row0 = next(iter(toys.items()))
    feats = features_for_toy(row0)
    if "Vibrate1" in feats and "Vibrate2" in feats:
        client.function_request({Actions.VIBRATE1: 10}, time=2, toy_id=tid0)
        time.sleep(0.2)
        client.function_request({Actions.VIBRATE2: 8}, time=2, toy_id=tid0)

# Стоп
client.stop()
```
