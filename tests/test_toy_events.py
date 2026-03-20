"""
Tests for Toy Events API (local WebSocket).

Run with: LOVENSE_LAN_IP=192.168.1.100 pytest tests/test_toy_events.py -v -s

Toy Events is in Lovense Remote only (not Lovense Connect).
- Lovense Remote: Toy Events WebSocket on port 20011 (per Lovense docs). Game Mode HTTP uses 20011.
  Use LOVENSE_TOY_EVENTS_PORT=20011. If 20011 fails, try 20011 (some app versions may differ).
- Lovense Connect: port 34567, no Toy Events — use Remote for Toy Events.
"""

import os
from typing import Any

import pytest

from tests.conftest import requires_lan
from tests.helpers.toy_events_helpers import collect_toy_events


def _log(msg: str) -> None:
    print(msg, flush=True)


# Lovense Connect (34567) has no Toy Events; only Lovense Remote (20011) has it
LOVENSE_CONNECT_PORT = 34567



@requires_lan
@pytest.mark.anyio
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
    _log(f"Connecting to Toy Events WebSocket (ws://{ip}:{port}/v1)...")
    events, access_granted, connect_error = await collect_toy_events(
        ip,
        port,
        app_name="lovensepy_test",
        duration_sec=10,
        log_fn=_log,
    )

    if connect_error is not None:
        pytest.skip(
            f"Toy Events connection failed: {connect_error} — check Game Mode, same port as LAN"
        )
    assert events, "No events — enable Game Mode, grant access in Lovense Remote when prompted"
    assert access_granted, "Access not granted — tap Allow when Lovense Remote asks"
    _log(">>> Toy Events OK.")


@requires_lan
@pytest.mark.anyio
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

    _log("Connecting... Grant access when prompted.")
    _log(">>> Trigger events: press toy button, change strength in Lovense Remote (30s)")

    events, access_granted, connect_error = await collect_toy_events(
        ip,
        port,
        app_name="lovensepy_events_test",
        duration_sec=30,
        log_fn=_log,
    )

    if connect_error is not None:
        pytest.skip(f"Connection failed: {connect_error}")

    if not access_granted:
        pytest.skip("Toy Events access was not granted in Lovense Remote")

    event_types = {e[0] for e in events}
    non_handshake_events = event_types - {"access-granted", "toy-list"}
    if not non_handshake_events:
        pytest.skip(
            "No interactive Toy Events received. "
            "This usually means connected toys do not support Toy Events or no interaction happened."
        )

    _log(f">>> Received {len(events)} events: {sorted(event_types)}")
