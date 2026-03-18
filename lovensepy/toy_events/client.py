"""
Toy Events API: WebSocket client for receiving toy events.

Business logic: Toy Events protocol (access, ping, event types).
Transport: WsTransport (lovensepy.transport).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from .._utils import ip_to_domain
from ..transport import WsTransport

PING_INTERVAL = 5.0  # seconds


class ToyEventsClient:
    """
    Toy Events API client.

    Receives real-time events: toy-list, toy-status, button-down, button-up,
    function-strength-changed, shake, battery-changed, motion-changed, event-closed.
    """

    def __init__(
        self,
        ip: str,
        port: int = 20011,
        use_https: bool = False,
        https_port: int = 30011,
        app_name: str = "lovensepy",
        *,
        on_open: Callable[[], Awaitable[None] | None] | None = None,
        on_close: Callable[[], Awaitable[None] | None] | None = None,
        on_error: Callable[[Exception], Awaitable[None] | None] | None = None,
        on_event: Callable[[str, Any], Awaitable[None] | None] | None = None,
    ) -> None:
        if use_https:
            domain = ip_to_domain(ip)
            url = f"wss://{domain}:{https_port}/v1"
        else:
            # Unencrypted WebSocket for local LAN; use use_https=True for WSS
            scheme, port_str = "ws", str(port)
            url = f"{scheme}://{ip}:{port_str}/v1"
        self._transport = WsTransport(url)
        self._app_name = app_name
        self._on_open = on_open
        self._on_close = on_close
        self._on_error = on_error
        self._on_event = on_event
        self._ping_task: asyncio.Task | None = None
        self._recv_task: asyncio.Task | None = None
        self._access_granted = False

    @property
    def is_connected(self) -> bool:
        """True if WebSocket transport is connected."""
        return self._transport.is_connected

    @property
    def is_access_granted(self) -> bool:
        """True if toy access has been granted by the app."""
        return self._access_granted

    async def connect(self) -> None:
        """Connect, request access, and receive events until disconnected."""
        self.disconnect()
        ok = await self._transport.connect()
        if not ok:
            if self._on_error:
                cb = self._on_error(ConnectionError("WebSocket connect failed"))
                if asyncio.iscoroutine(cb):
                    await cb
            return

        if self._on_open:
            cb = self._on_open()
            if asyncio.iscoroutine(cb):
                await cb

        # Toy Events protocol: request access
        await self._send_json({"type": "access", "data": {"appName": self._app_name}})

        self._ping_task = asyncio.create_task(self._ping_loop())
        self._recv_task = asyncio.create_task(self._recv_loop())
        try:
            await asyncio.gather(self._ping_task, self._recv_task)
        except asyncio.CancelledError:
            pass
        finally:
            self._cleanup()

    def disconnect(self) -> None:
        """Close connection."""
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        self._transport.close()
        self._access_granted = False

    def _cleanup(self) -> None:
        """Clean up connection. on_close callback is scheduled but not awaited."""
        self._access_granted = False
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        self._transport.close()
        if self._on_close:
            cb = self._on_close()
            if asyncio.iscoroutine(cb):
                asyncio.create_task(cb)

    async def _ping_loop(self) -> None:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            if not await self._send_json({"type": "ping"}):
                break

    async def _send_json(self, obj: dict) -> bool:
        return await self._transport.send(json.dumps(obj))

    async def _recv_loop(self) -> None:
        async for msg in self._transport.receive():
            await self._handle_message(msg)

    async def _handle_message(self, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        event_type = data.get("type")
        if not event_type:
            return
        if event_type == "access-granted":
            self._access_granted = True
        if event_type == "pong":
            return
        if event_type == "event-closed":
            self._access_granted = False
        if self._on_event:
            payload = data.get("data", data)
            cb = self._on_event(event_type, payload)
            if asyncio.iscoroutine(cb):
                await cb
