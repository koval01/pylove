#!/usr/bin/env python3
"""
Home Assistant MQTT bridge — thin shim.

The implementation lives in :mod:`lovensepy.services.mqtt_bridge`.

Run:

    python -m lovensepy.services.mqtt_bridge

Or (after ``pip install 'lovensepy[mqtt]'``):

    lovensepy-mqtt

Requires ``pip install 'lovensepy[mqtt]'``; for BLE add ``[ble]``.

Environment variables are documented in :mod:`lovensepy.services.mqtt_bridge`.
"""

from __future__ import annotations

from lovensepy.services.mqtt_bridge import main

if __name__ == "__main__":
    raise SystemExit(main())
