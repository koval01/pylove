"""State publish deduplication for MQTT bridge."""

from __future__ import annotations

__all__ = ["StateDeduper"]


class StateDeduper:
    """Avoid republishing identical payloads on state topics."""

    __slots__ = ("_last",)

    def __init__(self) -> None:
        self._last: dict[str, str] = {}

    def should_publish(self, key: str, payload: str) -> bool:
        if self._last.get(key) == payload:
            return False
        self._last[key] = payload
        return True

    def forget(self, key: str) -> None:
        self._last.pop(key, None)

    def clear(self) -> None:
        self._last.clear()
