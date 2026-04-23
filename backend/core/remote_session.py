from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.models import RemotePairingStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_TTL_SECONDS = 12 * 60 * 60
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass
class _PairSession:
    session_id: str
    pair_code: str
    ttl_seconds: int
    expires_at_utc: datetime
    controller_last_seen_utc: datetime | None = None
    worker_last_seen_utc: datetime | None = None


class RemoteSessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pair_session: _PairSession | None = None

    def preload(self, *, session_id: str | None, pair_code: str | None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        normalized_session = str(session_id or "").strip()
        normalized_code = str(pair_code or "").strip()
        if not normalized_session or not normalized_code:
            return
        resolved_ttl = self._clamp_ttl(ttl_seconds)
        expires_at = _utc_now() + timedelta(seconds=resolved_ttl)
        with self._lock:
            self._pair_session = _PairSession(
                session_id=normalized_session,
                pair_code=normalized_code,
                ttl_seconds=resolved_ttl,
                expires_at_utc=expires_at,
            )

    def create_pairing(self, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> tuple[str, str, str, RemotePairingStatus]:
        ttl = self._clamp_ttl(ttl_seconds)
        now = _utc_now()
        session_id = f"sst-{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"
        pair_code = "".join(secrets.choice("0123456789") for _ in range(6))
        pair_session = _PairSession(
            session_id=session_id,
            pair_code=pair_code,
            ttl_seconds=ttl,
            expires_at_utc=now + timedelta(seconds=ttl),
            controller_last_seen_utc=now,
        )
        with self._lock:
            self._pair_session = pair_session
        return session_id, pair_code, pair_session.expires_at_utc.isoformat(), self.snapshot()

    def verify_pairing(self, *, session_id: str, pair_code: str) -> tuple[bool, str | None]:
        with self._lock:
            pair_session = self._pair_session
            if pair_session is None:
                return False, "Pairing session is not initialized."
            if _utc_now() >= pair_session.expires_at_utc:
                return False, "Pairing session has expired."
            if str(session_id).strip() != pair_session.session_id:
                return False, "Session id does not match."
            if str(pair_code).strip() != pair_session.pair_code:
                return False, "Pair code does not match."
        return True, None

    def heartbeat(self, *, session_id: str, role: str) -> tuple[bool, str | None, RemotePairingStatus]:
        role_value = str(role or "").strip().lower()
        with self._lock:
            pair_session = self._pair_session
            if pair_session is None:
                return False, "Pairing session is not initialized.", self._snapshot_unlocked()
            if _utc_now() >= pair_session.expires_at_utc:
                return False, "Pairing session has expired.", self._snapshot_unlocked()
            if str(session_id).strip() != pair_session.session_id:
                return False, "Session id does not match.", self._snapshot_unlocked()
            if role_value == "controller":
                pair_session.controller_last_seen_utc = _utc_now()
            elif role_value == "worker":
                pair_session.worker_last_seen_utc = _utc_now()
            else:
                return False, "Unsupported heartbeat role.", self._snapshot_unlocked()
            # Active sessions should stay alive while peers are sending heartbeats.
            pair_session.expires_at_utc = _utc_now() + timedelta(seconds=pair_session.ttl_seconds)
            return True, None, self._snapshot_unlocked()

    def snapshot(self) -> RemotePairingStatus:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> RemotePairingStatus:
        pair_session = self._pair_session
        if pair_session is None:
            return RemotePairingStatus()
        now = _utc_now()
        is_active = now < pair_session.expires_at_utc
        controller_online = False
        worker_online = False
        if pair_session.controller_last_seen_utc is not None:
            controller_online = (now - pair_session.controller_last_seen_utc).total_seconds() <= 15
        if pair_session.worker_last_seen_utc is not None:
            worker_online = (now - pair_session.worker_last_seen_utc).total_seconds() <= 15
        return RemotePairingStatus(
            session_id=pair_session.session_id,
            expires_at_utc=pair_session.expires_at_utc.isoformat(),
            is_active=is_active,
            controller_last_seen_utc=(
                pair_session.controller_last_seen_utc.isoformat()
                if pair_session.controller_last_seen_utc is not None
                else None
            ),
            worker_last_seen_utc=(
                pair_session.worker_last_seen_utc.isoformat()
                if pair_session.worker_last_seen_utc is not None
                else None
            ),
            controller_online=controller_online,
            worker_online=worker_online,
        )

    @staticmethod
    def _clamp_ttl(ttl_seconds: int) -> int:
        try:
            parsed = int(ttl_seconds)
        except (TypeError, ValueError):
            parsed = DEFAULT_TTL_SECONDS
        return max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, parsed))
