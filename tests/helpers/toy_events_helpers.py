"""
Toy Events API integration helper.

This module is used to keep `tests/test_toy_events.py` readable by factoring out
the connection/receive orchestration.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from lovensepy import ToyEventsClient


def log(msg: str) -> None:
    print(msg, flush=True)


async def collect_toy_events(
    ip: str,
    port: int,
    *,
    app_name: str,
    duration_sec: float,
    log_fn: Callable[[str], None] = log,
) -> tuple[list[tuple[str, Any]], bool, Exception | None]:
    """
    Connect to the Toy Events WebSocket, request access, and collect events.

    Returns: (events, access_granted, connect_error)
    """

    events: list[tuple[str, Any]] = []
    access_granted = False
    connect_error: Exception | None = None

    def on_event(event_type: str, data: Any) -> None:
        nonlocal access_granted
        events.append((event_type, data))
        if event_type == "access-granted":
            access_granted = True
        log_fn(f"  [{event_type}] {str(data)[:80]}...")

    def on_error(exc: Exception) -> None:
        nonlocal connect_error
        connect_error = exc
        log_fn(f"  Error: {exc}")

    client = ToyEventsClient(
        ip,
        port=port,
        app_name=app_name,
        on_event=on_event,
        on_error=on_error,
    )

    task = asyncio.create_task(client.connect())
    await asyncio.sleep(duration_sec)
    client.disconnect()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    return events, access_granted, connect_error

