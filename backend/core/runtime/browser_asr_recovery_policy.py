"""
L4 Recovery policy — suggested actions with ordering semantics (priority / exclusive_group / execution_phase).

The executor (FSM + transport constraints) logs `basr.policy_action_accepted` / `basr.policy_action_rejected`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from backend.core.runtime.browser_asr_trace import BrowserAsrTraceFields
from backend.core.runtime.browser_asr_trace import log_basr, new_event_id
from backend.core.structured_runtime_logger import StructuredRuntimeLogger


class PolicyActionKind(str, Enum):
    NOOP = "noop"
    RESTART = "restart"
    BACKOFF_MS = "backoff_ms"
    MARK_DEGRADED = "mark_degraded"
    SEND_CONTROL = "send_control"


@dataclass(slots=True)
class PolicySuggestedAction:
    """Single suggested recovery step; sort order = execution order."""

    execution_phase: int
    priority: int
    kind: PolicyActionKind = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)
    exclusive_group: str | None = field(default=None, compare=False)


class BrowserAsrRecoveryPolicy:
    """Minimal policy: surface degraded hints; backend does not auto-restart the browser worker."""

    def suggest(
        self,
        *,
        degraded_reason: str | None,
        last_error: str | None,
        worker_connected: bool,
    ) -> list[PolicySuggestedAction]:
        _ = (last_error, worker_connected)
        actions: list[PolicySuggestedAction] = []
        if degraded_reason:
            actions.append(
                PolicySuggestedAction(
                    execution_phase=0,
                    priority=10,
                    kind=PolicyActionKind.MARK_DEGRADED,
                    payload={"degraded_reason": degraded_reason},
                    exclusive_group="health",
                )
            )
        actions.append(
            PolicySuggestedAction(
                execution_phase=1,
                priority=0,
                kind=PolicyActionKind.NOOP,
                payload={},
                exclusive_group=None,
            )
        )
        return sorted(actions, key=lambda a: (a.execution_phase, a.priority, a.kind.value))


class BrowserAsrPolicyExecutor:
    def __init__(
        self,
        *,
        structured_logger: StructuredRuntimeLogger | None,
        can_send_control: Callable[[], bool],
    ) -> None:
        self._structured_logger = structured_logger
        self._can_send_control = can_send_control

    def execute(
        self,
        *,
        actions: list[PolicySuggestedAction],
        trace: BrowserAsrTraceFields | None,
    ) -> dict[str, int]:
        """Returns counts accepted/rejected."""

        accepted = 0
        rejected = 0
        for action in sorted(actions, key=lambda a: (a.execution_phase, a.priority, a.kind.value)):
            outcome, reason, reject_code = self._try_one(action)
            self._log_outcome(action, outcome, reason, reject_code, trace)
            if outcome == "accepted":
                accepted += 1
            else:
                rejected += 1
        return {"policy_accepted": accepted, "policy_rejected": rejected}

    def _try_one(self, action: PolicySuggestedAction) -> tuple[str, str | None, str | None]:
        if action.kind in (PolicyActionKind.NOOP, PolicyActionKind.MARK_DEGRADED, PolicyActionKind.BACKOFF_MS):
            return "accepted", None, None
        if action.kind == PolicyActionKind.SEND_CONTROL:
            if self._can_send_control():
                return "accepted", None, None
            return "rejected", "no active websocket transport", "transport_unavailable"
        if action.kind == PolicyActionKind.RESTART:
            return "rejected", "restart not executed server-side (browser worker owns lifecycle)", "restart_not_implemented"
        return "rejected", "unknown action", "unknown"

    def _log_outcome(
        self,
        action: PolicySuggestedAction,
        outcome: str,
        reason: str | None,
        reject_code: str | None,
        parent_trace: BrowserAsrTraceFields | None,
    ) -> None:
        tid = new_event_id()
        log_trace = BrowserAsrTraceFields(
            event_id=tid,
            causal_parent_id=parent_trace.event_id if parent_trace else None,
            generation_id=parent_trace.generation_id if parent_trace else None,
            session_id=parent_trace.session_id if parent_trace else None,
            transport_id=parent_trace.transport_id if parent_trace else None,
            mono_ingress_at=parent_trace.mono_ingress_at if parent_trace else None,
        )
        payload = {
            "suggested_kind": action.kind.value,
            "execution_phase": action.execution_phase,
            "priority": action.priority,
            "exclusive_group": action.exclusive_group,
            "outcome": outcome,
            "reject_code": reject_code,
            "reason": reason,
        }
        log_basr(
            self._structured_logger,
            "browser_recognition",
            "policy_action_result",
            trace=log_trace,
            payload=payload,
            source="browser_asr_recovery_policy",
        )


__all__ = [
    "BrowserAsrPolicyExecutor",
    "BrowserAsrRecoveryPolicy",
    "PolicyActionKind",
    "PolicySuggestedAction",
]
