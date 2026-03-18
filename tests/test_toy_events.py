"""
Tests for Toy Events API (local WebSocket).

Run with: LOVENSE_LAN_IP=192.168.1.100 pytest tests/test_toy_events.py -v -s

Toy Events is in Lovense Remote only (not Lovense Connect).
- Lovense Remote: Toy Events WebSocket on port 20011 (per Lovense docs). Game Mode HTTP uses 20011.
  Use LOVENSE_TOY_EVENTS_PORT=20011. If 20011 fails, try 20011 (some app versions may differ).
- Lovense Connect: port 34567, no Toy Events — use Remote for Toy Events.
"""

import asyncio
import os
from typing import Any

import pytest

from lovensepy import ToyEventsClient
from tests.conftest import requires_lan


def _log(msg: str) -> None:
    print(msg, flush=True)


# Lovense Connect (34567) has no Toy Events; only Lovense Remote (20011) has it
LOVENSE_CONNECT_PORT = 34567


@requires_lan
@pytest.mark.asyncio
async def test_toy_events_connect_and_events():
    """
    Connect to Toy Events WebSocket, request access, receive events.
    Uses same IP/port as LAN. Enable Game Mode, grant access when prompted.
    """
    ip = os.environ["LOVENSE_LAN_IP"]
    port = int(
        os.environ.get("LOVENSE_TOY_EVENTS_PORT") or os.environ.get("LOVENSE_LAN_PORT", "20011")
    )
    if port == LOVENSE_CONNECT_PORT:
        pytest.skip(
            "Toy Events API is only in Lovense Remote (port 20011), not Lovense Connect (34567). "
            "Use LOVENSE_TOY_EVENTS_PORT=20011 with Lovense Remote."
        )
    events: list[tuple[str, Any]] = []
    access_granted = False
    connect_error: Exception | None = None

    def on_event(event_type: str, data: Any) -> None:
        nonlocal access_granted
        events.append((event_type, data))
        if event_type == "access-granted":
            access_granted = True
        _log(f"  [{event_type}] {str(data)[:80]}...")

    def on_error(exc: Exception) -> None:
        nonlocal connect_error
        connect_error = exc
        _log(f"  Error: {exc}")

    client = ToyEventsClient(
        ip,
        port=port,
        app_name="lovensepy_test",
        on_event=on_event,
        on_error=on_error,
    )

    async def run_with_timeout() -> None:
        _log(f"Connecting to Toy Events WebSocket (ws://{ip}:{port}/v1)...")
        task = asyncio.create_task(client.connect())
        await asyncio.sleep(10)
        client.disconnect()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await run_with_timeout()

    if connect_error:
        pytest.skip(
            f"Toy Events connection failed: {connect_error} — check Game Mode, same port as LAN"
        )
    assert events, "No events — enable Game Mode, grant access in Lovense Remote when prompted"
    assert access_granted, "Access not granted — tap Allow when Lovense Remote asks"
    _log(">>> Toy Events OK.")


@requires_lan
@pytest.mark.asyncio
async def test_toy_events_interactive():
    """
    Interactive: listen for events 30s. Requires toys with event support
    (Max 2, Nora, Solace, etc.). Edge/Gush don't support Toy Events.
    Trigger: press toy button, change strength in Lovense Remote.
    Run: LOVENSE_LAN_IP=... LOVENSE_TOY_EVENTS_PORT=20011 \\
        pytest tests/test_toy_events.py::test_toy_events_interactive -v -s
    """
    ip = os.environ["LOVENSE_LAN_IP"]
    port = int(
        os.environ.get("LOVENSE_TOY_EVENTS_PORT") or os.environ.get("LOVENSE_LAN_PORT", "20011")
    )
    if port == LOVENSE_CONNECT_PORT:
        pytest.skip("Toy Events only in Lovense Remote (20011), not Connect (34567)")

    events: list[tuple[str, Any]] = []
    connect_error: Exception | None = None

    def on_event(event_type: str, data: Any) -> None:
        events.append((event_type, data))
        _log(f"  [{event_type}] {data}")

    def on_error(exc: Exception) -> None:
        nonlocal connect_error
        connect_error = exc
        _log(f"  Error: {exc}")

    client = ToyEventsClient(
        ip,
        port=port,
        app_name="lovensepy_events_test",
        on_event=on_event,
        on_error=on_error,
    )

    _log("Connecting... Grant access when prompted.")
    _log(">>> Trigger events: press toy button, change strength in Lovense Remote (30s)")
    task = asyncio.create_task(client.connect())
    await asyncio.sleep(30)
    client.disconnect()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    if connect_error:
        pytest.skip(f"Connection failed: {connect_error}")
    event_types = {e[0] for e in events}
    _log(f">>> Received {len(events)} events: {sorted(event_types)}")
