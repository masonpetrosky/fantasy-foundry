"""Runtime auth/proxy parsing helpers for the backend entrypoint."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re

from fastapi import Request

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def load_trusted_proxy_networks(raw: str, *, logger: logging.Logger | None = None) -> tuple[IPNetwork, ...]:
    """Parse comma-separated CIDR/IP tokens into normalized proxy networks."""

    networks: list[IPNetwork] = []
    for token in raw.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            if "/" in candidate:
                network = ipaddress.ip_network(candidate, strict=False)
            else:
                addr: IPAddress = ipaddress.ip_address(candidate)
                suffix = "32" if isinstance(addr, ipaddress.IPv4Address) else "128"
                network = ipaddress.ip_network(f"{addr}/{suffix}", strict=False)
        except ValueError:
            if logger is not None:
                logger.warning("ignoring invalid FF_TRUSTED_PROXY_CIDRS token: %s", candidate)
            continue
        networks.append(network)
    return tuple(networks)


def parse_calculate_api_key_identities(raw: str) -> dict[str, str]:
    """Build stable logging identities for configured API keys."""

    identities: dict[str, str] = {}
    for token in re.split(r"[\s,]+", raw.strip()):
        api_key = token.strip()
        if not api_key:
            continue
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
        identities[api_key] = f"api_key:{digest}"
    return identities


def extract_calculate_api_key(request: Request | None) -> str | None:
    """Extract calculator API key from `x-api-key` or Bearer token headers."""

    if request is None:
        return None
    direct = str(request.headers.get("x-api-key") or "").strip()
    if direct:
        return direct
    auth_header = str(request.headers.get("authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        return token or None
    return None
