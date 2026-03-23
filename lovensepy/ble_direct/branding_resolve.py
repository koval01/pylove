"""Resolve BLE marketing ``nickName`` (ToyConfig flat map + firmware rules + UART fallback)."""

from __future__ import annotations

from typing import Literal

from ._ble_marketing_firmware import marketing_show_name_for_firmware
from ._ble_marketing_map import ble_marketing_name_overrides

BleBrandingSource = Literal[
    "toy_config_firmware",
    "toy_config_flat_map",
    "uart_detail_fallback",
    "advertised_only",
]


def resolve_ble_branding_nickname(
    *,
    advertised_name: str | None,
    toy_type_slug: str | None,
    model_letter: str | None,
    firmware: str | None,
) -> tuple[str, BleBrandingSource]:
    """Return display name and which rule produced it (for APIs / debugging).

    Matches :func:`lovensepy.ble_direct.hub._display_name_from_entry` logic.
    """
    raw = (advertised_name or "").strip() or None
    base = raw if raw else "Lovense Toy"
    if base.upper().startswith("LVS-"):
        base = base[4:].strip() or base

    if toy_type_slug and model_letter:
        fw_name = marketing_show_name_for_firmware(toy_type_slug, model_letter, firmware)
        if fw_name is not None:
            return fw_name, "toy_config_firmware"
        key = (toy_type_slug.lower(), model_letter.strip().upper())
        mapped = ble_marketing_name_overrides().get(key)
        if mapped:
            return mapped, "toy_config_flat_map"

    details: list[str] = []
    if toy_type_slug:
        details.append(f"series={toy_type_slug.lower()}")
    if model_letter:
        details.append(f"model={model_letter.strip().upper()}")
    if firmware:
        details.append(f"fw={firmware}")
    if details:
        return f"{base} ({', '.join(details)})", "uart_detail_fallback"
    return base, "advertised_only"


__all__ = ["BleBrandingSource", "resolve_ble_branding_nickname"]
