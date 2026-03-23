# Socket API

Socket API **только асинхронный**. Используйте `asyncio.run()` для точки входа.

### Шаг 1: Токен авторизации

```python
from lovensepy import get_token

auth_token = get_token(
    developer_token="YOUR_TOKEN",
    uid="user_123",
    uname="User"
)
```

### Шаг 2: URL сокета

Аргумент `platform` должен **точно** совпадать с **Website Name** в Lovense Developer Dashboard.

```python
from lovensepy import get_socket_url

socket_info = get_socket_url(auth_token, platform="Your App")
```

### Шаг 3: WebSocket URL

```python
from lovensepy import build_websocket_url

ws_url = build_websocket_url(socket_info, auth_token)
```

### Шаг 4: Подключение

```python
import asyncio
from lovensepy import SocketAPIClient

async def main():
    client = SocketAPIClient(ws_url, on_event=lambda e, p: print(e, p))
    await client.connect()  # фоновые циклы стартуют и быстро возвращаются
```

### Шаг 5: Запрос QR, когда Socket.IO готов

```python
    client_ref = []

    def on_connected():
        client_ref[0].send_event("basicapi_get_qrcode_ts", {"ackId": "1"})

    client = SocketAPIClient(ws_url, on_socket_io_connected=on_connected, on_event=...)
    client_ref.append(client)
```

### Шаг 6: Информация об устройстве после скана

Пользователь сканирует QR. Приходит `basicapi_update_device_info_tc` со списком игрушек в payload.

### Шаг 7: Отправка команд

Когда `client.is_socket_io_connected` истинно:

```python
    if client.is_socket_io_connected:
        client.send_command("Function", "Vibrate:10", time_sec=5, toy="toy_id")
```

### Шаг 8: Критичные стопы с ожиданием

```python
    await client.send_command_await("Function", "Stop", time_sec=0, toy="toy_id")
```

### Шаг 9: Долгоживущие соединения

```python
    # Держим соединение даже после кратковременных обрывов.
    runner = client.start_background(auto_reconnect=True, retry_delay=5.0)
```

Можно также вызывать `await client.connect_with_retry(retry_delay=5.0)` напрямую.

### Локальные команды в той же LAN

Передайте `use_local_commands=True`, чтобы после скана QR команды шли по HTTPS на устройство, а не только по WebSocket в облако.
