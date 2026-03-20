"""
Socket API integration demo scenarios and helpers.

Orchestration helpers for integration tests. They call the public library API.
"""

from __future__ import annotations

import asyncio
import math
import secrets
from typing import Any, Callable

from lovensepy import SocketAPIClient, features_for_toy


def log(msg: str) -> None:
    print(msg, flush=True)


def _build_toy_feature_sequence(toys: dict[str, Any]) -> list[tuple[str, str]]:
    sequence: list[tuple[str, str]] = []
    for tid, t in toys.items():
        for feat in features_for_toy(t):
            sequence.append((tid, feat))
    return sequence


async def run_socket_function_demo(
    client: SocketAPIClient,
    toys: dict[str, Any],
    *,
    feature_duration_sec: float = 5.0,
    num_steps: int = 100,
    combo_duration_sec: float = 4.0,
    log_fn: Callable[[str], None] = log,
) -> None:
    """Sine wave + combos demo executed via SocketAPIClient.send_command calls."""

    sequence = _build_toy_feature_sequence(toys)
    log_fn(
        f"\n>>> 1. Per-motor sine wave ({feature_duration_sec}s each) — {len(sequence)} steps:"
    )

    def stop_all_features_of_toy(toy_id: str) -> str:
        feats = features_for_toy(toys[toy_id])
        return ",".join(f"{f}:0" for f in feats)

    interval_sec = feature_duration_sec / num_steps

    async def send_sine_for_feature(
        toy_id: str,
        feature: str,
        stop_prev_first: bool = True,
    ) -> None:
        stop_prev = stop_prev_first
        for i in range(num_steps + 1):
            t = (i / num_steps) * feature_duration_sec
            level = int(10 + 10 * math.sin(math.pi * t))
            level = max(0, min(20, level))
            client.send_command(
                "Function",
                f"{feature}:{level}",
                time_sec=0,
                toy=toy_id,
                stop_previous=1 if stop_prev else 0,
            )
            stop_prev = False
            await asyncio.sleep(interval_sec)
        await asyncio.sleep(0.15)
        action = stop_all_features_of_toy(toy_id)
        await client.send_command_await("Function", action, time_sec=0, toy=toy_id)

    rng = secrets.SystemRandom()

    async def send_sine_combo(
        targets: list[tuple[str, str]],
        duration_sec: float,
    ) -> None:
        phases = {t: rng.uniform(0, 2 * math.pi) for t in targets}
        by_toy: dict[str, list[str]] = {}
        for tid, feat in targets:
            by_toy.setdefault(tid, []).append(feat)

        num_local_steps = num_steps
        interval = duration_sec / num_local_steps
        last_tid_combo: str | None = None

        for i in range(num_local_steps + 1):
            t_norm = i / num_local_steps
            levels: dict[tuple[str, str], int] = {}
            for tid, feat in targets:
                phase = phases[(tid, feat)]
                level = 10 + 10 * math.sin(math.pi * t_norm + phase)
                levels[(tid, feat)] = max(0, min(20, int(level)))

            for tid, feats in by_toy.items():
                action = ",".join(f"{f}:{levels[(tid, f)]}" for f in feats)
                stop_prev = tid != last_tid_combo
                client.send_command(
                    "Function",
                    action,
                    time_sec=0,
                    toy=tid,
                    stop_previous=1 if stop_prev else 0,
                )
                last_tid_combo = tid

            await asyncio.sleep(interval)

        await asyncio.sleep(0.15)
        for tid in by_toy:
            action = stop_all_features_of_toy(tid)
            await client.send_command_await("Function", action, time_sec=0, toy=tid)

    last_tid: str | None = None
    for idx, (tid, feat) in enumerate(sequence):
        toy = toys[tid]
        name = toy.get("name") or tid
        log_fn(f"    [{idx + 1}/{len(sequence)}] {name} — {feat}")
        await send_sine_for_feature(tid, feat, stop_prev_first=(tid != last_tid))
        last_tid = tid
        await asyncio.sleep(0.3)

    combo_duration = combo_duration_sec
    toy_list = list(toys.items())
    all_targets = [(tid, f) for tid, t in toys.items() for f in features_for_toy(t)]

    if len(all_targets) >= 2:
        two_motor_toys = [(tid, t) for tid, t in toys.items() if len(features_for_toy(t)) >= 2]
        if two_motor_toys:
            tid, t = two_motor_toys[0]
            feats = features_for_toy(t)[:2]
            targets_2m = [(tid, f) for f in feats]
            name = t.get("name") or tid
            log_fn(
                f"\n>>> 2. Two motors together ({name}: {feats}) — "
                f"{combo_duration}s, random phases:"
            )
            await send_sine_combo(targets_2m, combo_duration)
            await asyncio.sleep(0.5)

        if len(toy_list) >= 2:
            t1_id, t1 = toy_list[0]
            t2_id, t2 = toy_list[1]
            f1, f2 = features_for_toy(t1)[0], features_for_toy(t2)[0]
            n1, n2 = t1.get("name") or t1_id, t2.get("name") or t2_id
            log_fn(
                f"\n>>> 3. Two toys together ({n1}, {n2}) — "
                f"{combo_duration}s, random phases:"
            )
            targets_2t = [(t1_id, f1), (t2_id, f2)]
            await send_sine_combo(targets_2t, combo_duration)
            await asyncio.sleep(0.5)

        log_fn(f"\n>>> 4. All motors together — {combo_duration}s, random phases:")
        await send_sine_combo(all_targets, combo_duration)
        await asyncio.sleep(0.5)

    await asyncio.sleep(0.2)
    for tid in toys:
        action = stop_all_features_of_toy(tid)
        await client.send_command_await("Function", action, time_sec=0, toy=tid)
    log_fn(">>> Done.")

