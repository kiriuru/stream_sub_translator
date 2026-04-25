from __future__ import annotations

import re
from typing import Any

PROJECT_VERSION = "2.8.3"
RELEASE_TRACK = "stable"
DEFAULT_UPDATE_PROVIDER = "github_releases"
DEFAULT_RELEASE_CHANNEL = "stable"

_SEMVER_RE = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+].*)?$")


def _parse_semver(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _SEMVER_RE.match(text)
    if not match:
        return None
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def _is_remote_version_newer(local_version: str, remote_version: str) -> bool:
    local_semver = _parse_semver(local_version)
    remote_semver = _parse_semver(remote_version)
    if local_semver is None or remote_semver is None:
        return False
    return remote_semver > local_semver


def build_version_info_payload(config: dict[str, Any] | None) -> dict[str, Any]:
    payload = config if isinstance(config, dict) else {}
    raw_updates = payload.get("updates", {})
    updates = raw_updates if isinstance(raw_updates, dict) else {}

    provider = str(updates.get("provider", DEFAULT_UPDATE_PROVIDER) or DEFAULT_UPDATE_PROVIDER).strip().lower()
    if provider not in {"github_releases"}:
        provider = DEFAULT_UPDATE_PROVIDER

    github_repo = str(updates.get("github_repo", "") or "").strip()
    release_channel = str(updates.get("release_channel", DEFAULT_RELEASE_CHANNEL) or DEFAULT_RELEASE_CHANNEL).strip().lower()
    if release_channel not in {"stable", "prerelease"}:
        release_channel = DEFAULT_RELEASE_CHANNEL

    latest_known_version = str(updates.get("latest_known_version", "") or "").strip() or None
    last_checked_utc = str(updates.get("last_checked_utc", "") or "").strip() or None
    enabled = bool(updates.get("enabled", False))

    update_available = False
    if latest_known_version:
        update_available = _is_remote_version_newer(PROJECT_VERSION, latest_known_version)

    check_supported = bool(github_repo)
    message = (
        "Release sync scaffold is ready. Live GitHub polling is not enabled in this build."
    )

    return {
        "ok": True,
        "current_version": PROJECT_VERSION,
        "release_track": RELEASE_TRACK,
        "sync": {
            "provider": provider,
            "enabled": enabled,
            "github_repo": github_repo or None,
            "release_channel": release_channel,
            "latest_known_version": latest_known_version,
            "last_checked_utc": last_checked_utc,
            "update_available": update_available,
            "check_supported": check_supported,
            "check_active": False,
            "message": message,
        },
    }
