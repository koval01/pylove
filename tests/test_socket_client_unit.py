import asyncio
from typing import Any

from lovensepy.exceptions import LovenseDeviceOfflineError
from lovensepy.socket_api.client import SocketAPIClient


class _FakeTransport:
    def __init__(self):
        self.is_connected = False
        self.sent: list[str] = []

    async def connect(self) -> bool:
        self.is_connected = True
        return True

    async def send(self, message: str) -> bool:
        self.sent.append(message)
        return self.is_connected

    async def receive(self):
        # Keep connection alive briefly until closed by test.
        while self.is_connected:
            await asyncio.sleep(0.01)
            if False:
                yield ""
        return
        yield  # pragma: no cover

    def close(self) -> None:
        self.is_connected = False


def test_connect_is_non_blocking_and_disconnect_sets_closed():
    async def _runner():
        c = SocketAPIClient("wss://example")
        c._transport = _FakeTransport()  # type: ignore[assignment]

        await c.connect()
        assert c._runner_task is not None
        assert not c._runner_task.done()

        c.disconnect()
        await c.wait_closed()
        assert c._closed.is_set()

    asyncio.run(_runner())


def test_connect_with_retry_retries_until_limit():
    async def _runner():
        c = SocketAPIClient("wss://example")
        calls = {"n": 0}

        async def fake_run_forever():
            calls["n"] += 1

        c.run_forever = fake_run_forever  # type: ignore[method-assign]
        await c.connect_with_retry(retry_delay=0.0, max_retries=2)
        assert calls["n"] == 3

    asyncio.run(_runner())


def test_event_router_dispatches_global_and_specific_handlers():
    async def _runner():
        seen: list[tuple[str, Any]] = []

        def on_event(event: str, payload: Any) -> None:
            seen.append(("global", (event, payload)))

        c = SocketAPIClient("wss://example", on_event=on_event)

        @c.on("my_event")
        async def _my_event(payload: Any) -> None:
            seen.append(("specific", payload))

        await c._dispatch_event("my_event", {"ok": True})
        await asyncio.sleep(0)
        assert ("global", ("my_event", {"ok": True})) in seen
        assert ("specific", {"ok": True}) in seen

    asyncio.run(_runner())


def test_event_handler_exceptions_do_not_break_dispatch_loop():
    async def _runner():
        seen: list[str] = []

        async def bad_handler(payload: Any) -> None:
            _ = payload["missing"]  # raises KeyError

        async def good_handler(payload: Any) -> None:
            seen.append("good")

        def failing_on_event(event: str, payload: Any) -> None:
            raise ValueError("boom")

        c = SocketAPIClient("wss://example", on_event=failing_on_event)
        c.add_event_handler("my_event", bad_handler)
        c.add_event_handler("my_event", good_handler)

        # Must not raise despite user callback errors.
        await c._dispatch_event("my_event", {"ok": True})
        await asyncio.sleep(0)
        assert "good" in seen

    asyncio.run(_runner())


def test_send_command_uses_async_lan_client_without_threads():
    async def _runner():
        class _FakeLanClient:
            def __init__(self):
                self.payloads: list[dict[str, Any]] = []

            async def send_command(self, payload: dict[str, Any]) -> None:
                self.payloads.append(payload)

        c = SocketAPIClient("wss://example")
        c._lan_client = _FakeLanClient()  # type: ignore[assignment]
        c.send_command("Function", "Vibrate:10", toy="t1")
        await asyncio.sleep(0)
        assert c._lan_client.payloads  # type: ignore[union-attr]
        assert c._lan_client.payloads[-1]["toy"] == "t1"  # type: ignore[union-attr]

    asyncio.run(_runner())


def test_send_command_await_local_offline_does_not_raise():
    async def _runner():
        class _FakeLanClient:
            async def send_command(self, payload: dict[str, Any]) -> None:
                raise LovenseDeviceOfflineError("offline")

        c = SocketAPIClient("wss://example")
        c._lan_client = _FakeLanClient()  # type: ignore[assignment]

        # Should swallow offline errors (reporting via logs/warnings).
        await c.send_command_await("Function", "Stop", time_sec=0, toy="t1")

    asyncio.run(_runner())
