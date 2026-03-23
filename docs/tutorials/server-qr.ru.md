# Server API и сопряжение по QR

### Шаг 1: Токен разработчика

Получите токен в [Lovense Developer Dashboard](https://developer.lovense.com).

### Шаг 2: Callback URL

Настройте callback URL (например ngrok) и укажите его в Dashboard. Lovense будет POST’ить на этот URL, когда пользователь отсканирует QR.

### Шаг 3: Запросите QR-код

```python
from lovensepy import get_qr_code

qr_data = get_qr_code(developer_token="YOUR_TOKEN", uid="user_123")
qr_url = qr_data["qr"]   # URL картинки для сканирования
code = qr_data["code"]   # 6-символьный код для Remote
print(f"Scan QR: {qr_url}")
```

### Шаг 4: Пользователь сканирует QR

Пользователь сканирует QR в Lovense Remote.

### Шаг 5: Тело callback

Lovense POST’ит на callback URL с `uid` и `toys`. Сервер сохраняет `uid`.

### Шаг 6: Создайте `ServerClient`

```python
from lovensepy import ServerClient, Actions

client = ServerClient(developer_token="YOUR_TOKEN", uid="user_123")
```

Для кода с **`async def`** (боты, FastAPI, воркеры) используйте **`AsyncServerClient`**; он реализует **`LovenseAsyncControlClient`** вместе с **`AsyncLANClient`** и асинхронными BLE-клиентами — можно аннотировать один абстрактный клиент и менять транспорт. См. [LovenseAsyncControlClient](../api-reference.md#lovenseasynccontrolclient).

### Шаг 7: Отправка команд

Те же высокоуровневые методы, что у LAN (например `function_request`):

```python
import time

client.function_request({Actions.VIBRATE: 10}, time=5)
time.sleep(5)
client.stop()
```
