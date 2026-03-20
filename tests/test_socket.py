"""
Tests for Socket API — server (WebSocket, QR flow).

Run: LOVENSE_DEV_TOKEN=... LOVENSE_UID=... LOVENSE_PLATFORM="..." \\
    pytest tests/test_socket.py -v -s

LOVENSE_PLATFORM must match the Website Name from your Lovense Developer Dashboard.
For interactive (QR scan) tests, do NOT set LOVENSE_SKIP_INTERACTIVE.
"""

import asyncio
import os
from typing import Any

import pytest

from lovensepy import (
    SocketAPIClient,
    build_websocket_url,
    features_for_toy,
    get_socket_url,
    get_token,
)
from lovensepy.socket_api.events import (
    BASICAPI_GET_QRCODE_TC,
    BASICAPI_UPDATE_DEVICE_INFO_TC,
)
from tests.conftest import requires_interactive, requires_socket
from tests.helpers.socket_scenarios import run_socket_function_demo


async def _run_client(
    ws_url,
    on_connected,
    on_event,
    client_ref,
    on_open=None,
    on_error=None,
    use_local_commands=False,
    app_name="lovensepy_test",
):
    c = SocketAPIClient(
        ws_url,
        use_local_commands=use_local_commands,
        app_name=app_name,
        on_socket_open=on_open,
        on_socket_error=on_error,
        on_socket_io_connected=on_connected,
        on_event=on_event,
    )
    client_ref.append(c)
    await c.run_forever()


@pytest.fixture
def auth_token():
    """Get auth token from developer token and uid."""
    token = os.environ.get("LOVENSE_DEV_TOKEN")
    uid = os.environ.get("LOVENSE_UID", "test_user_lovensepy")
    if not token:
        pytest.skip("LOVENSE_DEV_TOKEN required")
    return get_token(token, uid, uname=f"user_{uid[:8]}")


@pytest.fixture
def ws_url(auth_token):
    """Build WebSocket URL. LOVENSE_PLATFORM must match Lovense Developer Dashboard."""
    platform = os.environ.get("LOVENSE_PLATFORM")
    if not platform:
        pytest.skip("LOVENSE_PLATFORM required (Website Name from Lovense Developer Dashboard)")
    info = get_socket_url(auth_token, platform)
    return build_websocket_url(info, auth_token)


def test_get_token(auth_token):
    """get_token returns non-empty auth token."""
    assert auth_token
    assert len(auth_token) > 10


def test_get_socket_url(auth_token):
    """get_socket_url returns socket info. Requires LOVENSE_PLATFORM."""
    platform = os.environ.get("LOVENSE_PLATFORM")
    if not platform:
        pytest.skip("LOVENSE_PLATFORM required")
    info = get_socket_url(auth_token, platform)
    assert "socketIoUrl" in info or "socketIoPath" in info


def test_build_websocket_url(auth_token):
    """build_websocket_url produces wss URL. Requires LOVENSE_PLATFORM."""
    platform = os.environ.get("LOVENSE_PLATFORM")
    if not platform:
        pytest.skip("LOVENSE_PLATFORM required")
    info = get_socket_url(auth_token, platform)
    url = build_websocket_url(info, auth_token)
    assert url.startswith("wss://")
    assert "EIO=3" in url
    assert "transport=websocket" in url


def _log(msg: str) -> None:
    print(msg, flush=True)


@pytest.mark.anyio
@requires_socket
@requires_interactive
async def test_full_flow(ws_url):
    """
    Full Socket API flow: connect, show QR, wait for scan, verify toys, send command.

    You MUST scan the QR code with Lovense Remote app. LAN IP is NOT needed for Socket API.
    """
    toys: dict[str, Any] = {}
    session_started = False
    qr_url: str | None = None
    qr_logged: set[str] = set()
    client_ref: list[SocketAPIClient] = []

    def on_event(event: str, payload: Any) -> None:
        nonlocal session_started, qr_url
        if event == BASICAPI_GET_QRCODE_TC:
            data = (payload or {}).get("data", {})
            url = data.get("qrcodeUrl") or data.get("qrcode")
            if url:
                url_str = url if isinstance(url, str) else str(url)
                qr_url = url_str
                if url_str not in qr_logged and not toys:
                    qr_logged.add(url_str)
                    _log("\n>>> SCAN QR: open in browser and scan with Lovense Remote app:")
                    _log(f">>> {url_str}\n")
        elif event in ("basicapi_update_app_online_tc", "basicapi_update_app_status_tc"):
            if (payload or {}).get("status") == 1:
                session_started = True
        elif event == BASICAPI_UPDATE_DEVICE_INFO_TC:
            for t in (payload or {}).get("toyList", []):
                if isinstance(t, dict) and t.get("connected"):
                    toys[t["id"]] = t

    qr_requested = False

    def on_connected() -> None:
        nonlocal qr_requested
        if qr_requested:
            return
        qr_requested = True
        _log("Socket.IO connected, waiting for session...")

    async def maybe_request_qr() -> None:
        await asyncio.sleep(2.0)
        if not toys and client_ref:
            _log("No toys yet, requesting QR code...")
            client_ref[0].send_event("basicapi_get_qrcode_ts", {"ackId": "1"})

    def on_open() -> None:
        _log("WebSocket opened, handshaking...")

    def on_error(exc: Exception) -> None:
        _log(f"WebSocket error: {exc}")

    _log("Connecting to Lovense WebSocket...")
    runner = asyncio.create_task(
        _run_client(ws_url, on_connected, on_event, client_ref, on_open, on_error)
    )
    qr_task = asyncio.create_task(maybe_request_qr())

    for i in range(120):
        await asyncio.sleep(1)
        if session_started and toys:
            _log("Session started, toys detected!")
            break
        if qr_url and not session_started and (i % 5 == 0):
            _log(f"Waiting for QR scan... ({i}s) — open the URL above in browser")

    assert session_started, "Session did not start — did you scan the QR with Lovense Remote?"
    assert toys, "No toys detected — connect a toy to Lovense Remote before scanning"

    _log(f"\n>>> Detected {len(toys)} toy(s):")
    for tid, t in toys.items():
        name = t.get("name") or "—"
        model = t.get("toyType") or t.get("name") or "—"
        features = features_for_toy(t)
        _log(f"    {tid}: {name} ({model}) — {features}")

    client = client_ref[0]
    await run_socket_function_demo(client, toys, log_fn=_log)

    qr_task.cancel()
    try:
        await qr_task
    except asyncio.CancelledError:
        pass
    runner.cancel()
    try:
        await runner
    except asyncio.CancelledError:
        pass


@pytest.mark.anyio
@requires_socket
@requires_interactive
async def test_by_local(ws_url):
    """
    Socket API by local: QR flow + commands via HTTPS to device (same LAN).

    Same as full flow but use_local_commands=True. Phone and test machine must be on same network.
    """
    toys: dict[str, Any] = {}
    session_started = False
    qr_url: str | None = None
    qr_logged: set[str] = set()
    client_ref: list[SocketAPIClient] = []

    def on_event(event: str, payload: Any) -> None:
        nonlocal session_started, qr_url
        if event == BASICAPI_GET_QRCODE_TC:
            data = (payload or {}).get("data", {})
            url = data.get("qrcodeUrl") or data.get("qrcode")
            if url:
                url_str = url if isinstance(url, str) else str(url)
                qr_url = url_str
                if url_str not in qr_logged and not toys:
                    qr_logged.add(url_str)
                    _log(f"\n>>> [BY LOCAL] SCAN QR: {url_str}\n")
        elif event in ("basicapi_update_app_online_tc", "basicapi_update_app_status_tc"):
            if (payload or {}).get("status") == 1:
                session_started = True
        elif event == BASICAPI_UPDATE_DEVICE_INFO_TC:
            for t in (payload or {}).get("toyList", []):
                if isinstance(t, dict) and t.get("connected"):
                    toys[t["id"]] = t

    def on_connected() -> None:
        pass

    async def maybe_request_qr() -> None:
        await asyncio.sleep(2.0)
        if not toys and client_ref:
            client_ref[0].send_event("basicapi_get_qrcode_ts", {"ackId": "1"})

    _log("Connecting (use_local_commands=True)...")
    runner = asyncio.create_task(
        _run_client(
            ws_url,
            on_connected,
            on_event,
            client_ref,
            use_local_commands=True,
            app_name="lovensepy_by_local",
        )
    )
    qr_task = asyncio.create_task(maybe_request_qr())

    for i in range(120):
        await asyncio.sleep(1)
        if session_started and toys and client_ref:
            break
        if qr_url and (i % 5 == 0):
            _log(f"Waiting for QR scan... ({i}s)")

    assert session_started, "Session did not start — scan QR with Lovense Remote"
    assert toys, "No toys — connect toy before scanning"
    assert client_ref[0].is_using_local_commands, (
        "Expected is_using_local_commands — device must be on same LAN as test machine"
    )

    _log(f"\n>>> By local: {len(toys)} toy(s), commands via HTTPS to device")
    tid = next(iter(toys.keys()))
    _log(f"Sending Vibrate:5 to {tid} for 3s (via local HTTPS)...")
    client_ref[0].send_command("Function", "Vibrate:5", time_sec=3, toy=tid)
    await asyncio.sleep(3.5)
    await client_ref[0].send_command_await("Function", "Stop", time_sec=0, toy=tid)
    _log(">>> Done.")

    qr_task.cancel()
    try:
        await qr_task
    except asyncio.CancelledError:
        pass
    runner.cancel()
    try:
        await runner
    except asyncio.CancelledError:
        pass
