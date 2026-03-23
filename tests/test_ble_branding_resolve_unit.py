"""Unit tests for :func:`resolve_ble_branding_nickname`."""

from __future__ import annotations

from lovensepy.ble_direct.branding_resolve import resolve_ble_branding_nickname


def test_resolve_matches_hub_lush_example() -> None:
    nick, src = resolve_ble_branding_nickname(
        advertised_name="LVS-Lush",
        toy_type_slug="lush",
        model_letter="S",
        firmware="100",
    )
    assert nick == "Lush 2"
    assert src == "toy_config_firmware"


def test_resolve_uart_detail_when_no_map() -> None:
    nick, src = resolve_ble_branding_nickname(
        advertised_name="LVS-Gush",
        toy_type_slug="gush",
        model_letter="QQ",
        firmware="62",
    )
    assert nick == "Gush (series=gush, model=QQ, fw=62)"
    assert src == "uart_detail_fallback"
