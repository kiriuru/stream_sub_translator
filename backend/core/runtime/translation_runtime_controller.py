from __future__ import annotations

from typing import Any, Awaitable, Callable

from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.translation_dispatcher import TranslationDispatcher
from backend.core.translation_engine import TranslationEngine
from backend.models import TranslationEvent
from backend.core.runtime.translation_runtime_coordinator import summarize_translation_diagnostics


class TranslationRuntimeController:
    """
    Stage 3 controller: owns TranslationEngine + TranslationDispatcher lifecycle + dispatcher metrics snapshot.

    It keeps the existing behavior:
    - submit_final() feeds the dispatcher
    - dispatcher publishes per-line + completion TranslationEvent(s)
    - events are routed into SubtitleRouter, and optionally broadcasted when presentation-relevant
    - runtime status is broadcast after translations update
    """

    name = "translation"

    def __init__(
        self,
        *,
        translation_engine: TranslationEngine,
        config_getter: Callable[[], dict],
        is_sequence_relevant_for_translation: Callable[[int], bool],
        handle_translation_event: Callable[[TranslationEvent], Awaitable[None]],
        metrics_callback: Callable[[dict], None],
        structured_logger: StructuredRuntimeLogger | None = None,
    ) -> None:
        self._engine = translation_engine
        self._config_getter = config_getter
        self._is_sequence_relevant_for_translation = is_sequence_relevant_for_translation
        self._handle_translation_event = handle_translation_event
        self._metrics_callback = metrics_callback
        self._structured_logger = structured_logger
        self._dispatcher_snapshot: dict[str, Any] = {}
        self._dispatcher: TranslationDispatcher | None = None

    def _translation_config(self) -> dict[str, Any]:
        config = self._config_getter()
        translation = config.get("translation", {}) if isinstance(config, dict) else {}
        return translation if isinstance(translation, dict) else {}

    def _build_dispatcher(self) -> TranslationDispatcher:
        return TranslationDispatcher(
            self._engine,
            self._config_getter,
            self._handle_translation_event,
            self._is_sequence_relevant_for_translation,
            self._on_metrics,
            structured_logger=self._structured_logger,
        )

    def _on_metrics(self, metrics: dict) -> None:
        if isinstance(metrics, dict):
            self._dispatcher_snapshot = dict(metrics)
        self._metrics_callback(metrics)

    async def start(self) -> None:
        # Recreate dispatcher per runtime start to avoid stale state across stop/start cycles.
        self._dispatcher_snapshot = {}
        self._dispatcher = self._build_dispatcher()
        self._engine.apply_live_settings(self._translation_config())

    async def stop(self) -> None:
        if self._dispatcher is None:
            return
        await self._dispatcher.stop()
        self._dispatcher = None

    def apply_live_settings(self) -> None:
        self._engine.apply_live_settings(self._translation_config())

    async def submit_final(self, *, sequence: int, source_text: str, source_lang: str) -> None:
        if self._dispatcher is None:
            # Be tolerant: runtime might submit before start() in some test harnesses.
            self._dispatcher = self._build_dispatcher()
        await self._dispatcher.submit_final(sequence=sequence, source_text=source_text, source_lang=source_lang)

    def diagnostics(self) -> TranslationDiagnostics:
        return summarize_translation_diagnostics(
            config_getter=self._config_getter,
            translation_engine=self._engine,
            translation_dispatcher_snapshot=self._dispatcher_snapshot,
        )

