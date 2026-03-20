"""
Standard Socket API: getToken, getSocketUrl, build WebSocket URL.
"""

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from .._http_identity import default_http_headers

# Public Lovense API endpoints (not secrets)
GET_TOKEN_URL = "https://api.lovense-api.com/api/basicApi/getToken"  # nosec B105
GET_SOCKET_URL = "https://api.lovense-api.com/api/basicApi/getSocketUrl"  # nosec B105


def get_token(
    developer_token: str,
    uid: str,
    uname: str | None = None,
    utoken: str | None = None,
    timeout: float = 10.0,
) -> str:
    """
    Get auth token for Socket API.

    Args:
        developer_token: From Lovense developer dashboard
        uid: User ID on your application
        uname: User nickname (optional)
        utoken: Encrypted user token for verification (optional)
        timeout: Request timeout

    Returns:
        authToken for get_socket_url

    Raises:
        ValueError: If API rejects the request
        httpx.HTTPError: On network errors
    """
    payload: dict[str, Any] = {
        "token": developer_token,
        "uid": uid,
    }
    if uname is not None:
        payload["uname"] = uname
    if utoken is not None:
        payload["utoken"] = utoken

    with httpx.Client(timeout=timeout, headers=default_http_headers()) as client:
        resp = client.post(GET_TOKEN_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 0 or not data.get("data", {}).get("authToken"):
        raise ValueError(data.get("message", "Failed to get Lovense token"))
    return data["data"]["authToken"]


def get_socket_url(
    auth_token: str,
    platform: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """
    Get Socket.IO URL info from Lovense.

    Args:
        auth_token: From get_token
        platform: Website Name from Lovense Developer Dashboard. Must match exactly.
            This is the name you registered in the dashboard (shown in Lovense Remote).
        timeout: Request timeout

    Returns:
        dict with socketIoUrl, socketIoPath, etc.

    Raises:
        ValueError: If API rejects the token (e.g. "Developer information not found"
            means platform does not match your dashboard)
        httpx.HTTPError: On network errors
    """
    payload = {"authToken": auth_token, "platform": platform}
    with httpx.Client(timeout=timeout, headers=default_http_headers()) as client:
        resp = client.post(GET_SOCKET_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    # Success: code==0 or truthy result (API may use either)
    if data.get("code") != 0 and not data.get("result"):
        raise ValueError(data.get("message", "Lovense API rejected token"))
    if not data.get("data"):
        raise ValueError("No socket info in response")
    return data["data"]


def build_websocket_url(socket_info: dict[str, Any], auth_token: str) -> str:
    """
    Build Engine.IO WebSocket URL from get_socket_url response.

    Uses socketIoUrl host, socketIoPath, and ntoken from URL query or authToken.
    """
    socket_io_url = socket_info.get("socketIoUrl", "")
    parsed = urlparse(socket_io_url)
    qs = parse_qs(parsed.query)
    ntoken_from_url = qs.get("ntoken", [None])[0] if qs else None
    raw = ntoken_from_url if ntoken_from_url else auth_token
    safe_token = raw.replace("+", "%2B").replace("/", "%2F").replace("=", "%3D")

    ws_host = parsed.netloc or parsed.hostname or ""
    if not ws_host:
        raise ValueError("Lovense socketIoUrl has no host")

    path = (socket_info.get("socketIoPath") or "").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    if not path.endswith("/"):
        path = f"{path}/"

    return f"wss://{ws_host}{path}?ntoken={safe_token}&EIO=3&transport=websocket"
