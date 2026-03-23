"""Unit tests for ToyConfig-derived firmware marketing names (BLE)."""

from __future__ import annotations

from lovensepy.ble_direct._ble_marketing_firmware import (
    marketing_show_name_for_firmware,
    parse_firmware_int,
)


def test_parse_firmware_int() -> None:
    assert parse_firmware_int("240") == 240
    assert parse_firmware_int("v62") == 62
    assert parse_firmware_int(None) is None
    assert parse_firmware_int("") is None


def test_lush_generations_packaged_rules() -> None:
    assert marketing_show_name_for_firmware("lush", "S", "10") == "Lush"
    assert marketing_show_name_for_firmware("lush", "S", "100") == "Lush 2"
    assert marketing_show_name_for_firmware("lush", "S", "145") == "Lush 3"
    assert marketing_show_name_for_firmware("lush", "S", "480") == "Lush 4"


def test_gush_firmware_rules() -> None:
    assert marketing_show_name_for_firmware("gush", "ED", "1") == "Gush"
    assert marketing_show_name_for_firmware("gush", "EZ", "65") == "Gush 2"


def test_unknown_letter_returns_none() -> None:
    assert marketing_show_name_for_firmware("lush", "P", "100") is None
