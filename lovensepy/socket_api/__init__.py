"""
Standard Socket API: getToken, getSocketUrl, WebSocket client.
"""

from .auth import build_websocket_url, get_socket_url, get_token
from .client import SocketAPIClient
from .events import (
    BASICAPI_GET_QRCODE_TC,
    BASICAPI_GET_QRCODE_TS,
    BASICAPI_SEND_TOY_COMMAND_TS,
    BASICAPI_UPDATE_APP_ONLINE_TC,
    BASICAPI_UPDATE_APP_STATUS_TC,
    BASICAPI_UPDATE_DEVICE_INFO_TC,
)

__all__ = [
    "get_token",
    "get_socket_url",
    "build_websocket_url",
    "SocketAPIClient",
    "BASICAPI_GET_QRCODE_TS",
    "BASICAPI_GET_QRCODE_TC",
    "BASICAPI_UPDATE_DEVICE_INFO_TC",
    "BASICAPI_UPDATE_APP_ONLINE_TC",
    "BASICAPI_UPDATE_APP_STATUS_TC",
    "BASICAPI_SEND_TOY_COMMAND_TS",
]
