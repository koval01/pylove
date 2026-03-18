#!/usr/bin/env python3
"""
Pattern player demo — high-level API for sine waves and combos.

Use raw methods (function_request) for custom logic, or SyncPatternPlayer
for ready-made patterns. Same LAN as Lovense Remote required.

Run: LOVENSE_LAN_IP=192.168.1.100 LOVENSE_LAN_PORT=20011 python -m examples.patterns_demo
"""

import os
import sys
import time

from lovensepy import LANClient, SyncPatternPlayer, features_for_toy
from lovensepy._models import GetToysResponse


def _parse_toys(resp: GetToysResponse | None) -> dict:
    """Normalize GetToysResponse into {toy_id: toy_dict}."""
    toys: dict = {}
    if not resp or resp.data is None:
        return toys
    return {toy.id: toy.model_dump() for toy in resp.data.toys}


def main() -> int:
    ip = os.environ.get("LOVENSE_LAN_IP")
    if not ip:
        print("Set LOVENSE_LAN_IP (e.g. 192.168.1.100)")
        return 1
    port = int(os.environ.get("LOVENSE_LAN_PORT", "20011"))

    client = LANClient("lovensepy patterns", ip, port=port)
    resp = client.get_toys()
    toys = _parse_toys(resp)
    if not toys:
        print("No toys — connect toys to Lovense Remote, enable Game Mode")
        return 1

    player = SyncPatternPlayer(client, toys)
    print(f"Toys: {list(toys.keys())}")
    for tid, t in toys.items():
        feats = player.features(tid)
        print(f"  {tid}: {t.get('name', '—')} — {feats}")

    # Option 1: Raw — single command
    print("\n>>> Raw: Vibrate:5 for 3s")
    tid = next(iter(toys.keys()))
    client.function_request({features_for_toy(toys[tid])[0]: 5}, time=3, toy_id=tid)
    time.sleep(3.5)
    player.stop(tid)

    # Option 2: High-level — sine wave on one feature
    print("\n>>> Pattern: sine wave on Vibrate1 for 5s")
    player.play_sine_wave(tid, player.features(tid)[0], duration_sec=5)

    # Option 3: Combo — two motors or two toys with random phases
    all_targets = [(tid, f) for tid, t in toys.items() for f in features_for_toy(t)]
    if len(all_targets) >= 2:
        print("\n>>> Pattern: combo (all motors) for 4s")
        player.play_combo(all_targets[:2], duration_sec=4)

    print("\n>>> Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
