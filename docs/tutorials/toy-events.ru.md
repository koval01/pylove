# События игрушек {#toy-events-tutorial}

Toy Events работают **только с Lovense Remote** (порт **20011**). Lovense Connect Toy Events не поддерживает.

### Шаг 1: Remote и Game Mode

Используйте Lovense Remote с включённым Game Mode. Порт обычно **20011**.

### Шаг 2: Клиент и callback

```python
import asyncio
from lovensepy import ToyEventsClient

def on_event(event_type, payload):
    print(event_type, payload)

client = ToyEventsClient(
    "192.168.1.100",
    port=20011,
    app_name="My App",
    on_event=on_event
)
```

### Шаг 3: Подключение

```python
async def main():
    await client.connect()

asyncio.run(main())
```

### Шаг 4: Запрос доступа

Пользователь выдаёт доступ, когда Remote показывает **Allow [My App] to access?**

### Шаг 5: Поток событий

Приходят события вроде `toy-list`, `button-down`, `function-strength-changed`, `shake`.
