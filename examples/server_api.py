#!/usr/bin/env python3
"""
Standard API Server — full example.

Requires LOVENSE_DEV_TOKEN and LOVENSE_UID (from your auth/QR flow).
Sends commands via Lovense cloud.
"""

import os
import sys

from lovensepy import ServerClient, Actions, Presets


def main() -> int:
    token = os.environ.get("LOVENSE_DEV_TOKEN")
    uid = os.environ.get("LOVENSE_UID")
    if not token or not uid:
        print("Set LOVENSE_DEV_TOKEN and LOVENSE_UID")
        return 1

    client = ServerClient(token, uid)

    # Function
    print("Sending Vibrate:5 for 5 seconds...")
    resp = client.function_request({Actions.VIBRATE: 5}, time=5)
    if resp:
        print("Response:", resp)
    else:
        print("Request failed")

    # Preset
    print("Sending PULSE preset for 5 seconds...")
    client.preset_request(Presets.PULSE, time=5)

    # Stop
    print("Stopping...")
    client.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
