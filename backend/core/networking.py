"""Networking helpers for proxy-aware client IP resolution."""

from __future__ import annotations

import ipaddress
from typing import Any

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_ip_text(raw: str | None) -> IPAddress | None:
    text = str(raw or "").strip().strip('"').strip("'")
    if not text:
        return None
    if text.lower().startswith("for="):
        text = text[4:].strip().strip('"').strip("'")
    if "%" in text:
        text = text.split("%", 1)[0]
    if text.startswith("[") and "]" in text:
        text = text[1:text.find("]")]
    elif text.count(":") == 1 and "." in text:
        host, port = text.rsplit(":", 1)
        if port.isdigit():
            text = host
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def trusted_proxy_ip(
    addr: IPAddress,
    *,
    trusted_proxy_networks: tuple[IPNetwork, ...],
    trust_x_forwarded_for: bool,
) -> bool:
    if trusted_proxy_networks:
        return any(addr in network for network in trusted_proxy_networks)
    return trust_x_forwarded_for


def forwarded_for_chain(header_value: str | None) -> list[IPAddress]:
    chain: list[IPAddress] = []
    for token in str(header_value or "").split(","):
        parsed = parse_ip_text(token)
        if parsed is not None:
            chain.append(parsed)
    return chain


def client_ip(
    request: Any,
    *,
    trust_x_forwarded_for: bool,
    trusted_proxy_networks: tuple[IPNetwork, ...],
) -> str:
    if request is None:
        return "unknown"

    peer_host = str(request.client.host) if request.client and request.client.host else ""
    peer_ip = parse_ip_text(peer_host)
    forwarded_chain = forwarded_for_chain(request.headers.get("x-forwarded-for"))

    if peer_ip is None:
        if forwarded_chain and trust_x_forwarded_for and not trusted_proxy_networks:
            return str(forwarded_chain[0])
        return peer_host or "unknown"

    if not forwarded_chain:
        return str(peer_ip)

    if not trusted_proxy_ip(
        peer_ip,
        trusted_proxy_networks=trusted_proxy_networks,
        trust_x_forwarded_for=trust_x_forwarded_for,
    ):
        return str(peer_ip)

    # Walk from nearest to farthest hop and return the first untrusted client hop.
    for hop in reversed(forwarded_chain):
        if trusted_proxy_ip(
            hop,
            trusted_proxy_networks=trusted_proxy_networks,
            trust_x_forwarded_for=trust_x_forwarded_for,
        ):
            continue
        return str(hop)
    return str(forwarded_chain[0])
