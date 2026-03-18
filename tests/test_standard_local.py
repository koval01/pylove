"""
Tests for Standard API — local (LAN Game Mode).

Run: LOVENSE_LAN_IP=... LOVENSE_LAN_PORT=20011 pytest tests/test_standard_local.py -v -s
"""

import math
import os
import secrets
import time
from typing import Any

import pytest

from lovensepy import Actions, LANClient, LovenseError, Presets, features_for_toy
from lovensepy._models import GetToysResponse
from tests.conftest import requires_lan


def _log(msg: str) -> None:
    print(msg, flush=True)


def _parse_lan_toys(resp: GetToysResponse | None) -> dict[str, dict[str, Any]]:
    """Normalize typed GetToysResponse into {toy_id: toy_dict}."""
    toys: dict[str, dict[str, Any]] = {}
    if not resp or resp.data is None:
        return toys
    for toy in resp.data.toys:
        toys[str(toy.id)] = toy.model_dump()
    return toys


@requires_lan
class TestLANClient:
    """LAN client tests. Requires LOVENSE_LAN_IP."""

    @pytest.fixture
    def client(self):
        ip = os.environ["LOVENSE_LAN_IP"]
        port = int(os.environ.get("LOVENSE_LAN_PORT", "20011"))
        return LANClient("lovensepy_test", ip, port=port)

    def test_get_toys(self, client):
        """API should return toys info (or empty if none connected)."""
        try:
            resp = client.get_toys()
        except LovenseError as e:
            pytest.skip(f"Network error: {e}")
        assert resp.code is not None
        assert resp.type is not None

    def test_get_toys_name(self, client):
        """API should return toy names."""
        try:
            resp = client.get_toys_name()
        except LovenseError as e:
            pytest.skip(f"Network error: {e}")
        assert resp.code is not None
        assert resp.type is not None

    def test_function_and_stop(self, client):
        """Send function then stop."""
        try:
            r1 = client.function_request({Actions.ALL: 2}, time=2)
            r2 = client.stop()
        except LovenseError as e:
            pytest.skip(f"Network error: {e}")
        assert r1.code is not None
        assert r2.code is not None

    def test_preset_request(self, client):
        """Send preset for short duration."""
        try:
            resp = client.preset_request(Presets.PULSE, time=2)
        except LovenseError as e:
            pytest.skip(f"Network error: {e}")
        assert resp.code is not None

    def test_pattern_request(self, client):
        """Send pattern."""
        try:
            resp = client.pattern_request([5, 10, 15], time=2)
        except LovenseError as e:
            pytest.skip(f"Network error: {e}")
        assert resp.code is not None

    def test_decode_response(self, client):
        """decode_response formats response string."""
        try:
            resp = client.get_toys()
        except LovenseError as e:
            pytest.skip(f"Network error: {e}")
        s = client.decode_response(resp)
        assert isinstance(s, str)
        assert len(s) > 0


@requires_lan
def test_full_flow():
    """
    Full LAN flow: get toys, per-motor sine wave, combos (2 motors, 2 toys, all).
    Like Socket API test but via HTTP.
    """
    ip = os.environ["LOVENSE_LAN_IP"]
    port = int(os.environ.get("LOVENSE_LAN_PORT", "20011"))
    client = LANClient("lovensepy_test", ip, port=port)

    try:
        resp = client.get_toys()
    except LovenseError as e:
        pytest.skip(f"Network error: {e}")
    toys = _parse_lan_toys(resp)
    assert toys, "No toys — connect toys to Lovense Remote Game Mode"

    _log(f"\n>>> Detected {len(toys)} toy(s):")
    for tid, t in toys.items():
        name = t.get("name") or t.get("nickName") or "—"
        model = t.get("toyType") or name
        feats = features_for_toy(t)
        _log(f"    {tid}: {name} ({model}) — {feats}")

    sequence: list[tuple[str, str]] = []
    for tid, t in toys.items():
        for feat in features_for_toy(t):
            sequence.append((tid, feat))

    FEATURE_DURATION = 5.0
    NUM_STEPS = 100
    INTERVAL = FEATURE_DURATION / NUM_STEPS

    def stop_all_features(toy_id: str) -> dict[str, int]:
        feats = features_for_toy(toys[toy_id])
        return {f: 0 for f in feats}

    _log(f"\n>>> 1. Per-motor sine wave ({FEATURE_DURATION}s each) — {len(sequence)} steps:")
    last_toy_id: str | None = None
    for idx, (tid, feat) in enumerate(sequence):
        name = toys[tid].get("name") or toys[tid].get("nickName") or tid
        _log(f"    [{idx + 1}/{len(sequence)}] {name} — {feat}")
        feats = features_for_toy(toys[tid])
        stop_prev = tid != last_toy_id
        for i in range(NUM_STEPS + 1):
            t = (i / NUM_STEPS) * FEATURE_DURATION
            level = int(10 + 10 * math.sin(math.pi * t))
            level = max(0, min(20, level))
            action = {f: (level if f == feat else 0) for f in feats}
            client.function_request(action, time=0, toy_id=tid, stop_previous=stop_prev)
            stop_prev = False
            time.sleep(INTERVAL)
        last_toy_id = tid
        time.sleep(0.15)
        client.function_request(stop_all_features(tid), time=0, toy_id=tid)
        time.sleep(0.3)

    rng = secrets.SystemRandom()
    COMBO_DURATION = 4.0
    toy_list = list(toys.items())
    all_targets = [(tid, f) for tid, t in toys.items() for f in features_for_toy(t)]

    if len(all_targets) >= 2:
        two_motor_toys = [(tid, t) for tid, t in toys.items() if len(features_for_toy(t)) >= 2]
        if two_motor_toys:
            tid, t = two_motor_toys[0]
            feats = features_for_toy(t)[:2]
            targets_2m = [(tid, f) for f in feats]
            name = t.get("name") or t.get("nickName") or tid
            _log(
                f"\n>>> 2. Two motors together ({name}: {feats}) — "
                f"{COMBO_DURATION}s, random phases:"
            )
            phases = {t: rng.uniform(0, 2 * math.pi) for t in targets_2m}
            for i in range(101):
                t_norm = i / 100
                levels = {
                    t: max(0, min(20, int(10 + 10 * math.sin(math.pi * t_norm + phases[t]))))
                    for t in targets_2m
                }
                action = {f: levels[(tid, f)] for f in feats}
                client.function_request(action, time=0, toy_id=tid, stop_previous=False)
                time.sleep(COMBO_DURATION / 100)
            time.sleep(0.15)
            client.function_request(stop_all_features(tid), time=0, toy_id=tid)
            time.sleep(0.5)

        if len(toy_list) >= 2:
            t1_id, t1 = toy_list[0]
            t2_id, t2 = toy_list[1]
            f1, f2 = features_for_toy(t1)[0], features_for_toy(t2)[0]
            n1, n2 = t1.get("name") or t1_id, t2.get("name") or t2_id
            _log(f"\n>>> 3. Two toys together ({n1}, {n2}) — {COMBO_DURATION}s, random phases:")
            targets_2t = [(t1_id, f1), (t2_id, f2)]
            phases = {t: rng.uniform(0, 2 * math.pi) for t in targets_2t}
            last_tid: str | None = None
            for i in range(101):
                t_norm = i / 100
                for tid, feat in targets_2t:
                    level = max(
                        0, min(20, int(10 + 10 * math.sin(math.pi * t_norm + phases[(tid, feat)])))
                    )
                    stop_prev = tid != last_tid
                    client.function_request(
                        {feat: level}, time=0, toy_id=tid, stop_previous=stop_prev
                    )
                    last_tid = tid
                time.sleep(COMBO_DURATION / 100)
            time.sleep(0.15)
            for tid in (t1_id, t2_id):
                client.function_request(stop_all_features(tid), time=0, toy_id=tid)
            time.sleep(0.5)

        _log(f"\n>>> 4. All motors together — {COMBO_DURATION}s, random phases:")
        by_toy: dict[str, list[str]] = {}
        for tid, feat in all_targets:
            by_toy.setdefault(tid, []).append(feat)
        phases = {t: rng.uniform(0, 2 * math.pi) for t in all_targets}
        last_tid_4: str | None = None
        for i in range(101):
            t_norm = i / 100
            for tid, feats in by_toy.items():
                levels = {
                    f: max(0, min(20, int(10 + 10 * math.sin(math.pi * t_norm + phases[(tid, f)]))))
                    for f in feats
                }
                stop_prev = tid != last_tid_4
                client.function_request(levels, time=0, toy_id=tid, stop_previous=stop_prev)
                last_tid_4 = tid
            time.sleep(COMBO_DURATION / 100)
        time.sleep(0.15)
        for tid in toys:
            client.function_request(stop_all_features(tid), time=0, toy_id=tid)
        time.sleep(0.5)

    time.sleep(0.2)
    for tid in toys:
        client.function_request(stop_all_features(tid), time=0, toy_id=tid)
    _log(">>> Done.")
