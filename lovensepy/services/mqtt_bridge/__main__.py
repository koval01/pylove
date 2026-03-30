"""Allow ``python -m lovensepy.services.mqtt_bridge``."""

from __future__ import annotations

from ._cli import main

if __name__ == "__main__":
    raise SystemExit(main())
