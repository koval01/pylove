"""Unit tests for Home Assistant MQTT bridge (no broker required)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from lovensepy._models import GetToysResponse
from lovensepy.ble_direct.hub import BleDirectHub
from lovensepy.exceptions import LovenseBLEError
from lovensepy.integrations.mqtt.discovery import (
    build_discovery_payloads,
    default_availability_topic,
)
from lovensepy.integrations.mqtt.ha_bridge import (
    HAMqttBridge,
    _battery_from_payload,
    _clamp_feature,
    _normalize_toy_row_from_get_toys,
    _parse_toy_list_data,
    _strength_from_payload,
    _toy_connected_from_dict,
)
from lovensepy.integrations.mqtt.state import StateDeduper
from lovensepy.integrations.mqtt.topics import (
    mqtt_safe_toy_id,
    subscribe_wildcard,
    topic_segment_to_action_name,
)


def test_mqtt_safe_toy_id_sanitizes():
    assert mqtt_safe_toy_id("ab/cd#+") == "ab_cd"


def test_subscribe_wildcard():
    assert subscribe_wildcard("lovensepy") == "lovensepy/+/+/set"


def test_topic_segment_to_action_name():
    assert topic_segment_to_action_name("vibrate") == "Vibrate"
    assert topic_segment_to_action_name("VIBRATE1") == "Vibrate1"
    assert topic_segment_to_action_name("nope") is None


def test_state_deduper():
    d = StateDeduper()
    assert d.should_publish("k", "1") is True
    assert d.should_publish("k", "1") is False
    assert d.should_publish("k", "2") is True


def test_parse_toy_list_data():
    toys = _parse_toy_list_data({"toys": {"a": {"name": "X"}, "b": {"id": "bid"}}})
    ids = {t["id"] for t in toys}
    assert ids == {"a", "bid"}


def test_clamp_feature_stroke():
    assert _clamp_feature("Stroke", 150) == 100
    assert _clamp_feature("Pump", 9) == 3


def test_battery_from_payload():
    assert _battery_from_payload({"battery": 42}) == 42
    assert _battery_from_payload({"data": {"level": 5}}) == 5
    assert _battery_from_payload({"value": 100}) == 100
    assert _battery_from_payload({"batteryLevel": "67"}) == 67
    assert _battery_from_payload(None) is None


def test_parse_toy_list_toy_list_and_battery():
    raw = {
        "type": "toy-list",
        "toyList": [
            {"id": "a1", "name": "Gush", "type": "gush", "battery": 88},
        ],
    }
    toys = _parse_toy_list_data(raw)
    assert len(toys) == 1
    assert toys[0]["id"] == "a1"
    assert toys[0]["toyType"] == "gush"
    assert _battery_from_payload(toys[0]) == 88


def test_strength_from_payload():
    out = _strength_from_payload(
        {"id": "t1", "strength": {"vibrate": 12}},
        "t1",
    )
    assert out == {"Vibrate": 12}


def test_build_discovery_payloads_contains_components():
    toy = {"id": "toy1", "name": "Lush", "toyType": "lush"}
    av = default_availability_topic("lovensepy")
    rows = build_discovery_payloads(
        topic_prefix="lovensepy",
        toy_dict=toy,
        bridge_availability_topic=av,
    )
    topics = [r[0] for r in rows]
    assert any(t.startswith("homeassistant/number/") for t in topics)
    assert any(t.startswith("homeassistant/button/") for t in topics)


def test_discovery_preset_select_optimistic_and_option_values():
    toy = {"id": "toy1", "name": "LVS-Gush", "toyType": "gush", "nickName": "Gush 2"}
    av = default_availability_topic("lovensepy")
    rows = build_discovery_payloads(
        topic_prefix="lovensepy",
        toy_dict=toy,
        bridge_availability_topic=av,
        per_toy_availability=False,
    )
    select_presets = [
        json.loads(payload) for topic, payload in rows if "select" in topic and "preset" in topic
    ]
    assert len(select_presets) == 1
    cfg = select_presets[0]
    assert cfg.get("optimistic") is True
    assert cfg["options"] == ["pulse", "wave", "fireworks", "earthquake"]
    topics = [r[0] for r in rows]
    assert any(t.startswith("homeassistant/select/") for t in topics)
    assert any(t.startswith("homeassistant/sensor/") for t in topics)
    for _, payload in rows:
        cfg = json.loads(payload)
        assert "availability" in cfg
        assert len(cfg["availability"]) == 1
        assert cfg["availability"][0]["topic"] == av
        assert "device" in cfg


def test_build_discovery_payloads_bridge_only_availability():
    toy = {"id": "toy1", "name": "Lush", "toyType": "lush"}
    av = default_availability_topic("lovensepy")
    rows = build_discovery_payloads(
        topic_prefix="lovensepy",
        toy_dict=toy,
        bridge_availability_topic=av,
        per_toy_availability=False,
    )
    cfg = json.loads(rows[0][1])
    assert len(cfg["availability"]) == 1
    assert cfg["availability"][0]["topic"] == av


def test_toy_connected_from_dict_status():
    assert _toy_connected_from_dict({"status": "1"}) is True
    assert _toy_connected_from_dict({"status": "0"}) is False
    assert _toy_connected_from_dict({}) is True


def test_hamqttbridge_lazy_export_from_root():
    import lovensepy as lp
    from lovensepy.integrations.mqtt import HAMqttBridge

    assert getattr(lp, "HAMqttBridge") is HAMqttBridge


def test_hamqttbridge_lan_requires_ip():
    with pytest.raises(ValueError, match="lan_ip"):
        HAMqttBridge("127.0.0.1", transport="lan")


def test_hamqttbridge_ble_disables_toy_events_by_transport():
    b = HAMqttBridge("127.0.0.1", transport="ble", use_toy_events=True)
    assert b._use_toy_events is False


def test_hamqttbridge_ble_hub_only_with_ble_transport():
    with pytest.raises(ValueError, match="ble_hub"):
        HAMqttBridge("127.0.0.1", lan_ip="10.0.0.1", ble_hub=BleDirectHub())


def test_normalize_toy_row_from_get_toys_sets_toy_type_from_type():
    from lovensepy._models import ToyInfo

    info = ToyInfo.model_validate({"id": "x", "name": "LVS-Lush", "type": "lush", "status": "1"})
    d = _normalize_toy_row_from_get_toys(info)
    assert d.get("toyType") == "lush"


def test_ha_discovery_prefers_ble_nickname_and_fills_toy_type_from_type_slug():
    """Same shape as BLE :meth:`BleDirectHub.get_toys` after ToyConfig branding."""
    from lovensepy._models import ToyInfo

    info = ToyInfo.model_validate(
        {
            "id": "edge_a716eeff1a",
            "name": "LVS-Edge",
            "status": "1",
            "version": "243",
            "battery": 95,
            "nickName": "Edge 2",
            "fullFunctionNames": ["Vibrate1", "Vibrate2"],
            "toyType": None,
            "type": "edge",
        }
    )
    d = _normalize_toy_row_from_get_toys(info)
    assert d["toyType"] == "edge"
    av = default_availability_topic("lovensepy")
    rows = build_discovery_payloads(
        topic_prefix="lovensepy",
        toy_dict=d,
        bridge_availability_topic=av,
        per_toy_availability=False,
    )
    assert rows
    cfg0 = json.loads(rows[0][1])
    assert cfg0["device"]["name"] == "Edge 2"
    assert cfg0["device"]["model"] == "edge"


def _make_partial_bridge():
    b = HAMqttBridge("127.0.0.1", lan_ip="127.0.0.1", use_toy_events=False)
    b._topic_prefix = "lovensepy"
    b._toys = {
        "t1": {"id": "real1", "name": "Test", "toyType": "lush"},
    }
    published: list[tuple[str, str]] = []

    class _Mqtt:
        def publish(
            self,
            topic: str,
            payload: str | None = None,
            qos: int = 0,
            retain: bool = False,
            properties: object | None = None,
        ) -> None:
            published.append((topic, str(payload) if payload is not None else ""))

    b._mqtt = _Mqtt()
    lan = AsyncMock()
    b._control = lan
    b._deduper = StateDeduper()
    return b, lan, published


def test_handle_command_function_request():
    async def _run():
        b, lan, _pub = _make_partial_bridge()
        await b._handle_command_topic("lovensepy/t1/vibrate/set", b"7")
        lan.function_request.assert_awaited_once()
        args, kwargs = lan.function_request.await_args
        assert args[0]["Vibrate"] == 7
        assert kwargs["toy_id"] == "real1"

    asyncio.run(_run())


def test_handle_command_stop():
    async def _run():
        b, lan, _pub = _make_partial_bridge()
        await b._handle_command_topic("lovensepy/t1/stop/set", b"PRESS")
        lan.stop.assert_awaited_once_with(toy_id="real1")

    asyncio.run(_run())


def test_handle_command_preset():
    async def _run():
        b, lan, _pub = _make_partial_bridge()
        await b._handle_command_topic("lovensepy/t1/preset/set", b"pulse")
        lan.preset_request.assert_awaited_once()
        args, kwargs = lan.preset_request.await_args
        assert args[0] == "pulse"
        assert kwargs.get("toy_id") == "real1"
        assert kwargs.get("wait_for_completion") is False

    asyncio.run(_run())


def test_handle_command_preset_quoted_payload():
    async def _run():
        b, lan, _pub = _make_partial_bridge()
        await b._handle_command_topic("lovensepy/t1/preset/set", b'"wave"')
        lan.preset_request.assert_awaited_once()
        assert lan.preset_request.await_args[0][0] == "wave"

    asyncio.run(_run())


def test_handle_toy_event_battery_changed_merged_payload():
    """Simulates ToyEventsClient callback after merging root toyId into data."""

    async def _run():
        b, _lan, pub = _make_partial_bridge()
        b._toys = {"toy1": {"id": "toy1", "toyType": "gush", "name": "Gush"}}
        await b._handle_toy_event("battery-changed", {"toyId": "toy1", "value": 73})
        bat_topic = None
        for topic, payload in pub:
            if topic.endswith("/battery/state"):
                bat_topic = (topic, payload)
        assert bat_topic is not None
        assert bat_topic[1] == "73"

    asyncio.run(_run())


def test_handle_command_clamps_vibrate():
    async def _run():
        b, lan, _pub = _make_partial_bridge()
        await b._handle_command_topic("lovensepy/t1/vibrate/set", b"99")
        args, kwargs = lan.function_request.await_args
        assert args[0]["Vibrate"] == 20

    asyncio.run(_run())


def test_handle_command_keeps_other_vector_levels():
    async def _run():
        b, lan, _pub = _make_partial_bridge()
        b._toys = {
            # Edge/Diamo-style dual vibrate (dolce falls back to ["Vibrate"] only).
            "t1": {"id": "real1", "name": "Test", "toyType": "edge"},
        }
        b._feature_levels["t1"] = {"Vibrate1": 9, "Vibrate2": 4}
        await b._handle_command_topic("lovensepy/t1/vibrate1/set", b"11")
        args, _kwargs = lan.function_request.await_args
        assert args[0] == {"Vibrate1": 11, "Vibrate2": 4}

    asyncio.run(_run())


def test_handle_command_marks_toy_offline_when_ble_not_connected():
    async def _run():
        b, lan, pub = _make_partial_bridge()
        lan.function_request.side_effect = LovenseBLEError("Not connected")
        await b._handle_command_topic("lovensepy/t1/vibrate/set", b"5")
        assert ("lovensepy/t1/device_availability", "offline") in pub
        assert b._toys["t1"]["status"] == "0"

    asyncio.run(_run())


def test_unknown_toy_command_publishes_offline_availability():
    async def _run():
        b, _lan, pub = _make_partial_bridge()
        await b._handle_command_topic("lovensepy/ghost123/vibrate/set", b"5")
        assert ("lovensepy/ghost123/device_availability", "offline") in pub

    asyncio.run(_run())


def test_unknown_toy_command_clears_stale_discovery_after_inventory_ready():
    async def _run():
        b, _lan, pub = _make_partial_bridge()
        b._inventory_ready = True
        await b._handle_command_topic("lovensepy/ghost123/vibrate/set", b"5")
        assert ("lovensepy/ghost123/device_availability", "offline") in pub
        assert any(
            t.startswith("homeassistant/") and "lovensepy_ghost123_" in t and p == ""
            for t, p in pub
        )

    asyncio.run(_run())


def test_refresh_keeps_toy_cache_when_get_toys_snapshot_empty():
    """Empty GetToys must not drop HA command routing (retained discovery topics)."""

    async def _run():
        b = HAMqttBridge("127.0.0.1", lan_ip="127.0.0.1", use_toy_events=False)
        b._topic_prefix = "lovensepy"
        b._toys = {"t1": {"id": "real1", "toyType": "lush", "name": "X", "status": "1"}}

        class _Mqtt:
            def __init__(self) -> None:
                self.published: list[tuple[str, str]] = []

            def publish(
                self,
                topic: str,
                payload: str | None = None,
                qos: int = 0,
                retain: bool = False,
            ) -> None:
                self.published.append((topic, str(payload) if payload is not None else ""))

        mqtt = _Mqtt()
        b._mqtt = mqtt
        ctrl = AsyncMock()
        ctrl.get_toys = AsyncMock(
            return_value=GetToysResponse.model_validate({"data": {"toys": []}}),
        )
        b._control = ctrl
        await b._refresh_toys_and_discovery()
        assert "t1" in b._toys
        assert b._toys["t1"]["status"] == "0"
        assert any(
            t == "lovensepy/t1/device_availability" and p == "offline" for t, p in mqtt.published
        )

    asyncio.run(_run())
