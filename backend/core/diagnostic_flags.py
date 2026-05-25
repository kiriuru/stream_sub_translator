"""Environment-driven gating for opt-in deep diagnostics traces.

Background:
    Pipeline/API/UI/runtime-lifecycle/startup-journey JSONL traces were introduced
    to triage broken desktop installs (see ``docs/ETALON_RUNTIME_VERIFICATION.md``).
    They are useful for forensic comparisons against the etalon reference but
    they are noisy in steady-state operation and were not part of the 0.4.1
    GitHub release surface.

Default behaviour (no env vars set):
    ``api-trace.jsonl``, ``pipeline-trace.jsonl``, ``ui-trace.jsonl``,
    ``startup-journey.jsonl`` are **not** created; the corresponding
    ``runtime_lifecycle.*`` records are **not** appended to
    ``runtime-events.log``. Backbone files (``runtime-events.log``,
    ``session-latest.jsonl``, ``backend.log``) continue to be written
    exactly as in 0.4.1.

Opt-in:
    Set ``SST_DEEP_DIAGNOSTICS=1`` to enable *all* deep traces, or set
    individual flags below when narrowing scope:

    * ``SST_TRACE_API`` ......... ``logs/api-trace.jsonl``
    * ``SST_TRACE_PIPELINE`` .... ``logs/pipeline-trace.jsonl``
    * ``SST_TRACE_UI`` .......... ``logs/ui-trace.jsonl``
    * ``SST_TRACE_STARTUP_JOURNEY``  ``logs/startup-journey.jsonl``
    * ``SST_TRACE_RUNTIME_LIFECYCLE``  extra ``runtime_lifecycle.*`` rows
      in ``logs/runtime-events.log``
    * ``SST_TRACE_RUNTIME_EVENTS_VERBOSE``  ``DBG`` and ``VRB`` events in
      ``logs/runtime-events.log`` (``basr.*`` FSM/recovery, browser heart-
      beats, translation queue depth, …). Off by default — only ``INF``,
      ``WRN``, ``ERR``, ``CRT`` events reach disk so user installs stay
      close to the 0.4.1 volume footprint.

A flag is considered "on" when its value is one of
``{"1", "true", "yes", "on"}`` (case-insensitive).
"""

from __future__ import annotations

import os
from typing import Iterable

_MASTER_ENV = "SST_DEEP_DIAGNOSTICS"
_TRUE_TOKENS: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def _is_env_truthy(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() in _TRUE_TOKENS


def _any_truthy(names: Iterable[str]) -> bool:
    return any(_is_env_truthy(name) for name in names)


def is_deep_diagnostics_enabled() -> bool:
    """Master switch — when set, *every* deep trace flag is implicitly on."""

    return _is_env_truthy(_MASTER_ENV)


def is_api_trace_enabled() -> bool:
    return _any_truthy((_MASTER_ENV, "SST_TRACE_API"))


def is_pipeline_trace_enabled() -> bool:
    return _any_truthy((_MASTER_ENV, "SST_TRACE_PIPELINE"))


def is_ui_trace_enabled() -> bool:
    return _any_truthy((_MASTER_ENV, "SST_TRACE_UI"))


def is_startup_journey_enabled() -> bool:
    return _any_truthy((_MASTER_ENV, "SST_TRACE_STARTUP_JOURNEY"))


def is_runtime_lifecycle_trace_enabled() -> bool:
    return _any_truthy((_MASTER_ENV, "SST_TRACE_RUNTIME_LIFECYCLE"))


def is_runtime_events_verbose_enabled() -> bool:
    """
    Gate the high-frequency DBG/VRB stream written to ``logs/runtime-events.log``.

    Off by default (matches 0.4.1 sizing on user installs). When off, the
    structured runtime logger writes only ``INF``/``WRN``/``ERR``/``CRT``
    events — high-frequency observability noise (``basr.*`` FSM/recovery
    transitions, ``browser_worker_status`` heartbeats, translation queue
    depth ticks, …) is suppressed.

    Turn on for triage via ``SST_DEEP_DIAGNOSTICS=1`` or the per-channel
    ``SST_TRACE_RUNTIME_EVENTS_VERBOSE=1``.
    """
    return _any_truthy((_MASTER_ENV, "SST_TRACE_RUNTIME_EVENTS_VERBOSE"))


__all__ = (
    "is_deep_diagnostics_enabled",
    "is_api_trace_enabled",
    "is_pipeline_trace_enabled",
    "is_ui_trace_enabled",
    "is_startup_journey_enabled",
    "is_runtime_lifecycle_trace_enabled",
    "is_runtime_events_verbose_enabled",
)
