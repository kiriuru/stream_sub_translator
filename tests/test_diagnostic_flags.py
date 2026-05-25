"""Regression coverage for the opt-in deep-diagnostics env-var gating.

These flags control whether ``logs/api-trace.jsonl``, ``logs/pipeline-trace.jsonl``,
``logs/ui-trace.jsonl``, ``logs/startup-journey.jsonl`` are created and whether
extra ``runtime_lifecycle.*`` rows are appended to ``logs/runtime-events.log``.
The 0.4.2 baseline keeps these *off* by default to match the 0.4.1 release
surface (see ``docs/ETALON_RUNTIME_VERIFICATION.md`` §3.1).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core import diagnostic_flags  # noqa: E402
from backend.core.api_trace_log import ApiTraceLog, api_trace  # noqa: E402
from backend.core.pipeline_trace_log import (  # noqa: E402
    PipelineTraceLog,
    pipeline_trace_mapping,
)
import backend.core.pipeline_trace_log as pipeline_trace_module  # noqa: E402
import backend.core.runtime_lifecycle_trace as runtime_lifecycle_trace_module  # noqa: E402
from backend.core.runtime_lifecycle_trace import runtime_trace  # noqa: E402
from backend.core.startup_journey_log import (  # noqa: E402
    StartupJourneyLog,
    journey_log_mapping,
)
from backend.core.ui_trace_log import UiTraceLog, ui_trace_mapping  # noqa: E402


_DEEP_ENV_VARS = (
    "SST_DEEP_DIAGNOSTICS",
    "SST_TRACE_API",
    "SST_TRACE_PIPELINE",
    "SST_TRACE_UI",
    "SST_TRACE_STARTUP_JOURNEY",
    "SST_TRACE_RUNTIME_LIFECYCLE",
)


def _clear_env() -> dict[str, str]:
    saved: dict[str, str] = {}
    for name in _DEEP_ENV_VARS:
        if name in os.environ:
            saved[name] = os.environ.pop(name)
    return saved


def _restore_env(saved: dict[str, str]) -> None:
    for name in _DEEP_ENV_VARS:
        os.environ.pop(name, None)
    os.environ.update(saved)


class DiagnosticFlagsTests(unittest.TestCase):
    def test_all_flags_off_by_default(self) -> None:
        saved = _clear_env()
        try:
            self.assertFalse(diagnostic_flags.is_deep_diagnostics_enabled())
            self.assertFalse(diagnostic_flags.is_api_trace_enabled())
            self.assertFalse(diagnostic_flags.is_pipeline_trace_enabled())
            self.assertFalse(diagnostic_flags.is_ui_trace_enabled())
            self.assertFalse(diagnostic_flags.is_startup_journey_enabled())
            self.assertFalse(diagnostic_flags.is_runtime_lifecycle_trace_enabled())
        finally:
            _restore_env(saved)

    def test_master_switch_enables_every_subflag(self) -> None:
        saved = _clear_env()
        os.environ["SST_DEEP_DIAGNOSTICS"] = "1"
        try:
            self.assertTrue(diagnostic_flags.is_deep_diagnostics_enabled())
            self.assertTrue(diagnostic_flags.is_api_trace_enabled())
            self.assertTrue(diagnostic_flags.is_pipeline_trace_enabled())
            self.assertTrue(diagnostic_flags.is_ui_trace_enabled())
            self.assertTrue(diagnostic_flags.is_startup_journey_enabled())
            self.assertTrue(diagnostic_flags.is_runtime_lifecycle_trace_enabled())
        finally:
            _restore_env(saved)

    def test_individual_flag_enables_only_its_channel(self) -> None:
        saved = _clear_env()
        os.environ["SST_TRACE_UI"] = "1"
        try:
            self.assertFalse(diagnostic_flags.is_deep_diagnostics_enabled())
            self.assertFalse(diagnostic_flags.is_api_trace_enabled())
            self.assertFalse(diagnostic_flags.is_pipeline_trace_enabled())
            self.assertTrue(diagnostic_flags.is_ui_trace_enabled())
            self.assertFalse(diagnostic_flags.is_startup_journey_enabled())
            self.assertFalse(diagnostic_flags.is_runtime_lifecycle_trace_enabled())
        finally:
            _restore_env(saved)

    def test_accepts_common_truthy_tokens(self) -> None:
        saved = _clear_env()
        try:
            for token in ("1", "true", "yes", "ON", "True", "Yes"):
                os.environ["SST_TRACE_API"] = token
                self.assertTrue(
                    diagnostic_flags.is_api_trace_enabled(),
                    msg=f"token {token!r} should be truthy",
                )
            for token in ("0", "false", "no", "off", "", "anything-else"):
                os.environ["SST_TRACE_API"] = token
                self.assertFalse(
                    diagnostic_flags.is_api_trace_enabled(),
                    msg=f"token {token!r} should be falsy",
                )
        finally:
            _restore_env(saved)


class TraceCallsitesNoopWithoutConfigureTests(unittest.TestCase):
    """The 0.4.1 baseline behaviour: trace functions silently skip work
    when no one has called the corresponding ``configure_*`` factory.

    This is the contract that ``app_bootstrap.initialize_app_state`` relies
    on: with the env-flags off it does not configure the singletons, and the
    library helpers below must remain safe to call from arbitrary callsites.
    """

    def setUp(self) -> None:
        self._saved_api = ApiTraceLog._instance
        self._saved_ui = UiTraceLog._instance
        self._saved_journey = StartupJourneyLog._instance
        self._saved_pipeline = pipeline_trace_module._instance
        ApiTraceLog._instance = None
        UiTraceLog._instance = None
        StartupJourneyLog._instance = None
        pipeline_trace_module._instance = None

    def tearDown(self) -> None:
        ApiTraceLog._instance = self._saved_api
        UiTraceLog._instance = self._saved_ui
        StartupJourneyLog._instance = self._saved_journey
        pipeline_trace_module._instance = self._saved_pipeline

    def test_helpers_do_not_raise_or_persist_records(self) -> None:
        # All five helpers must accept payloads silently and write nothing —
        # no file IO, no exceptions, no globals mutated.
        api_trace("http", "request_complete", path="/api/health", status_code=200)
        ui_trace_mapping("dashboard", "render", "ok", {"frame": 1})
        pipeline_trace_mapping("backend", "asr", "partial", {"text": "hi"})
        journey_log_mapping("backend", "ready", {"detail": "noop"})
        self.assertIsNone(ApiTraceLog.get())
        self.assertIsNone(UiTraceLog.get())
        self.assertIsNone(StartupJourneyLog.get())
        self.assertIsNone(PipelineTraceLog.get())


class RuntimeTraceGateTests(unittest.TestCase):
    def test_runtime_trace_is_noop_without_flag(self) -> None:
        captured: list[tuple[str, str]] = []

        class _StubLogger:
            def log(self, channel, event, **_kwargs):  # noqa: ANN001
                captured.append((channel, event))

        with patch.object(
            runtime_lifecycle_trace_module,
            "is_runtime_lifecycle_trace_enabled",
            return_value=False,
        ):
            runtime_trace(_StubLogger(), "backend_startup", source="app_bootstrap")
        self.assertEqual(captured, [])

    def test_runtime_trace_writes_when_flag_on(self) -> None:
        captured: list[tuple[str, str]] = []

        class _StubLogger:
            def log(self, channel, event, **_kwargs):  # noqa: ANN001
                captured.append((channel, event))

        with patch.object(
            runtime_lifecycle_trace_module,
            "is_runtime_lifecycle_trace_enabled",
            return_value=True,
        ):
            runtime_trace(_StubLogger(), "backend_startup", source="app_bootstrap")
        self.assertEqual(captured, [("runtime_lifecycle", "backend_startup")])


if __name__ == "__main__":
    unittest.main()
