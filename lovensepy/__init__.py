"""
lovensepy — Python Lovense API client.

Supports:
- Standard API LAN (Game Mode)
- Standard API Server
- Standard Socket API
- Toy Events API
- Home Assistant MQTT bridge (optional ``paho-mqtt``)

Raw methods: function_request, send_command for custom logic.
High-level: SyncPatternPlayer, AsyncPatternPlayer for ready-made patterns.
"""

from typing import Any

from ._constants import Actions, Presets
from ._http_identity import package_version
from .exceptions import (
    LovenseAuthError,
    LovenseDeviceOfflineError,
    LovenseError,
    LovenseNetworkError,
    LovenseResponseParseError,
    LovenseTimeoutError,
)
from .patterns import AsyncPatternPlayer, SyncPatternPlayer
from .socket_api import (
    SocketAPIClient,
    build_websocket_url,
    get_socket_url,
    get_token,
)
from .standard import (
    AsyncLANClient,
    AsyncServerClient,
    LANClient,
    ServerClient,
    get_qr_code,
)
from .toy_events import ToyEventsClient
from .toy_utils import features_for_toy, stop_actions

__version__ = package_version()


def __getattr__(name: str) -> Any:
    if name == "HAMqttBridge":
        from lovensepy.integrations.mqtt.ha_bridge import HAMqttBridge

        return HAMqttBridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    "Actions",
    "Presets",
    "LANClient",
    "AsyncLANClient",
    "ServerClient",
    "AsyncServerClient",
    "get_qr_code",
    "get_token",
    "get_socket_url",
    "build_websocket_url",
    "SocketAPIClient",
    "ToyEventsClient",
    "SyncPatternPlayer",
    "AsyncPatternPlayer",
    "features_for_toy",
    "stop_actions",
    "LovenseError",
    "LovenseNetworkError",
    "LovenseAuthError",
    "LovenseDeviceOfflineError",
    "LovenseTimeoutError",
    "LovenseResponseParseError",
    "HAMqttBridge",
]
