"""
Tests for Socket API — local only (no token, no WebSocket, no QR).

Run: LOVENSE_LAN_IP=... LOVENSE_LAN_PORT=20011 pytest tests/test_socket_local.py -v -s
"""

import os
import time

from lovensepy import LANClient, SyncPatternPlayer, features_for_toy
from tests.conftest import requires_lan
from tests.test_standard_local import _parse_lan_toys


def _log(msg: str) -> None:
    print(msg, flush=True)


@requires_lan
def test_local_only():
    """
    Socket API by local — ONLY local, no token, no WebSocket, no QR.

    Uses SyncPatternPlayer from library.
    LOVENSE_LAN_PORT: 20011 (HTTP), 30011/30011 (HTTPS, auto-detected, verify_ssl=0).
    """
    ip = os.environ["LOVENSE_LAN_IP"]
    https_port = os.environ.get("LOVENSE_LAN_HTTPS_PORT")
    port = int(os.environ.get("LOVENSE_LAN_PORT", "20011"))
    verify_ssl = os.environ.get("LOVENSE_VERIFY_SSL", "0").lower() in ("1", "true", "yes")
    if https_port:
        client = LANClient(
            "lovensepy_local_only",
            ip,
            use_https=True,
            ssl_port=int(https_port),
            verify_ssl=verify_ssl,
        )
    elif port in (30011, 30011):
        client = LANClient(
            "lovensepy_local_only", ip, use_https=True, ssl_port=port, verify_ssl=verify_ssl
        )
    else:
        client = LANClient("lovensepy_local_only", ip, port=port)

    resp = client.get_toys()
    toys = _parse_lan_toys(resp)
    assert toys, "No toys — connect toys to Lovense Remote, enable Game Mode, same LAN"

    player = SyncPatternPlayer(client, toys)
    sequence = [(tid, feat) for tid, t in toys.items() for feat in features_for_toy(t)]

    _log(f"\n>>> [LOCAL ONLY] {len(toys)} toy(s) via SyncPatternPlayer:")
    for tid, t in toys.items():
        name = t.get("name") or t.get("nickName") or "—"
        _log(f"    {tid}: {name} — {player.features(tid)}")

    FEATURE_DURATION = 5.0
    COMBO_DURATION = 4.0

    _log(f"\n>>> 1. Per-motor sine wave ({FEATURE_DURATION}s each) — {len(sequence)} steps:")
    last_tid: str | None = None
    for idx, (tid, feat) in enumerate(sequence):
        name = toys[tid].get("name") or toys[tid].get("nickName") or tid
        _log(f"    [{idx + 1}/{len(sequence)}] {name} — {feat}")
        player.play_sine_wave(
            tid, feat, duration_sec=FEATURE_DURATION, stop_prev_first=(tid != last_tid)
        )
        last_tid = tid
        time.sleep(0.3)

    toy_list = list(toys.items())
    all_targets = [(tid, f) for tid, t in toys.items() for f in features_for_toy(t)]

    if len(all_targets) >= 2:
        two_motor_toys = [(tid, t) for tid, t in toys.items() if len(features_for_toy(t)) >= 2]
        if two_motor_toys:
            tid, t = two_motor_toys[0]
            feats = features_for_toy(t)[:2]
            targets_2m = [(tid, f) for f in feats]
            name = t.get("name") or t.get("nickName") or tid
            _log(f"\n>>> 2. Two motors together ({name}: {feats}) — {COMBO_DURATION}s:")
            player.play_combo(targets_2m, duration_sec=COMBO_DURATION)
            time.sleep(0.5)

        if len(toy_list) >= 2:
            t1_id, t1 = toy_list[0]
            t2_id, t2 = toy_list[1]
            f1, f2 = features_for_toy(t1)[0], features_for_toy(t2)[0]
            n1, n2 = t1.get("name") or t1_id, t2.get("name") or t2_id
            _log(f"\n>>> 3. Two toys together ({n1}, {n2}) — {COMBO_DURATION}s:")
            player.play_combo([(t1_id, f1), (t2_id, f2)], duration_sec=COMBO_DURATION)
            time.sleep(0.5)

        _log(f"\n>>> 4. All motors together — {COMBO_DURATION}s:")
        player.play_combo(all_targets, duration_sec=COMBO_DURATION)
        time.sleep(0.5)

    time.sleep(0.2)
    for tid in toys:
        player.stop(tid)
    _log(">>> Done.")
