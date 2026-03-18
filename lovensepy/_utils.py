"""
Shared utilities: URL building, etc.
"""

__all__ = ["ip_to_domain"]


def ip_to_domain(ip: str) -> str:
    """Convert 192.168.1.1 to 192-168-1-1.lovense.club for Lovense HTTPS/WSS.

    Expects a dotted-decimal IPv4 address. Empty or invalid input raises ValueError.
    """
    if not ip or not ip.strip():
        raise ValueError("ip must not be empty")
    parts = ip.strip().split(".")
    if len(parts) != 4:
        raise ValueError("ip must be dotted-decimal IPv4 (e.g. 192.168.1.1)")
    for part in parts:
        try:
            n = int(part)
            if n < 0 or n > 255:
                raise ValueError("ip octets must be 0-255")
        except ValueError as exc:
            raise ValueError("ip must be dotted-decimal IPv4 (e.g. 192.168.1.1)") from exc
    return ip.strip().replace(".", "-") + ".lovense.club"
