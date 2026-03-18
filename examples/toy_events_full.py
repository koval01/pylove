#!/usr/bin/env python3
"""
Toy Events API — full example.

Minimal async usage (run with asyncio.run):
    import asyncio
    from lovensepy import ToyEventsClient

    async def main():
        client = ToyEventsClient("192.168.1.100", port=20011, app_name="My App", on_event=lambda e, p: print(e, p))
        await client.connect()

    asyncio.run(main())

Connects to Game Mode WebSocket, requests access, receives real-time events:
toy-list, toy-status, button-down, button-up, function-strength-changed,
shake, battery-changed, motion-changed, event-closed.

Toy Events is in Lovense Remote only (not Lovense Connect).
- Lovense Remote: LOVENSE_LAN_IP, LOVENSE_TOY_EVENTS_PORT=20011 (per Lovense docs)
- Lovense Connect has no Toy Events.
"""

import asyncio
import os
import sys
from typing import Any

from lovensepy import ToyEventsClient


def main() -> int:
    ip = os.environ.get("LOVENSE_LAN_IP")
    if not ip:
        print("Set LOVENSE_LAN_IP (e.g. 192.168.1.100)")
        return 1
    port = int(os.environ.get("LOVENSE_TOY_EVENTS_PORT") or os.environ.get("LOVENSE_LAN_PORT", "20011"))
    use_https = os.environ.get("LOVENSE_USE_HTTPS", "").lower() in ("1", "true", "yes")

    def on_event(event_type: str, data: Any) -> None:
        print(f"[{event_type}] {data}")

    client = ToyEventsClient(
        ip,
        port=port,
        use_https=use_https,
        app_name="lovensepy toy events",
        on_event=on_event,
    )

    async def run() -> None:
        print("Connecting... Open Lovense Remote, enable Game Mode.")
        await client.connect()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
