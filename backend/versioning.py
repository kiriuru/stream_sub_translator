from __future__ import annotations

import re
from typing import Any

PROJECT_VERSION = "0.3.2"
RELEASE_TRACK = "stable"
DEFAULT_UPDATE_PROVIDER = "github_releases"
DEFAULT_RELEASE_CHANNEL = "stable"

_SEMVER_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:\.(?P<build>\d+))?(?:[-+].*)?$"
)


def _parse_semver(value: str) -> tuple[int, int, int, int] | None:
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
        int(match.group("build") or 0),
    )


def _is_remote_version_newer(local_version: str, remote_version: str) -> bool:
    local_semver = _parse_semver(local_version)
    remote_semver = _parse_semver(remote_version)
    if local_semver is None or remote_semver is None:
        return False
    return remote_semver > local_semver


def _format_semver(semver: tuple[int, int, int, int]) -> str:
    major, minor, patch, build = semver
    if build:
        return f"{major}.{minor}.{patch}.{build}"
    return f"{major}.{minor}.{patch}"


def extract_latest_github_release_version(
    releases_payload: Any,
    *,
    release_channel: str = "stable",
) -> tuple[str | None, str]:
    """
    Given GitHub Releases API payload, determine the latest version tag.

    release_channel:
      - stable: ignore prereleases
      - prerelease: allow prereleases
    """
    channel = str(release_channel or "stable").strip().lower()
    if channel not in {"stable", "prerelease"}:
        channel = "stable"

    if not isinstance(releases_payload, list):
        return None, "GitHub releases payload was not a list."

    best: tuple[int, int, int, int] | None = None
    best_raw: str | None = None
    scanned = 0
    for item in releases_payload:
        if not isinstance(item, dict):
            continue
        scanned += 1
        if bool(item.get("draft", False)):
            continue
        is_prerelease = bool(item.get("prerelease", False))
        if channel == "stable" and is_prerelease:
            continue
        tag = str(item.get("tag_name", "") or "").strip()
        if not tag:
            tag = str(item.get("name", "") or "").strip()
        if not tag:
            continue
        semver = _parse_semver(tag)
        if semver is None:
            continue
        if best is None or semver > best:
            best = semver
            best_raw = tag

    if best is None:
        return None, f"No usable release versions found (scanned {scanned} releases)."
    formatted = _format_semver(best)
    raw = str(best_raw or "").lstrip("v").strip()
    if raw and raw != formatted:
        return formatted, f"Latest release tag: {raw} (normalized to {formatted})."
    return formatted, f"Latest release version: {formatted}."


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
        "Update check is available via /api/updates/check."
        if enabled and check_supported
        else "Update checks are disabled or not configured."
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
