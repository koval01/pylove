#!/usr/bin/env python3
"""
FastAPI server for Lovense local (LAN/Game Mode) control.

Expose a simple HTTP API for dashboards, automations, and custom integrations.

Timed motor / function control is scheduled with **asyncio tasks** and tracked per
(toy_id, feature). A command on *Vibrate2* does not cancel an active *Vibrate1*
slot on the same toy.

``GET /tasks`` lists **function** slots and **preset** / **pattern** sessions (timer
mirrors ``time`` you sent to the device; it is bookkeeping only — the toy still
runs the preset/pattern locally).

Task timestamps:

- ``started_at`` — wall clock (UTC, ISO-8601) when the task was created.
- ``started_monotonic_sec`` — value of ``time.monotonic()`` at creation (seconds
  since an undefined boot point; **not** a calendar time). Used with
  ``ends_mono`` to compute ``remaining_sec`` without DST / NTP jumps.

If preset/pattern ``time`` is ``0``, the **device** still receives ``0`` (open-ended
per Lovense); the **server-side tracker** uses ``LOVENSE_SESSION_MAX_SEC``
(default **60**) so the row disappears from ``/tasks`` after that cap.

Sending the **same** preset or pattern again (same toy + same identity) **extends**
the planner (``ends_mono``) and **sends another LAN command** with ``time`` equal
to this request’s duration (the extension segment). Lovense applies duration per
command, so without a resend the toy stops when the **first** ``timeSec`` elapses.
The preset/pattern **phase** may restart on the device when extending — that is a
firmware/app limitation.

FastAPI does not ship a separate "task manager" type; the documented approach is
**lifespan** + **app.state** for startup/shutdown and owning background work.
(``BackgroundTasks`` runs work after the response and is a poor fit for
long‑running overlapping motor timers — we use asyncio tasks instead.)

Requires:
    pip install fastapi uvicorn lovensepy

Environment:
    LOVENSE_LAN_IP      - phone/PC running Lovense Remote (Game Mode), e.g. 192.168.1.100
    LOVENSE_LAN_PORT    - Game Mode HTTP port (default: 20011)
    LOVENSE_APP_NAME    - app name sent to Lovense API (default: lovensepy_fastapi)
    LOVENSE_SESSION_MAX_SEC - preset/pattern time=0: server tracker length in seconds (default: 60)

Run:
    uvicorn examples.fastapi_lan_api:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field, field_validator, model_validator

from lovensepy import Actions, LANClient, LovenseError, Presets
from lovensepy._constants import FUNCTION_RANGES
from lovensepy._models import ToyInfo
from lovensepy.toy_utils import features_for_toy, stop_actions


class PatternTemplate(StrEnum):
    SOFT = "soft"
    WAVE = "wave"
    STAIRS = "stairs"


PATTERN_TEMPLATES: dict[PatternTemplate, list[int]] = {
    PatternTemplate.SOFT: [3, 5, 7, 5],
    PatternTemplate.WAVE: [2, 6, 10, 14, 10, 6],
    PatternTemplate.STAIRS: [3, 6, 9, 12, 15, 18],
}


def pattern_session_signature(
    pattern: list[int],
    *,
    interval: int,
    actions: list[Actions] | None,
    template: PatternTemplate | None,
) -> str:
    """Stable id for “same pattern job” (extend timer without resending LAN command)."""
    act = ",".join(sorted(str(a) for a in (actions or [])))
    if template is not None:
        return f"t:{template}|i:{interval}|a:{act}"
    return f"p:{json.dumps(pattern, separators=(',', ':'))}|i:{interval}|a:{act}"


class APIConfig(BaseModel):
    lan_ip: str = Field(..., min_length=7, description="Game Mode host, e.g. 192.168.1.100")
    lan_port: int = Field(default=20011, ge=1, le=65535)
    app_name: str = Field(default="lovensepy_fastapi", min_length=1)
    session_max_sec: float = Field(
        default=60.0,
        ge=1.0,
        le=86400.0,
        description="Preset/pattern time=0: how long the server keeps the row in /tasks.",
    )
    allowed_toy_ids: list[str] = Field(
        default_factory=list,
        description="Optional fixed toy ids for docs enum: LOVENSE_TOY_IDS=id1,id2",
    )

    @classmethod
    def from_env(cls) -> "APIConfig":
        ip = os.environ.get("LOVENSE_LAN_IP")
        if not ip:
            raise ValueError("Set LOVENSE_LAN_IP to enable local Lovense control.")
        raw_toys = os.environ.get("LOVENSE_TOY_IDS", "")
        allowed_toy_ids = [item.strip() for item in raw_toys.split(",") if item.strip()]
        return cls(
            lan_ip=ip,
            lan_port=int(os.environ.get("LOVENSE_LAN_PORT", "20011")),
            app_name=os.environ.get("LOVENSE_APP_NAME", "lovensepy_fastapi"),
            session_max_sec=float(os.environ.get("LOVENSE_SESSION_MAX_SEC", "60")),
            allowed_toy_ids=allowed_toy_ids,
        )


class FunctionCommand(BaseModel):
    actions: dict[Actions, float] = Field(
        ...,
        description="Per-function levels, e.g. {'Vibrate1': 10}. Each key is scheduled separately.",
    )
    time: float = Field(
        default=0,
        ge=0,
        description="Seconds to hold each listed function (0 = until stopped via API).",
    )
    loop_on_time: float | None = Field(default=None, ge=1)
    loop_off_time: float | None = Field(default=None, ge=1)
    toy_id: str = Field(..., min_length=1, description="Target toy id.")
    stop_previous: bool = Field(
        default=False,
        description="If true, cancel every active slot on this toy before applying this command.",
    )

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, value: dict[Actions, float]) -> dict[Actions, float]:
        if not value:
            raise ValueError("actions must not be empty")
        for action, level in value.items():
            min_level, max_level = FUNCTION_RANGES.get(str(action), (0, 20))
            if not (min_level <= level <= max_level):
                raise ValueError(
                    f"Invalid level for {action}: {level}. Allowed range: {min_level}..{max_level}"
                )
        return value


class PresetCommand(BaseModel):
    name: Presets = Field(..., description="Preset name from Lovense app.")
    time: float = Field(
        default=0,
        ge=0,
        description="Sent to Lovense as-is. If 0, server /tasks tracker still expires after LOVENSE_SESSION_MAX_SEC (default 60s).",
    )
    toy_id: str | None = Field(default=None, description="Target toy id.")


class PatternCommand(BaseModel):
    pattern: list[int] | None = Field(
        default=None, description="Strength sequence values in range 0..20."
    )
    template: PatternTemplate | None = Field(
        default=None,
        description="Predefined pattern template.",
    )
    actions: list[Actions] | None = Field(
        default=None,
        description="Optional action list, e.g. ['Vibrate'] or ['All'].",
    )
    interval: int = Field(default=100, ge=100, le=1000)
    time: float = Field(
        default=0,
        ge=0,
        description="Sent to Lovense as-is. If 0, server /tasks tracker expires after LOVENSE_SESSION_MAX_SEC (default 60s).",
    )
    toy_id: str | None = Field(default=None, description="Target toy id.")

    @model_validator(mode="after")
    def validate_pattern(self) -> "PatternCommand":
        if self.pattern is None and self.template is None:
            raise ValueError("Provide either 'pattern' or 'template'.")
        if self.pattern is not None and self.template is not None:
            raise ValueError("Use only one: 'pattern' or 'template'.")
        if self.pattern is not None:
            if not self.pattern:
                raise ValueError("pattern must not be empty")
            if len(self.pattern) > 50:
                raise ValueError("pattern must have at most 50 values")
            for value in self.pattern:
                if value < 0 or value > 20:
                    raise ValueError("pattern values must be within 0..20")
        return self


class StopToyBody(BaseModel):
    toy_id: str = Field(..., min_length=1)


def _reject_stop_feature_all_or_stop(value: Actions) -> Actions:
    if value == Actions.ALL:
        raise ValueError("To stop every function on a toy, use POST /command/stop/toy.")
    if value == Actions.STOP:
        raise ValueError("Use /command/stop/toy or /command/stop/all.")
    return value


class StopFeatureBody(BaseModel):
    toy_id: str = Field(..., min_length=1)
    feature: Actions = Field(..., description="Function / motor to zero out on the device.")

    @field_validator("feature")
    @classmethod
    def reject_all_alias(cls, value: Actions) -> Actions:
        return _reject_stop_feature_all_or_stop(value)


class StopToysBatchBody(BaseModel):
    toy_ids: list[str] = Field(..., min_length=1, description="Stop each toy (device + local slots).")


class StopFeatureBatchItem(BaseModel):
    toy_id: str = Field(..., min_length=1)
    feature: Actions = Field(...)

    @field_validator("feature")
    @classmethod
    def reject_all_alias(cls, value: Actions) -> Actions:
        return _reject_stop_feature_all_or_stop(value)


class StopFeaturesBatchBody(BaseModel):
    items: list[StopFeatureBatchItem] = Field(..., min_length=1)


def as_dict(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model  # pragma: no cover


def execute_or_http_error(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except LovenseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def extract_toy_ids(client: LANClient) -> list[str]:
    response = execute_or_http_error(client.get_toys)
    if not response.data or not response.data.toys:
        return []
    return sorted({toy.id for toy in response.data.toys if toy.id})


def patch_openapi_toy_ids(app: FastAPI, toy_ids: list[str]) -> None:
    if not toy_ids:
        return
    if app.openapi_schema:
        app.openapi_schema = None

    schema_names = (
        "FunctionCommand",
        "PresetCommand",
        "PatternCommand",
        "StopToyBody",
        "StopFeatureBody",
    )

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for model_name in schema_names:
            model = schema.get("components", {}).get("schemas", {}).get(model_name, {})
            props = model.get("properties", {})
            toy = props.get("toy_id")
            if isinstance(toy, dict):
                toy["enum"] = toy_ids
                toy["description"] = "Target toy id."
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


def _toy_info_as_dict(toy: ToyInfo) -> dict[str, Any]:
    return toy.model_dump()


class LanControlScheduler:
    """Schedules per-(toy, feature) holds and merges snapshots to the LAN API."""

    def __init__(self, client: LANClient, *, session_max_sec: float = 60.0) -> None:
        self._client = client
        self._session_max_sec = session_max_sec
        self._closed = False
        self._locks: dict[str, asyncio.Lock] = {}
        self._levels: dict[tuple[str, str], float] = {}
        self._tasks: dict[tuple[str, str], asyncio.Task[None]] = {}
        self._session_tasks: dict[str, asyncio.Task[None]] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    @property
    def closed(self) -> bool:
        return self._closed

    def _lock_for(self, toy_id: str) -> asyncio.Lock:
        if toy_id not in self._locks:
            self._locks[toy_id] = asyncio.Lock()
        return self._locks[toy_id]

    async def shutdown(self) -> None:
        self._closed = True
        pending = list(self._tasks.values()) + list(self._session_tasks.values())
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()
        self._session_tasks.clear()
        self._levels.clear()
        self._meta.clear()

    def _fetch_toy_dict(self, toy_id: str) -> dict[str, Any] | None:
        response = execute_or_http_error(self._client.get_toys)
        if not response.data:
            return None
        for toy in response.data.toys:
            if toy.id == toy_id:
                return _toy_info_as_dict(toy)
        return None

    def _expand_actions(self, toy_id: str, actions: dict[Actions, float]) -> dict[str, float]:
        if Actions.ALL not in actions:
            return {str(k): float(v) for k, v in actions.items()}
        if len(actions) != 1:
            raise ValueError("When using Actions.ALL, it must be the only key in actions.")
        level = float(actions[Actions.ALL])
        toy = self._fetch_toy_dict(toy_id)
        if not toy:
            raise ValueError(f"Toy {toy_id!r} not found (GetToys).")
        feats = features_for_toy(toy)
        return {f: level for f in feats}

    async def _cancel_slot(self, toy_id: str, feature: str) -> None:
        key = (toy_id, feature)
        old = self._tasks.pop(key, None)
        if old is not None and not old.done():
            old.cancel()
            try:
                await old
            except asyncio.CancelledError:
                pass

    async def cancel_sessions_for_toy(self, toy_id: str | None) -> None:
        to_cancel = [
            tid
            for tid, m in list(self._meta.items())
            if m.get("kind") in ("preset", "pattern") and m.get("toy_id") == toy_id
        ]
        for tid in to_cancel:
            task = self._session_tasks.pop(tid, None)
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._meta.pop(tid, None)

    async def cancel_all_sessions(self) -> None:
        for tid in list(self._session_tasks.keys()):
            task = self._session_tasks.pop(tid, None)
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        for tid, m in list(self._meta.items()):
            if m.get("kind") in ("preset", "pattern"):
                self._meta.pop(tid, None)

    async def cancel_every_slot_for_toy(self, toy_id: str) -> None:
        await self.cancel_sessions_for_toy(toy_id)
        keys = [key for key in self._tasks if key[0] == toy_id]
        for toy_key, feature in keys:
            await self._cancel_slot(toy_key, feature)

    async def cancel_all_function_slots(self) -> None:
        keys = list(self._tasks.keys())
        for toy_id, feature in keys:
            await self._cancel_slot(toy_id, feature)

    async def cancel_all_slots(self) -> None:
        """Cancel every function slot and every preset/pattern session."""
        await self.cancel_all_sessions()
        await self.cancel_all_function_slots()

    async def _run_session_until(self, task_id: str) -> None:
        """Sleep until ``meta[ends_mono]``; survives deadline bumps via task cancel/replace."""
        try:
            while True:
                meta = self._meta.get(task_id)
                if not meta:
                    return
                deadline = float(meta["ends_mono"])
                now = time.monotonic()
                rem = deadline - now
                if rem <= 0:
                    break
                await asyncio.sleep(rem)
        except asyncio.CancelledError:
            raise
        finally:
            current = asyncio.current_task()
            registered = self._session_tasks.get(task_id)
            if registered is current:
                self._session_tasks.pop(task_id, None)
                self._meta.pop(task_id, None)

    def find_matching_preset_session(self, toy_id: str | None, preset_name: str) -> str | None:
        for tid, m in list(self._meta.items()):
            if m.get("kind") != "preset":
                continue
            if m.get("toy_id") != toy_id:
                continue
            if m.get("preset") != preset_name:
                continue
            t = self._session_tasks.get(tid)
            if t is not None and not t.done():
                return tid
        return None

    def find_matching_pattern_session(self, toy_id: str | None, signature: str) -> str | None:
        for tid, m in list(self._meta.items()):
            if m.get("kind") != "pattern":
                continue
            if m.get("toy_id") != toy_id:
                continue
            if m.get("pattern_session_key") != signature:
                continue
            t = self._session_tasks.get(tid)
            if t is not None and not t.done():
                return tid
        return None

    async def extend_session(self, task_id: str, duration: float) -> dict[str, Any]:
        """Extend planner deadline and resend Preset/Pattern so the toy keeps running."""
        if self._closed:
            raise RuntimeError("scheduler_closed")
        meta = self._meta.get(task_id)
        if not meta or meta.get("kind") not in ("preset", "pattern"):
            raise ValueError("session not found or not extendable")

        requested = float(duration)
        if requested <= 0:
            effective = float(self._session_max_sec)
        else:
            effective = requested

        kind = meta.get("kind")
        toy_id_meta = meta.get("toy_id")

        # Lovense applies timeSec per command — without resending, the toy stops when
        # the previous segment ends even if /tasks shows a later deadline.
        if kind == "preset":
            preset_name = meta.get("preset")
            if not preset_name:
                raise ValueError("preset name missing from session meta")

            def send_preset() -> Any:
                return self._client.preset_request(
                    preset_name, time=effective, toy_id=toy_id_meta
                )

            await asyncio.to_thread(send_preset)
        elif kind == "pattern":
            pdata = meta.get("pattern_data")
            if not isinstance(pdata, list):
                raise ValueError(
                    "pattern_data missing in session meta (session started before "
                    "full pattern was stored); start the pattern once more to enable extend."
                )
            interval = int(meta.get("interval", 100))
            actions_raw = meta.get("pattern_actions")

            def send_pattern() -> Any:
                return self._client.pattern_request(
                    pdata,
                    actions=actions_raw,
                    interval=interval,
                    time=effective,
                    toy_id=toy_id_meta,
                )

            await asyncio.to_thread(send_pattern)
        else:
            raise ValueError("session not extendable")

        now = time.monotonic()
        old_end = float(meta["ends_mono"])
        new_end = max(old_end, now + effective)
        meta["ends_mono"] = new_end
        meta["extension_count"] = int(meta.get("extension_count", 0)) + 1
        meta["last_extended_at"] = datetime.now(timezone.utc).isoformat()
        meta["duration_sec"] = new_end - float(meta["started_monotonic_sec"])
        meta["last_extend_effective_sec"] = effective

        kind_str = str(meta.get("kind", "session"))

        new_task = asyncio.create_task(
            self._run_session_until(task_id),
            name=f"lovense:session:{kind_str}:{toy_id_meta}:wait",
        )
        old_task = self._session_tasks.get(task_id)
        self._session_tasks[task_id] = new_task
        if old_task is not None and old_task is not new_task and not old_task.done():
            old_task.cancel()
            try:
                await old_task
            except asyncio.CancelledError:
                pass

        return {
            "renewed": True,
            "scheduler_task_id": task_id,
            "lovense_resent": True,
            "device_extend_time_sec": effective,
            "remaining_sec": max(0.0, new_end - time.monotonic()),
        }

    async def track_session(
        self,
        *,
        kind: Literal["preset", "pattern"],
        toy_id: str | None,
        duration: float,
        detail: dict[str, Any],
    ) -> str:
        if self._closed:
            raise RuntimeError("scheduler_closed")
        task_id = str(uuid.uuid4())
        requested = float(duration)
        if requested <= 0:
            effective = float(self._session_max_sec)
            duration_capped = True
        else:
            effective = requested
            duration_capped = False

        now_mono = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        self._meta[task_id] = {
            "task_id": task_id,
            "kind": kind,
            "toy_id": toy_id,
            "duration_requested_sec": requested,
            "duration_sec": effective,
            "duration_capped_to_max": duration_capped,
            "extension_count": 0,
            "started_at": started_at,
            "started_monotonic_sec": now_mono,
            "ends_mono": now_mono + effective,
            **detail,
        }
        task = asyncio.create_task(
            self._run_session_until(task_id),
            name=f"lovense:session:{kind}:{toy_id}:wait",
        )
        self._session_tasks[task_id] = task
        return task_id

    def _clamp_actions(self, actions: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for feat, raw in actions.items():
            lo, hi = FUNCTION_RANGES.get(feat, (0, 20))
            v = int(round(float(raw)))
            out[feat] = float(max(lo, min(hi, v)))
        return out

    async def _apply_snapshot(self, toy_id: str) -> None:
        actions: dict[str, float] = {}
        for (tid, feat), lvl in self._levels.items():
            if tid == toy_id:
                actions[feat] = lvl
        actions = self._clamp_actions(actions)

        def send() -> Any:
            if not actions:
                toy_dict = self._fetch_toy_dict(toy_id)
                if toy_dict:
                    zeros = stop_actions(toy_dict)
                    return self._client.function_request(zeros, time=0, toy_id=toy_id)
                return self._client.stop(toy_id)
            return self._client.function_request(actions, time=0, toy_id=toy_id)

        await asyncio.to_thread(send)

    async def _run_slot(
        self,
        task_id: str,
        toy_id: str,
        feature: str,
        level: float,
        duration: float,
    ) -> None:
        lock = self._lock_for(toy_id)
        try:
            async with lock:
                if self._closed:
                    return
                self._levels[(toy_id, feature)] = level
                await self._apply_snapshot(toy_id)

            if duration > 0:
                await asyncio.sleep(duration)
            else:
                wait = asyncio.Event()
                await wait.wait()
        except asyncio.CancelledError:
            raise
        finally:
            async with lock:
                self._levels.pop((toy_id, feature), None)
                self._tasks.pop((toy_id, feature), None)
                self._meta.pop(task_id, None)
                await self._apply_snapshot(toy_id)

    async def schedule_function(
        self,
        toy_id: str,
        actions: dict[Actions, float],
        duration: float,
        *,
        stop_previous: bool,
        loop_on_time: float | None,
        loop_off_time: float | None,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("scheduler_closed")
        if loop_on_time is not None or loop_off_time is not None:
            await self.cancel_every_slot_for_toy(toy_id)
            expanded = self._expand_actions(toy_id, actions)

            def send_loop() -> Any:
                return self._client.function_request(
                    expanded,
                    time=duration,
                    loop_on_time=loop_on_time,
                    loop_off_time=loop_off_time,
                    toy_id=toy_id,
                    stop_previous=True,
                )

            return as_dict(await asyncio.to_thread(send_loop))

        expanded = self._expand_actions(toy_id, actions)
        if stop_previous:
            await self.cancel_every_slot_for_toy(toy_id)

        created: list[dict[str, Any]] = []
        for feature, level in expanded.items():
            await self._cancel_slot(toy_id, feature)
            task_id = str(uuid.uuid4())
            task = asyncio.create_task(
                self._run_slot(task_id, toy_id, feature, float(level), float(duration)),
                name=f"lovense:{toy_id}:{feature}",
            )
            self._tasks[(toy_id, feature)] = task
            now_mono = time.monotonic()
            started_at = datetime.now(timezone.utc).isoformat()
            self._meta[task_id] = {
                "task_id": task_id,
                "kind": "function",
                "toy_id": toy_id,
                "feature": feature,
                "level": float(level),
                "duration_sec": float(duration),
                "started_at": started_at,
                "started_monotonic_sec": now_mono,
                "ends_mono": (now_mono + duration) if duration > 0 else None,
            }
            created.append(self._meta[task_id])
        return {"scheduled": created, "type": "OK"}

    def list_tasks(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        rows: list[dict[str, Any]] = []
        for meta in self._meta.values():
            row = dict(meta)
            ends = row.get("ends_mono")
            if ends is not None:
                row["remaining_sec"] = max(0.0, ends - now)
            else:
                row["remaining_sec"] = None
            rows.append(row)
        rows.sort(
            key=lambda r: (
                r.get("toy_id") or "",
                r.get("kind", "function"),
                r.get("feature", ""),
                r.get("task_id", ""),
            )
        )
        return rows

    async def stop_all(self) -> dict[str, Any]:
        await self.cancel_all_slots()
        response = await asyncio.to_thread(lambda: self._client.stop())
        return as_dict(response)

    async def stop_toy(self, toy_id: str) -> dict[str, Any]:
        await self.cancel_every_slot_for_toy(toy_id)
        response = await asyncio.to_thread(lambda: self._client.stop(toy_id))
        return as_dict(response)

    async def stop_feature(self, toy_id: str, feature: Actions) -> dict[str, Any]:
        feat = str(feature)
        await self._cancel_slot(toy_id, feat)
        lock = self._lock_for(toy_id)
        async with lock:
            self._levels.pop((toy_id, feat), None)
            await self._apply_snapshot(toy_id)
        return {"type": "OK", "toy_id": toy_id, "feature": feat}


def create_app(config: APIConfig | None = None) -> FastAPI:
    cfg = config or APIConfig.from_env()
    client = LANClient(cfg.app_name, cfg.lan_ip, port=cfg.lan_port)

    discovered_toys = execute_or_http_error(lambda: extract_toy_ids(client))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = client
        app.state.scheduler = LanControlScheduler(
            client, session_max_sec=cfg.session_max_sec
        )
        yield
        await app.state.scheduler.shutdown()

    app = FastAPI(
        title="LovensePy LAN API",
        description="LAN Game Mode control with per-motor scheduling (asyncio + lifespan).",
        version="1.4.1",
        lifespan=lifespan,
    )

    patch_openapi_toy_ids(app, sorted({*cfg.allowed_toy_ids, *discovered_toys}))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/meta")
    def meta() -> dict[str, Any]:
        return {
            "actions": [str(item) for item in Actions],
            "presets": [str(item) for item in Presets],
            "pattern_templates": list(PATTERN_TEMPLATES.keys()),
            "toy_ids": extract_toy_ids(client),
            "session_max_sec": cfg.session_max_sec,
        }

    @app.get("/toys")
    def get_toys() -> dict[str, Any]:
        response = execute_or_http_error(client.get_toys)
        return as_dict(response)

    @app.get(
        "/tasks",
        summary="Active scheduler rows",
        response_description=(
            "Each item includes started_at (UTC ISO-8601) and started_monotonic_sec "
            "(time.monotonic() snapshot for remaining_sec math). Preset/pattern time=0 "
            "uses duration_sec=session_max_sec on the server tracker only."
        ),
    )
    async def list_tasks(request: Request) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        return {"tasks": scheduler.list_tasks()}

    @app.post("/command/function")
    async def function_command(request: Request, payload: FunctionCommand) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        if scheduler.closed:
            raise HTTPException(status_code=503, detail="Server is shutting down.")
        try:
            return await scheduler.schedule_function(
                payload.toy_id,
                payload.actions,
                payload.time,
                stop_previous=payload.stop_previous,
                loop_on_time=payload.loop_on_time,
                loop_off_time=payload.loop_off_time,
            )
        except LovenseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            if str(exc) == "scheduler_closed":
                raise HTTPException(status_code=503, detail="Server is shutting down.") from exc
            raise

    @app.post("/command/preset")
    async def preset_command(request: Request, payload: PresetCommand) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        if scheduler.closed:
            raise HTTPException(status_code=503, detail="Server is shutting down.")

        preset_name = str(payload.name)
        existing = scheduler.find_matching_preset_session(payload.toy_id, preset_name)
        if existing:
            try:
                return await scheduler.extend_session(existing, float(payload.time))
            except LovenseError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except RuntimeError as exc:
                if str(exc) == "scheduler_closed":
                    raise HTTPException(
                        status_code=503, detail="Server is shutting down."
                    ) from exc
                raise

        if payload.toy_id:
            await scheduler.cancel_every_slot_for_toy(payload.toy_id)
        else:
            await scheduler.cancel_all_slots()

        def send() -> Any:
            return client.preset_request(payload.name, time=payload.time, toy_id=payload.toy_id)

        try:
            response = as_dict(await asyncio.to_thread(send))
        except LovenseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        try:
            response["scheduler_task_id"] = await scheduler.track_session(
                kind="preset",
                toy_id=payload.toy_id,
                duration=float(payload.time),
                detail={"preset": preset_name},
            )
            response["renewed"] = False
            response["lovense_resent"] = True
        except RuntimeError as exc:
            if str(exc) != "scheduler_closed":
                raise
        return response

    @app.post("/command/pattern")
    async def pattern_command(request: Request, payload: PatternCommand) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        if scheduler.closed:
            raise HTTPException(status_code=503, detail="Server is shutting down.")

        pattern = (
            payload.pattern
            if payload.pattern is not None
            else PATTERN_TEMPLATES[payload.template or PatternTemplate.SOFT]
        )
        sig = pattern_session_signature(
            pattern,
            interval=payload.interval,
            actions=payload.actions,
            template=payload.template,
        )
        existing = scheduler.find_matching_pattern_session(payload.toy_id, sig)
        if existing:
            try:
                return await scheduler.extend_session(existing, float(payload.time))
            except LovenseError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except RuntimeError as exc:
                if str(exc) == "scheduler_closed":
                    raise HTTPException(
                        status_code=503, detail="Server is shutting down."
                    ) from exc
                raise

        if payload.toy_id:
            await scheduler.cancel_every_slot_for_toy(payload.toy_id)
        else:
            await scheduler.cancel_all_slots()

        def send() -> Any:
            return client.pattern_request(
                pattern,
                actions=[str(action) for action in payload.actions] if payload.actions else None,
                interval=payload.interval,
                time=payload.time,
                toy_id=payload.toy_id,
            )

        try:
            response = as_dict(await asyncio.to_thread(send))
        except LovenseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        detail: dict[str, Any] = {
            "interval": payload.interval,
            "pattern_length": len(pattern),
            "pattern_preview": pattern[:16],
            "pattern_session_key": sig,
            "pattern_data": list(pattern),
            "pattern_actions": [str(a) for a in payload.actions] if payload.actions else None,
        }
        if payload.template is not None:
            detail["template"] = str(payload.template)
        try:
            response["scheduler_task_id"] = await scheduler.track_session(
                kind="pattern",
                toy_id=payload.toy_id,
                duration=float(payload.time),
                detail=detail,
            )
            response["renewed"] = False
            response["lovense_resent"] = True
        except RuntimeError as exc:
            if str(exc) != "scheduler_closed":
                raise
        return response

    @app.post("/command/stop/all")
    async def stop_all(request: Request) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        try:
            return await scheduler.stop_all()
        except LovenseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/command/stop/toy")
    async def stop_toy(request: Request, payload: StopToyBody) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        try:
            return await scheduler.stop_toy(payload.toy_id)
        except LovenseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/command/stop/feature")
    async def stop_feature(request: Request, payload: StopFeatureBody) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        try:
            return await scheduler.stop_feature(payload.toy_id, payload.feature)
        except LovenseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/command/stop/toys/batch")
    async def stop_toys_batch(request: Request, payload: StopToysBatchBody) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        results: list[dict[str, Any]] = []
        for tid in payload.toy_ids:
            try:
                results.append(
                    {"toy_id": tid, "ok": True, "response": await scheduler.stop_toy(tid)}
                )
            except LovenseError as exc:
                results.append({"toy_id": tid, "ok": False, "error": str(exc)})
        return {"results": results}

    @app.post("/command/stop/features/batch")
    async def stop_features_batch(
        request: Request, payload: StopFeaturesBatchBody
    ) -> dict[str, Any]:
        scheduler: LanControlScheduler = request.app.state.scheduler
        results: list[dict[str, Any]] = []
        for item in payload.items:
            try:
                results.append(
                    {
                        "toy_id": item.toy_id,
                        "feature": str(item.feature),
                        "ok": True,
                        "response": await scheduler.stop_feature(item.toy_id, item.feature),
                    }
                )
            except LovenseError as exc:
                results.append(
                    {
                        "toy_id": item.toy_id,
                        "feature": str(item.feature),
                        "ok": False,
                        "error": str(exc),
                    }
                )
        return {"results": results}

    return app


try:
    app = create_app()
except ValueError as exc:
    app = FastAPI(
        title="LovensePy LAN API",
        description="Configuration error. Set LOVENSE_LAN_IP.",
        version="1.4.1",
    )

    @app.get("/health")
    def health_error() -> dict[str, str]:
        return {"status": "error"}

    @app.get("/config-error")
    def config_error() -> dict[str, str]:
        raise HTTPException(status_code=500, detail=str(exc))

    @app.api_route("/{_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def fail_all(_path: str) -> dict[str, str]:
        raise HTTPException(
            status_code=500,
            detail="Invalid configuration. Set LOVENSE_LAN_IP and restart server.",
        )
