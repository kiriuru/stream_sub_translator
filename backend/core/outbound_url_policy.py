from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from fastapi import HTTPException

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
    }
)


def _env_flag(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def is_elevated_network_exposure(*, bind_host: str | None = None, allow_lan: bool | None = None) -> bool:
    """True when the API may be reachable beyond loopback (LAN bind)."""
    if allow_lan is None:
        allow_lan = _env_flag("SST_ALLOW_LAN")
    if allow_lan:
        return True
    host = (bind_host or "").strip().lower()
    return host in {"0.0.0.0", "::"}


def _normalize_hostname(host: str) -> str:
    value = (host or "").strip().lower()
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1]
    return value


def is_restricted_outbound_host(host: str) -> bool:
    """Return True if the host must not be used for server-side OpenAI helper fetches."""
    normalized = _normalize_hostname(host)
    if not normalized:
        return True
    if normalized in _BLOCKED_HOSTNAMES:
        return True
    if normalized.endswith(".localhost") or normalized.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return bool(
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def assert_openai_base_url_allowed(
    base_url: str,
    *,
    bind_host: str | None = None,
    allow_lan: bool | None = None,
) -> str:
    """
    When LAN bind is active, reject base_url targets that reach private or loopback space.
    Localhost bind keeps private URLs allowed (local OpenAI-compatible servers).
    """
    if not is_elevated_network_exposure(bind_host=bind_host, allow_lan=allow_lan):
        return base_url
    parsed = urlparse(base_url)
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="base_url hostname is missing or invalid")
    if is_restricted_outbound_host(hostname):
        raise HTTPException(
            status_code=400,
            detail=(
                "base_url targets a private, loopback, or link-local address; "
                "not allowed when LAN bind is enabled"
            ),
        )
    return base_url
