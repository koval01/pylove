"""
Pytest configuration and fixtures.

Environment variables for tests:
- LOVENSE_DEV_TOKEN: Developer token (required for Socket API tests)
- LOVENSE_UID: User ID (default: test_user_lovensepy)
- LOVENSE_PLATFORM: Website Name from Lovense Developer Dashboard (required for getSocketUrl).
  Must match exactly. E.g. "Your App" or your Website Name from dashboard.
- LOVENSE_LAN_IP: LAN IP for Game Mode tests
- LOVENSE_LAN_PORT: LAN HTTP port (default: 20011).
  Lovense Remote Game Mode: 20011. Lovense Connect: 34567.
- LOVENSE_LAN_HTTPS_PORT: LAN HTTPS port for local-only Socket API test (default: 30011).
- LOVENSE_VERIFY_SSL: For HTTPS (30011/30011), set to 1 to verify SSL (default 0 for local).
- LOVENSE_TOY_EVENTS_PORT: Toy Events WebSocket port (default: 20011 per Lovense docs).
  Toy Events is in Lovense Remote only. Lovense Connect has no Toy Events.
- LOVENSE_SKIP_INTERACTIVE: Set to 1 to skip tests that require QR scan
"""

import os

import pytest


def has_lan_config() -> bool:
    return bool(os.environ.get("LOVENSE_LAN_IP"))


def has_socket_config() -> bool:
    return bool(os.environ.get("LOVENSE_DEV_TOKEN"))


def skip_interactive() -> bool:
    return os.environ.get("LOVENSE_SKIP_INTERACTIVE", "").lower() in ("1", "true", "yes")


requires_lan = pytest.mark.skipif(
    not has_lan_config(),
    reason="Set LOVENSE_LAN_IP to run LAN tests",
)

requires_socket = pytest.mark.skipif(
    not has_socket_config(),
    reason="Set LOVENSE_DEV_TOKEN to run Socket API tests",
)

requires_interactive = pytest.mark.skipif(
    skip_interactive(),
    reason="Set LOVENSE_SKIP_INTERACTIVE=0 to run interactive (QR scan) tests",
)
