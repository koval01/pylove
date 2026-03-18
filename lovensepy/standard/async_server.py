"""
Async Standard API — By Server client.

Async counterpart of :class:`lovensepy.standard.server.ServerClient` using
``httpx.AsyncClient`` via :class:`lovensepy.transport.async_http.AsyncHttpTransport`.
"""

from __future__ import annotations

import json
import logging as py_logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .._constants import FUNCTION_RANGES, SERVER_ERROR_CODES, Actions, Presets
from .._models import CommandResponse
from ..exceptions import LovenseError, LovenseResponseParseError
from ..transport import AsyncHttpTransport

__all__ = ["AsyncServerClient"]

SERVER_COMMAND_URL = "https://api.lovense-api.com/api/lan/v2/command"

_ResponseModelT = TypeVar("_ResponseModelT", bound=BaseModel)

_logger = py_logging.getLogger(__name__)


class AsyncServerClient:
    """Standard API Server client (async)."""

    def __init__(
        self,
        developer_token: str,
        uid: str,
        timeout: float = 10.0,
    ) -> None:
        self.developer_token = developer_token
        self.uid = uid
        self.timeout = timeout
        self.last_command: dict[str, Any] | None = None
        self.error_codes = SERVER_ERROR_CODES
        self.actions = Actions
        self.presets = Presets

        self._transport = AsyncHttpTransport(
            endpoint=SERVER_COMMAND_URL,
            headers={},
            timeout=timeout,
            verify=True,
        )

    @property
    def api_endpoint(self) -> str:
        """Endpoint URL for consistency with LANClient."""
        return self._transport.endpoint

    def _base_payload(self) -> dict[str, Any]:
        return {"token": self.developer_token, "uid": self.uid}

    async def aclose(self) -> None:
        """Close underlying HTTP sessions."""
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncServerClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self.aclose()
        return False

    async def send_command(
        self,
        command_data: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send command to Lovense server API."""
        timeout = timeout or self.timeout
        cmd = dict(command_data)

        # Clamp timeSec for non-zero values (API constraint, same as LAN)
        if (ts := cmd.get("timeSec")) is not None and ts != 0:
            cmd["timeSec"] = max(1.0, min(float(ts), 6000.0))

        payload = {**self._base_payload(), **cmd}
        self.last_command = payload

        data = await self._transport.post(payload, timeout=timeout)
        _logger.debug(self.decode_response(data))
        return data

    def _validate_response(
        self,
        data: dict[str, Any],
        model: type[_ResponseModelT],
    ) -> _ResponseModelT:
        """Validate a raw command response into a strict Pydantic model."""
        try:
            return model.model_validate(data)
        except ValidationError as e:
            raise LovenseResponseParseError(
                "Failed to validate Lovense API response",
                endpoint=self._transport.endpoint,
                payload=data,
            ) from e

    def _clamp_actions(self, actions: dict[str | Actions, int | float]) -> dict[str, int | float]:
        result: dict[str, int | float] = {}
        for action, value in actions.items():
            key = str(action)
            if key in FUNCTION_RANGES:
                lo, hi = FUNCTION_RANGES[key]
                result[key] = int(max(lo, min(hi, value)))
            else:
                result[key] = value
        return result

    async def function_request(
        self,
        actions: dict[str | Actions, int | float],
        time: float = 0,
        loop_on_time: float | None = None,
        loop_off_time: float | None = None,
        toy_id: str | list[str] | None = None,
        stop_previous: bool | None = None,
        timeout: float | None = None,
    ) -> CommandResponse:
        """Send Function command."""
        clamped = self._clamp_actions(actions)
        action_str = ",".join(f"{k}:{v}" for k, v in clamped.items())
        payload: dict[str, Any] = {
            "command": "Function",
            "action": action_str,
            "timeSec": time,
            "apiVer": 1,
        }
        if loop_on_time is not None:
            payload["loopRunningSec"] = max(loop_on_time, 1)
        if loop_off_time is not None:
            payload["loopPauseSec"] = max(loop_off_time, 1)
        if toy_id is not None:
            payload["toy"] = toy_id
        if stop_previous is not None:
            payload["stopPrevious"] = 1 if stop_previous else 0
        return self._validate_response(
            await self.send_command(payload, timeout=timeout), CommandResponse
        )

    async def stop(
        self, toy_id: str | list[str] | None = None, timeout: float | None = None
    ) -> CommandResponse:
        """Stop all toys."""
        payload: dict[str, Any] = {
            "command": "Function",
            "action": "Stop",
            "timeSec": 0,
            "apiVer": 1,
        }
        if toy_id is not None:
            payload["toy"] = toy_id
        return self._validate_response(
            await self.send_command(payload, timeout=timeout), CommandResponse
        )

    async def pattern_request(
        self,
        rule: str,
        strength: str,
        time: float = 0,
        toy_id: str | list[str] | None = None,
        timeout: float | None = None,
    ) -> CommandResponse:
        """Send Pattern command."""
        payload: dict[str, Any] = {
            "command": "Pattern",
            "rule": rule,
            "strength": strength,
            "timeSec": time,
            "apiVer": 2,
        }
        if toy_id is not None:
            payload["toy"] = toy_id
        return self._validate_response(
            await self.send_command(payload, timeout=timeout), CommandResponse
        )

    async def preset_request(
        self,
        name: str | Presets,
        time: float = 0,
        toy_id: str | list[str] | None = None,
        timeout: float | None = None,
    ) -> CommandResponse:
        """Send Preset command."""
        payload: dict[str, Any] = {
            "command": "Preset",
            "name": str(name),
            "timeSec": time,
            "apiVer": 1,
        }
        if toy_id is not None:
            payload["toy"] = toy_id
        return self._validate_response(
            await self.send_command(payload, timeout=timeout), CommandResponse
        )

    def decode_response(self, response: dict[str, Any] | BaseModel | None) -> str:
        """Format response as human-readable string."""
        if response is None:
            return "No response received from the server."
        if isinstance(response, BaseModel):
            response = response.model_dump()
        code = response.get("code")
        msg = self.error_codes.get(code, "Unknown") if isinstance(code, int) else str(code)
        out = f"Server response: code={code}, {msg}\n"
        if (data := response.get("data")) is not None:
            out += f"Data: {json.dumps(data, indent=2)}"
        return out

    class _PlayContextManager:
        """Async context manager: auto-stop on exit."""

        def __init__(
            self,
            client: AsyncServerClient,
            actions: dict[str | Actions, int | float],
            *,
            time: float,
            loop_on_time: float | None,
            loop_off_time: float | None,
            toy_id: str | list[str] | None,
            stop_previous: bool | None,
            timeout: float | None,
        ) -> None:
            self._client = client
            self._actions = actions
            self._time = time
            self._loop_on_time = loop_on_time
            self._loop_off_time = loop_off_time
            self._toy_id = toy_id
            self._stop_previous = stop_previous
            self._timeout = timeout
            self._response: CommandResponse | None = None

        async def __aenter__(self) -> CommandResponse:
            self._response = await self._client.function_request(
                self._actions,
                time=self._time,
                loop_on_time=self._loop_on_time,
                loop_off_time=self._loop_off_time,
                toy_id=self._toy_id,
                stop_previous=self._stop_previous,
                timeout=self._timeout,
            )
            return self._response

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            try:
                await self._client.stop(self._toy_id, timeout=self._timeout)
            except LovenseError:
                if exc_type is None:
                    raise
            return False

    def play(
        self,
        actions: dict[str | Actions, int | float],
        *,
        time: float = 0,
        loop_on_time: float | None = None,
        loop_off_time: float | None = None,
        toy_id: str | list[str] | None = None,
        stop_previous: bool | None = None,
        timeout: float | None = None,
    ) -> AsyncServerClient._PlayContextManager:
        """Async: start a Function command on enter and stop on exit."""
        return AsyncServerClient._PlayContextManager(
            self,
            actions,
            time=time,
            loop_on_time=loop_on_time,
            loop_off_time=loop_off_time,
            toy_id=toy_id,
            stop_previous=stop_previous,
            timeout=timeout,
        )
