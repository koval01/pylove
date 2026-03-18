#!/usr/bin/env python3
"""
Standard API LAN (Game Mode) — full example.

Lovense Remote App > Discover > Game Mode > Enable LAN
Set LOVENSE_LAN_IP and optionally LOVENSE_LAN_PORT (default 20011).
"""

import os
import sys

from lovensepy import LANClient, Actions, Presets


def main() -> int:
    ip = os.environ.get("LOVENSE_LAN_IP")
    if not ip:
        print("Set LOVENSE_LAN_IP (e.g. 192.168.1.100)")
        return 1
    port = int(os.environ.get("LOVENSE_LAN_PORT", "20011"))

    client = LANClient("lovensepy example", ip, port=port)

    # Get toys
    toys_response = client.get_toys()
    if toys_response.data and toys_response.data.toys:
        print("Toys:", [t.model_dump() for t in toys_response.data.toys])
    else:
        print("No toys or connection failed")

    # Get toy names
    names = client.get_toys_name()
    if names.data:
        print("Toy names:", names.data)

    # Preset (5 sec)
    print("Sending PULSE preset for 5 seconds...")
    client.preset_request(Presets.PULSE, time=5)

    # Function
    print("Sending Vibrate:5 for 3 seconds...")
    client.function_request({Actions.ALL: 5}, time=3)

    # Pattern
    print("Sending pattern [5,10,15,20] for 4 seconds...")
    client.pattern_request([5, 10, 15, 20], time=4)

    # Stop
    print("Stopping...")
    client.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
