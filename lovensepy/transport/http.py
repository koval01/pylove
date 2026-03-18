"""
HTTP transport: POST JSON to Lovense command endpoint.
"""

import json
import logging as py_logging
from typing import Any

import httpx

from ..exceptions import (
    LovenseAuthError,
    LovenseDeviceOfflineError,
    LovenseNetworkError,
    LovenseResponseParseError,
    LovenseTimeoutError,
)

__all__ = ["HttpTransport"]

_logger = py_logging.getLogger(__name__)


class HttpTransport:
    """
    HTTP client for Lovense command API.

    Sends POST requests to /command endpoint. Handles connection, timeouts, errors.
    """

    def __init__(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        verify: bool = True,
    ) -> None:
        self.endpoint = endpoint
        self.headers = headers or {}
        self.timeout = timeout
        self.verify = verify

    def post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        verify: bool | None = None,
    ) -> dict[str, Any]:
        """
        POST JSON payload to endpoint. Raises on failure.
        """
        timeout = timeout or self.timeout
        verify = verify if verify is not None else self.verify

        _logger.debug("HTTP payload: %s", payload)

        try:
            with httpx.Client(verify=verify, timeout=timeout) as client:
                resp = client.post(
                    self.endpoint,
                    json=payload,
                    headers=self.headers,
                )
        except httpx.ConnectError as e:
            _logger.debug("HTTP connect error: %s", e)
            raise LovenseDeviceOfflineError(
                f"Failed to connect to {self.endpoint}",
                endpoint=self.endpoint,
                payload=payload,
            ) from e
        except httpx.TimeoutException as e:
            _logger.debug("HTTP timeout: %s", e)
            raise LovenseTimeoutError(
                f"Timed out while calling {self.endpoint}",
                endpoint=self.endpoint,
                payload=payload,
            ) from e
        except httpx.HTTPError as e:
            _logger.debug("HTTP request error: %s", e)
            raise LovenseNetworkError(
                f"HTTP request failed for {self.endpoint}",
                endpoint=self.endpoint,
                payload=payload,
            ) from e

        if resp.status_code != 200:
            if resp.status_code in (401, 403):
                raise LovenseAuthError(
                    f"Authentication failed (HTTP {resp.status_code}) for {self.endpoint}",
                    endpoint=self.endpoint,
                    payload=payload,
                )
            _logger.debug("HTTP non-200 status: %s", resp.status_code)
            raise LovenseNetworkError(
                f"Non-200 response (HTTP {resp.status_code}) for {self.endpoint}",
                endpoint=self.endpoint,
                payload=payload,
            )

        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise LovenseResponseParseError(
                f"Failed to decode JSON response from {self.endpoint}",
                endpoint=self.endpoint,
                payload=payload,
            ) from e
