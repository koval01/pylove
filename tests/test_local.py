"""
Tests for Standard API — local (LAN Game Mode).

Run: LOVENSE_LAN_IP=... LOVENSE_LAN_PORT=20011 pytest tests/test_local.py -v -s
"""

import os

import pytest

from lovensepy import (
    Actions,
    LANClient,
    LovenseError,
    Presets,
    SyncPatternPlayer,
)
from tests.conftest import requires_lan
from tests.helpers.lan_scenarios import (
    build_lan_client_from_env,
    parse_lan_toys,
    run_lan_function_demo,
    run_sync_pattern_player_demo,
)


def _log(msg: str) -> None:
    print(msg, flush=True)


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

    toys = parse_lan_toys(resp)
    assert toys, "No toys — connect toys to Lovense Remote Game Mode"

    run_lan_function_demo(client, toys, log_fn=_log)


@requires_lan
def test_sync_pattern_player_flow():
    """
    LAN + SyncPatternPlayer flow: get toys, run per-motor waves and combos, stop all.
    """
    client = build_lan_client_from_env("lovensepy_local_only")
    resp = client.get_toys()
    toys = parse_lan_toys(resp)
    assert toys, "No toys — connect toys to Lovense Remote, enable Game Mode, same LAN"

    player = SyncPatternPlayer(client, toys)
    run_sync_pattern_player_demo(player, toys, log_fn=_log)
