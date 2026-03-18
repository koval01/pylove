#!/usr/bin/env python3
"""
Standard Socket API — full example with QR flow.

Minimal async usage (run with asyncio.run):
    import asyncio
    from lovensepy import get_token, get_socket_url, build_websocket_url, SocketAPIClient

    async def main():
        auth_token = get_token(developer_token, uid, uname="User")
        socket_info = get_socket_url(auth_token, platform="Your App")
        ws_url = build_websocket_url(socket_info, auth_token)
        client = SocketAPIClient(ws_url, on_event=lambda e, p: print(e, p))
        await client.connect()

    asyncio.run(main())

Flow:
1. get_token(developer_token, uid) -> auth_token
2. get_socket_url(auth_token, platform) -> socket_info
3. build_websocket_url(socket_info, auth_token) -> ws_url
4. Connect SocketAPIClient
5. Send basicapi_get_qrcode_ts -> receive basicapi_get_qrcode_tc (QR URL)
6. User scans QR in Lovense Remote app
7. Receive basicapi_update_app_status_tc (status=1) -> online
8. Receive basicapi_update_device_info_tc -> toyList
9. Send basicapi_send_toy_command_ts to control toys

Set LOVENSE_DEV_TOKEN and LOVENSE_UID. If not set, prompts interactively.
"""

import asyncio
import os
import sys
from typing import Any

from lovensepy import get_token, get_socket_url, build_websocket_url, SocketAPIClient
from lovensepy.socket_api.events import (
    BASICAPI_GET_QRCODE_TC,
    BASICAPI_UPDATE_DEVICE_INFO_TC,
)


def main() -> int:
    token = os.environ.get("LOVENSE_DEV_TOKEN")
    uid = os.environ.get("LOVENSE_UID")
    if not token:
        token = input("Lovense developer token: ").strip()
    if not uid:
        uid = input("User ID (uid): ").strip() or "test_user_001"
    if not token:
        print("Token required")
        return 1

    platform = os.environ.get("LOVENSE_PLATFORM")
    if not platform:
        platform = input(
            "Lovense platform (Website Name from Developer Dashboard): "
        ).strip() or "lovensepy"

    auth_token = get_token(token, uid, uname=f"user_{uid[:8]}")
    socket_info = get_socket_url(auth_token, platform)
    ws_url = build_websocket_url(socket_info, auth_token)

    toys: dict[str, Any] = {}
    session_started = False
    qr_url: str | None = None
    client_ref: list[SocketAPIClient] = []

    async def run_with_control() -> None:
        nonlocal session_started, qr_url

        def on_ev(event: str, payload: Any) -> None:
            nonlocal session_started, qr_url
            if event == BASICAPI_GET_QRCODE_TC:
                data = payload.get("data", {}) if isinstance(payload, dict) else {}
                url = data.get("qrcodeUrl") or data.get("qrcode")
                if url:
                    qr_url = url if isinstance(url, str) else str(url)
                    print(f"\n>>> Scan QR: {qr_url}\n")
            elif event in ("basicapi_update_app_online_tc", "basicapi_update_app_status_tc"):
                if (payload or {}).get("status") == 1:
                    session_started = True
                    print("Online")
            elif event == BASICAPI_UPDATE_DEVICE_INFO_TC:
                for t in (payload or {}).get("toyList", []):
                    if isinstance(t, dict) and t.get("connected"):
                        toys[t["id"]] = t

        def on_connected() -> None:
            client_ref[0].send_event(
                "basicapi_get_qrcode_ts", {"ackId": "1"}
            )

        c = SocketAPIClient(ws_url, on_socket_io_connected=on_connected, on_event=on_ev)
        client_ref.append(c)
        await c.connect()

    async def main_async() -> None:
        runner = asyncio.create_task(run_with_control())
        try:
            for _ in range(90):
                await asyncio.sleep(1)
                if session_started and toys and client_ref:
                    toy_id = next(iter(toys.keys()))
                    print(f"Sending Vibrate:5 to {toy_id} for 3 seconds...")
                    client_ref[0].send_command(
                        "Function", "Vibrate:5", time_sec=3, toy=toy_id
                    )
                    await asyncio.sleep(4)
                    print("Stopping...")
                    client_ref[0].send_command(
                        "Function", "Stop", time_sec=0, toy=toy_id
                    )
                    await asyncio.sleep(1)
                    break
        finally:
            runner.cancel()
            try:
                await runner
            except asyncio.CancelledError:
                pass

    asyncio.run(main_async())
    return 0


if __name__ == "__main__":
    sys.exit(main())
