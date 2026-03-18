"""
High-level pattern players for Lovense toys.

Use raw methods (function_request, send_command) for custom logic,
or PatternPlayer for ready-made sine waves and combos.

Example (LAN, sync):
    from lovensepy import LANClient
    from lovensepy.patterns import SyncPatternPlayer
    from lovensepy.toy_utils import features_for_toy

    client = LANClient("my_app", "192.168.1.100", port=20011)
    toys = {...}  # from client.get_toys()
    player = SyncPatternPlayer(client, toys)
    player.play_sine_wave("toy_id", "Vibrate1", duration_sec=5)
    player.play_combo([("toy1", "Vibrate1"), ("toy2", "Vibrate")], duration_sec=4)

Example (Socket API, async):
    from lovensepy import SocketAPIClient
    from lovensepy.patterns import AsyncPatternPlayer

    player = AsyncPatternPlayer(client, toys)
    await player.play_sine_wave("toy_id", "Vibrate1", duration_sec=5)
    await player.play_combo([("toy1", "Vibrate1"), ("toy2", "Vibrate")], duration_sec=4)
"""

import asyncio
import math
import secrets
import time
from typing import Any

from ._models import GetToysData, GetToysResponse, ToyInfo
from .toy_utils import features_for_toy, stop_actions

__all__ = ["SyncPatternPlayer", "AsyncPatternPlayer"]


def _normalize_toys(toys: Any) -> dict[str, dict[str, Any]]:
    """Normalize toy collection input for pattern players.

    Accepts either the legacy toy dict mapping ``{toy_id: toy_dict}`` or typed
    `GetToysResponse` / `GetToysData` objects.
    """
    if isinstance(toys, GetToysResponse):
        if toys.data is None:
            return {}
        return {t.id: t.model_dump() for t in toys.data.toys}
    if isinstance(toys, GetToysData):
        return {t.id: t.model_dump() for t in toys.toys}
    if isinstance(toys, list) and all(isinstance(t, ToyInfo) for t in toys):
        return {t.id: t.model_dump() for t in toys}
    if isinstance(toys, dict):
        # Legacy expected shape: {toy_id: toy_dict}
        return toys
    raise TypeError("toys must be a legacy toy dict mapping or a GetToysResponse/GetToysData")


def _actions_to_str(actions: dict[str, int | float]) -> str:
    return ",".join(f"{k}:{v}" for k, v in actions.items())


def _sine_wave_steps(
    feature: str,
    all_features: list[str],
    duration_sec: float,
    num_steps: int = 100,
) -> list[tuple[dict[str, int], bool]]:
    """Generate (actions_dict, stop_prev) for sine wave. No I/O."""
    steps: list[tuple[dict[str, int], bool]] = []
    stop_prev = True
    for i in range(num_steps + 1):
        t_val = (i / num_steps) * duration_sec
        level = int(10 + 10 * math.sin(math.pi * t_val))
        level = max(0, min(20, level))
        action = {f: (level if f == feature else 0) for f in all_features}
        steps.append((action, stop_prev))
        stop_prev = False
    # final stop
    steps.append(({f: 0 for f in all_features}, False))
    return steps


def _combo_steps(
    targets: list[tuple[str, str]],
    toys: dict[str, dict[str, Any]],  # pylint: disable=unused-argument
    duration_sec: float,  # pylint: disable=unused-argument
    num_steps: int = 100,
) -> list[list[tuple[str, dict[str, int], bool]]]:
    """Generate frames of (toy_id, actions_dict, stop_prev).

    One sleep per frame. Caller does stop at end.
    """
    rng = secrets.SystemRandom()
    phases = {t: rng.uniform(0, 2 * math.pi) for t in targets}
    by_toy: dict[str, list[str]] = {}
    for tid, feat in targets:
        by_toy.setdefault(tid, []).append(feat)

    frames: list[list[tuple[str, dict[str, int], bool]]] = []
    for i in range(num_steps + 1):
        t_norm = i / num_steps
        frame: list[tuple[str, dict[str, int], bool]] = []
        last_tid: str | None = None
        for tid, feats in by_toy.items():
            levels = {
                f: max(
                    0,
                    min(20, int(10 + 10 * math.sin(math.pi * t_norm + phases[(tid, f)]))),
                )
                for f in feats
            }
            stop_prev = tid != last_tid
            frame.append((tid, levels, stop_prev))
            last_tid = tid
        frames.append(frame)
    return frames


class SyncPatternPlayer:
    """
    Sync pattern player for LANClient.

    Use play_sine_wave, play_combo for ready-made patterns.
    Uses stop_previous when switching toys.
    """

    def __init__(
        self,
        client: Any,
        toys: Any,
    ) -> None:
        self._client = client
        self._toys = _normalize_toys(toys)

    def features(self, toy_id: str) -> list[str]:
        """Get features for toy."""
        return features_for_toy(self._toys[toy_id])

    def stop(self, toy_id: str) -> Any:
        """Stop all motors of toy."""
        actions = stop_actions(self._toys[toy_id])
        return self._client.function_request(actions, time=0, toy_id=toy_id)

    def play_sine_wave(
        self,
        toy_id: str,
        feature: str,
        duration_sec: float = 5.0,
        num_steps: int = 100,
        stop_prev_first: bool = True,
    ) -> None:
        """
        Play sine wave on one feature for duration_sec.

        Uses time_sec=0 per step; device holds level until next command.
        """
        feats = self.features(toy_id)
        if feature not in feats:
            raise ValueError(f"Toy {toy_id} has no feature {feature} (available: {feats})")
        steps = _sine_wave_steps(feature, feats, duration_sec, num_steps)
        interval = duration_sec / num_steps
        stop_prev = stop_prev_first
        for action, sp in steps[:-1]:
            self._client.function_request(action, time=0, toy_id=toy_id, stop_previous=stop_prev)
            stop_prev = sp
            time.sleep(interval)
        time.sleep(0.15)
        self._client.function_request(steps[-1][0], time=0, toy_id=toy_id)

    def play_combo(
        self,
        targets: list[tuple[str, str]],
        duration_sec: float = 4.0,
        num_steps: int = 100,
    ) -> None:
        """
        Play sine waves on multiple (toy_id, feature) with random phases.

        targets: [(toy_id, feature), ...] e.g. [("t1", "Vibrate1"), ("t2", "Vibrate")]
        """
        if not targets:
            return
        frames = _combo_steps(targets, self._toys, duration_sec, num_steps)
        interval = duration_sec / num_steps
        for frame in frames:
            for tid, action, stop_prev in frame:
                self._client.function_request(action, time=0, toy_id=tid, stop_previous=stop_prev)
            time.sleep(interval)
        time.sleep(0.15)
        for tid in {t for t, _ in targets}:
            self.stop(tid)


class AsyncPatternPlayer:
    """
    Async pattern player for SocketAPIClient.

    Use play_sine_wave, play_combo for ready-made patterns.
    Uses stop_previous when switching toys.
    """

    def __init__(
        self,
        client: Any,
        toys: Any,
    ) -> None:
        self._client = client
        self._toys = _normalize_toys(toys)

    def features(self, toy_id: str) -> list[str]:
        """Get features for toy."""
        return features_for_toy(self._toys[toy_id])

    async def stop(self, toy_id: str) -> None:
        """Stop all motors of toy."""
        feats = self.features(toy_id)
        action = ",".join(f"{f}:0" for f in feats)
        await self._client.send_command_await("Function", action, time_sec=0, toy=toy_id)

    async def play_sine_wave(
        self,
        toy_id: str,
        feature: str,
        duration_sec: float = 5.0,
        num_steps: int = 100,
        stop_prev_first: bool = True,
    ) -> None:
        """
        Play sine wave on one feature for duration_sec.

        Uses time_sec=0 per step; device holds level until next command.
        """
        feats = self.features(toy_id)
        if feature not in feats:
            raise ValueError(f"Toy {toy_id} has no feature {feature} (available: {feats})")
        steps = _sine_wave_steps(feature, feats, duration_sec, num_steps)
        interval = duration_sec / num_steps
        stop_prev = stop_prev_first
        for action, sp in steps[:-1]:
            action_str = _actions_to_str(action)
            await self._client.send_command_await(
                "Function", action_str, time_sec=0, toy=toy_id, stop_previous=1 if stop_prev else 0
            )
            stop_prev = sp
            await asyncio.sleep(interval)
        await asyncio.sleep(0.15)
        await self._client.send_command_await(
            "Function", _actions_to_str(steps[-1][0]), time_sec=0, toy=toy_id
        )

    async def play_combo(
        self,
        targets: list[tuple[str, str]],
        duration_sec: float = 4.0,
        num_steps: int = 100,
    ) -> None:
        """
        Play sine waves on multiple (toy_id, feature) with random phases.

        targets: [(toy_id, feature), ...] e.g. [("t1", "Vibrate1"), ("t2", "Vibrate")]
        """
        if not targets:
            return
        frames = _combo_steps(targets, self._toys, duration_sec, num_steps)
        interval = duration_sec / num_steps
        for frame in frames:
            for tid, action, stop_prev in frame:
                action_str = _actions_to_str(action)
                await self._client.send_command_await(
                    "Function", action_str, time_sec=0, toy=tid, stop_previous=1 if stop_prev else 0
                )
            await asyncio.sleep(interval)
        await asyncio.sleep(0.15)
        for tid in {t for t, _ in targets}:
            await self.stop(tid)
