from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import logging
import time
from typing import Any, Awaitable, Callable

from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.translation_engine import PreparedTranslationRequest, TranslationEngine
from backend.models import TranslationEvent, TranslationItem

logger = logging.getLogger(__name__)

_DEFAULT_QUEUE_MAX_SIZE = 8
_DEFAULT_TIMEOUT_MS = 10_000
_DEFAULT_MAX_CONCURRENT_JOBS = 2


@dataclass(slots=True)
class _QueuedJob:
    job_id: int
    sequence: int
    source_text: str
    source_lang: str
    submitted_at_monotonic: float


@dataclass(slots=True)
class _ActiveJob:
    job_id: int
    sequence: int
    source_lang: str
    source_text_len: int
    task: asyncio.Task


@dataclass(slots=True)
class _TargetResult:
    item: TranslationItem
    provider_latency_ms: float
    status_message: str | None
    outcome: str
    reason: str | None = None


class TranslationDispatcher:
    def __init__(
        self,
        translation_engine: TranslationEngine,
        config_getter: Callable[[], dict],
        publish_callback: Callable[[TranslationEvent], Awaitable[None]],
        is_sequence_relevant: Callable[[int], bool],
        metrics_callback: Callable[[dict], None] | None = None,
        structured_logger: StructuredRuntimeLogger | None = None,
    ) -> None:
        self._translation_engine = translation_engine
        self._config_getter = config_getter
        self._publish_callback = publish_callback
        self._is_sequence_relevant = is_sequence_relevant
        self._metrics_callback = metrics_callback
        self._structured_logger = structured_logger
        self._queue: deque[_QueuedJob] = deque()
        self._queue_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._worker_task: asyncio.Task | None = None
        self._active_jobs: dict[int, _ActiveJob] = {}
        self._next_job_id = 0
        self._stopped = False
        self._metrics: dict[str, int | float | str | None] = {
            "translation_queue_depth": 0,
            "translation_jobs_started": 0,
            "translation_jobs_cancelled": 0,
            "translation_stale_results_dropped": 0,
            "translation_queue_latency_ms": None,
            "translation_provider_latency_ms": None,
            "translation_last_runtime_reason": None,
            "translation_last_provider": None,
            "translation_last_target_lang": None,
            "translation_last_timeout_ms": None,
        }
        self._last_logged_queue_depth: int | None = None

    async def submit_final(
        self,
        *,
        sequence: int,
        source_text: str,
        source_lang: str,
    ) -> None:
        if self._stopped:
            return
        self._ensure_worker_started()
        await self.cancel_older_than(sequence)
        await self._enqueue(
            _QueuedJob(
                job_id=self._allocate_job_id(),
                sequence=sequence,
                source_text=source_text,
                source_lang=source_lang,
                submitted_at_monotonic=time.perf_counter(),
            )
        )

    async def cancel_older_than(self, sequence: int) -> None:
        tasks_to_cancel: list[asyncio.Task] = []
        async with self._lock:
            if self._queue:
                kept_jobs: list[_QueuedJob] = []
                for job in self._queue:
                    if job.sequence < sequence and not self._is_sequence_relevant(job.sequence):
                        self._increment_metric_locked("translation_jobs_cancelled", 1)
                        self._set_runtime_reason_locked("cancelled:replaced_by_newer_sequence")
                        self._log_event_locked(
                            "translation_job_cancelled",
                            job_id=job.job_id,
                            sequence=job.sequence,
                            source_lang=job.source_lang,
                            source_text_len=len(job.source_text),
                            queue_depth=len(self._queue),
                            relevant=False,
                            fresh=False,
                            reason="replaced_by_newer_sequence",
                        )
                        continue
                    kept_jobs.append(job)
                self._queue = deque(kept_jobs)
            for active_job in list(self._active_jobs.values()):
                if active_job.sequence < sequence and not self._is_sequence_relevant(active_job.sequence):
                    tasks_to_cancel.append(active_job.task)
                    self._increment_metric_locked("translation_jobs_cancelled", 1)
                    self._set_runtime_reason_locked("cancelled:active_job_replaced")
                    self._log_event_locked(
                        "translation_job_cancelled",
                        job_id=active_job.job_id,
                        sequence=active_job.sequence,
                        source_lang=active_job.source_lang,
                        source_text_len=active_job.source_text_len,
                        queue_depth=len(self._queue) + len(self._active_jobs),
                        relevant=False,
                        fresh=False,
                        reason="active_job_replaced",
                    )
            self._emit_metrics_locked()
        for task in tasks_to_cancel:
            task.cancel()

    async def stop(self) -> None:
        self._stopped = True
        self._queue_event.set()
        worker_task = self._worker_task
        if worker_task is not None:
            worker_task.cancel()
        tasks: list[asyncio.Task] = []
        async with self._lock:
            self._queue.clear()
            tasks = [active_job.task for active_job in self._active_jobs.values()]
            self._active_jobs.clear()
            self._metrics["translation_queue_depth"] = 0
            self._emit_metrics_locked()
        for task in tasks:
            task.cancel()
        if worker_task is not None:
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._worker_task = None

    def _ensure_worker_started(self) -> None:
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._worker_task = asyncio.create_task(self._worker_loop())

    def _allocate_job_id(self) -> int:
        self._next_job_id += 1
        return self._next_job_id

    def _translation_config(self) -> dict[str, Any]:
        config = self._config_getter()
        translation = config.get("translation", {}) if isinstance(config, dict) else {}
        return translation if isinstance(translation, dict) else {}

    def _queue_max_size(self) -> int:
        translation = self._translation_config()
        try:
            return max(1, min(64, int(translation.get("queue_max_size", _DEFAULT_QUEUE_MAX_SIZE) or _DEFAULT_QUEUE_MAX_SIZE)))
        except (TypeError, ValueError):
            return _DEFAULT_QUEUE_MAX_SIZE

    def _provider_timeout_seconds(self) -> float:
        translation = self._translation_config()
        try:
            timeout_ms = int(translation.get("timeout_ms", _DEFAULT_TIMEOUT_MS) or _DEFAULT_TIMEOUT_MS)
        except (TypeError, ValueError):
            timeout_ms = _DEFAULT_TIMEOUT_MS
        return max(1.0, min(60.0, timeout_ms / 1000.0))

    def _max_concurrent_jobs(self) -> int:
        translation = self._translation_config()
        try:
            return max(
                1,
                min(8, int(translation.get("max_concurrent_jobs", _DEFAULT_MAX_CONCURRENT_JOBS) or _DEFAULT_MAX_CONCURRENT_JOBS)),
            )
        except (TypeError, ValueError):
            return _DEFAULT_MAX_CONCURRENT_JOBS

    async def _enqueue(self, job: _QueuedJob) -> None:
        async with self._lock:
            while len(self._queue) >= self._queue_max_size():
                dropped_index = None
                for index, queued_job in enumerate(self._queue):
                    if not self._is_sequence_relevant(queued_job.sequence):
                        dropped_index = index
                        break
                if dropped_index is None:
                    dropped_index = 0
                kept_jobs = list(self._queue)
                dropped_job = kept_jobs.pop(dropped_index)
                self._queue = deque(kept_jobs)
                self._increment_metric_locked("translation_jobs_cancelled", 1)
                self._set_runtime_reason_locked("cancelled:queue_overflow")
                is_relevant = self._is_sequence_relevant(dropped_job.sequence)
                self._log_event_locked(
                    "translation_job_cancelled",
                    job_id=dropped_job.job_id,
                    sequence=dropped_job.sequence,
                    source_lang=dropped_job.source_lang,
                    source_text_len=len(dropped_job.source_text),
                    queue_depth=len(self._queue),
                    relevant=is_relevant,
                    fresh=is_relevant,
                    reason="queue_overflow",
                )
            self._queue.append(job)
            self._queue_event.set()
            self._emit_metrics_locked()

    async def _worker_loop(self) -> None:
        try:
            while not self._stopped:
                async with self._lock:
                    if self._stopped:
                        return
                    if self._queue and len(self._active_jobs) < self._max_concurrent_jobs():
                        job = self._queue.popleft()
                        queue_latency_ms = max(0.0, (time.perf_counter() - job.submitted_at_monotonic) * 1000.0)
                        timeout_ms = int(self._provider_timeout_seconds() * 1000)
                        self._metrics["translation_queue_latency_ms"] = round(queue_latency_ms, 2)
                        task = asyncio.create_task(self._run_job(job))
                        self._active_jobs[job.job_id] = _ActiveJob(
                            job_id=job.job_id,
                            sequence=job.sequence,
                            source_lang=job.source_lang,
                            source_text_len=len(job.source_text),
                            task=task,
                        )
                        self._increment_metric_locked("translation_jobs_started", 1)
                        self._set_runtime_reason_locked(None)
                        self._emit_metrics_locked()
                        is_relevant = self._is_sequence_relevant(job.sequence)
                        self._log_event_locked(
                            "translation_job_started",
                            job_id=job.job_id,
                            sequence=job.sequence,
                            source_lang=job.source_lang,
                            source_text_len=len(job.source_text),
                            queue_depth=len(self._queue) + len(self._active_jobs),
                            queue_latency_ms=round(queue_latency_ms, 2),
                            timeout_ms=timeout_ms,
                            relevant=is_relevant,
                            fresh=is_relevant,
                        )
                        continue
                    self._queue_event.clear()
                await self._queue_event.wait()
        except asyncio.CancelledError:
            raise

    async def _run_job(self, job: _QueuedJob) -> None:
        translation_config: dict[str, Any] | None = None
        prepared: PreparedTranslationRequest | None = None
        target_tasks: list[asyncio.Task] = []
        try:
            translation_config = self._translation_config()
            if not translation_config.get("enabled"):
                self._log_event(
                    "translation_publish_skipped",
                    job_id=job.job_id,
                    sequence=job.sequence,
                    source_lang=job.source_lang,
                    source_text_len=len(job.source_text),
                    relevant=self._is_sequence_relevant(job.sequence),
                    fresh=self._is_sequence_relevant(job.sequence),
                    reason="translation_disabled",
                )
                return
            prepared = self._translation_engine.prepare_request(translation_config)
            async with self._lock:
                self._set_metric_locked("translation_last_provider", prepared.provider_name)
            if not prepared.target_languages:
                self._log_event(
                    "translation_publish_skipped",
                    job_id=job.job_id,
                    sequence=job.sequence,
                    source_lang=job.source_lang,
                    source_text_len=len(job.source_text),
                    provider=prepared.provider_name,
                    target_languages=[],
                    relevant=self._is_sequence_relevant(job.sequence),
                    fresh=self._is_sequence_relevant(job.sequence),
                    reason="no_target_languages",
                )
                return
            if not self._is_sequence_relevant(job.sequence):
                async with self._lock:
                    self._increment_metric_locked("translation_stale_results_dropped", 1)
                    self._set_runtime_reason_locked("stale:job_not_relevant")
                    self._emit_metrics_locked()
                self._log_event(
                    "translation_stale_dropped",
                    job_id=job.job_id,
                    sequence=job.sequence,
                    source_lang=job.source_lang,
                    source_text_len=len(job.source_text),
                    provider=prepared.provider_name,
                    target_languages=list(prepared.target_languages),
                    relevant=False,
                    fresh=False,
                    reason="job_not_relevant",
                )
                return
            timeout_seconds = self._provider_timeout_seconds()
            timeout_ms = int(timeout_seconds * 1000)
            target_tasks = [
                asyncio.create_task(
                    self._translate_one_target(
                        job=job,
                        prepared=prepared,
                        target_lang=target_lang,
                        timeout_seconds=timeout_seconds,
                    )
                )
                for target_lang in prepared.target_languages
            ]
            published_items: list[TranslationItem] = []
            final_status_message: str | None = None
            for target_lang in prepared.target_languages:
                self._log_event(
                    "translation_target_started",
                    job_id=job.job_id,
                    sequence=job.sequence,
                    source_lang=job.source_lang,
                    source_text_len=len(job.source_text),
                    target_lang=target_lang,
                    target_languages=list(prepared.target_languages),
                    provider=prepared.provider_name,
                    timeout_ms=timeout_ms,
                    relevant=True,
                    fresh=True,
                )
            for task in asyncio.as_completed(target_tasks):
                result = await task
                item = result.item
                provider_latency_ms = round(result.provider_latency_ms, 2)
                status_message = result.status_message
                async with self._lock:
                    self._metrics["translation_provider_latency_ms"] = provider_latency_ms
                    self._metrics["translation_last_target_lang"] = item.target_lang
                    self._metrics["translation_last_timeout_ms"] = timeout_ms
                    if result.outcome in {"timeout", "error"}:
                        self._set_runtime_reason_locked(result.reason or item.error or result.outcome)
                    self._emit_metrics_locked()
                is_relevant = self._is_sequence_relevant(job.sequence)
                event_fields = {
                    "job_id": job.job_id,
                    "sequence": job.sequence,
                    "source_lang": job.source_lang,
                    "source_text_len": len(job.source_text),
                    "target_lang": item.target_lang,
                    "target_languages": list(prepared.target_languages),
                    "provider": prepared.provider_name,
                    "latency_ms": provider_latency_ms,
                    "queue_latency_ms": self._metrics.get("translation_queue_latency_ms"),
                    "timeout_ms": timeout_ms,
                    "relevant": is_relevant,
                    "fresh": is_relevant,
                }
                if result.outcome == "timeout":
                    self._log_event("translation_target_timeout", reason=result.reason, **event_fields)
                elif result.outcome == "error":
                    self._log_event("translation_target_error", reason=result.reason or item.error, **event_fields)
                else:
                    self._log_event("translation_target_done", reason=result.reason, **event_fields)
                if self._stopped:
                    self._log_event(
                        "translation_publish_skipped",
                        job_id=job.job_id,
                        sequence=job.sequence,
                        source_lang=job.source_lang,
                        source_text_len=len(job.source_text),
                        target_lang=item.target_lang,
                        provider=prepared.provider_name,
                        relevant=False,
                        fresh=False,
                        reason="dispatcher_stopped",
                    )
                    return
                if not is_relevant:
                    logger.info("Dropping stale translation result for sequence=%s target=%s", job.sequence, item.target_lang)
                    async with self._lock:
                        self._increment_metric_locked("translation_stale_results_dropped", 1)
                        self._set_runtime_reason_locked("stale:target_result_arrived_late")
                        self._emit_metrics_locked()
                    self._log_event(
                        "translation_stale_dropped",
                        job_id=job.job_id,
                        sequence=job.sequence,
                        source_lang=job.source_lang,
                        source_text_len=len(job.source_text),
                        target_lang=item.target_lang,
                        target_languages=list(prepared.target_languages),
                        provider=prepared.provider_name,
                        latency_ms=provider_latency_ms,
                        timeout_ms=timeout_ms,
                        relevant=False,
                        fresh=False,
                        reason="target_result_arrived_late",
                    )
                    self._log_event(
                        "translation_publish_skipped",
                        job_id=job.job_id,
                        sequence=job.sequence,
                        source_lang=job.source_lang,
                        source_text_len=len(job.source_text),
                        target_lang=item.target_lang,
                        provider=prepared.provider_name,
                        relevant=False,
                        fresh=False,
                        reason="stale_result",
                    )
                    continue
                event = TranslationEvent(
                    sequence=job.sequence,
                    source_text=job.source_text,
                    source_lang=job.source_lang,
                    translations=[item],
                    provider=prepared.provider_name,
                    provider_group=prepared.provider_group,
                    experimental=prepared.experimental,
                    local_provider=prepared.local_provider,
                    used_default_prompt=False,
                    status_message=status_message,
                    is_complete=False,
                )
                await self._publish_event(event)
                published_items.append(item)
                if status_message:
                    final_status_message = status_message
                self._log_event(
                    "translation_publish_accepted",
                    job_id=job.job_id,
                    sequence=job.sequence,
                    source_lang=job.source_lang,
                    source_text_len=len(job.source_text),
                    target_lang=item.target_lang,
                    provider=prepared.provider_name,
                    relevant=True,
                    fresh=True,
                    reason="target_result",
                )
            final_relevant = self._is_sequence_relevant(job.sequence)
            if self._stopped or not final_relevant:
                self._log_event(
                    "translation_publish_skipped",
                    job_id=job.job_id,
                    sequence=job.sequence,
                    source_lang=job.source_lang,
                    source_text_len=len(job.source_text),
                    provider=prepared.provider_name,
                    relevant=final_relevant and not self._stopped,
                    fresh=final_relevant and not self._stopped,
                    reason="completion_not_relevant" if not self._stopped else "dispatcher_stopped",
                )
                return
            event = TranslationEvent(
                sequence=job.sequence,
                source_text=job.source_text,
                source_lang=job.source_lang,
                translations=list(published_items),
                provider=prepared.provider_name,
                provider_group=prepared.provider_group,
                experimental=prepared.experimental,
                local_provider=prepared.local_provider,
                used_default_prompt=False,
                status_message=final_status_message,
                is_complete=True,
            )
            await self._publish_event(event)
            self._log_event(
                "translation_publish_accepted",
                job_id=job.job_id,
                sequence=job.sequence,
                source_lang=job.source_lang,
                source_text_len=len(job.source_text),
                provider=prepared.provider_name,
                relevant=True,
                fresh=True,
                reason="job_complete",
            )
        except asyncio.CancelledError:
            for task in target_tasks:
                task.cancel()
            await asyncio.gather(*target_tasks, return_exceptions=True)
            raise
        except Exception as exc:
            logger.exception("Translation dispatcher job failed for sequence=%s", job.sequence)
            error_reason = str(exc).strip() or exc.__class__.__name__
            async with self._lock:
                self._set_runtime_reason_locked(f"job_error:{error_reason}")
                self._emit_metrics_locked()
            target_languages = (
                list(prepared.target_languages)
                if prepared is not None
                else self._normalize_target_languages(translation_config.get("target_languages", []))
                if isinstance(translation_config, dict)
                else []
            )
            provider_name = (
                prepared.provider_name
                if prepared is not None
                else str(translation_config.get("provider", "")).strip() or None
                if isinstance(translation_config, dict)
                else None
            )
            self._log_event(
                "translation_job_error",
                job_id=job.job_id,
                sequence=job.sequence,
                source_lang=job.source_lang,
                source_text_len=len(job.source_text),
                provider=provider_name,
                target_languages=target_languages,
                relevant=self._is_sequence_relevant(job.sequence),
                fresh=self._is_sequence_relevant(job.sequence),
                error_type=exc.__class__.__name__,
                reason=error_reason,
            )
        finally:
            async with self._lock:
                current_job = self._active_jobs.get(job.job_id)
                if current_job is not None and current_job.task is asyncio.current_task():
                    self._active_jobs.pop(job.job_id, None)
                self._emit_metrics_locked()
                if self._queue:
                    self._queue_event.set()

    async def _translate_one_target(
        self,
        *,
        job: _QueuedJob,
        prepared: PreparedTranslationRequest,
        target_lang: str,
        timeout_seconds: float,
    ) -> _TargetResult:
        started_at = time.perf_counter()
        try:
            item, diagnostics = await asyncio.wait_for(
                self._translation_engine.translate_target(
                    source_text=job.source_text,
                    source_lang=job.source_lang,
                    provider_name=prepared.provider_name,
                    provider_settings=prepared.provider_settings,
                    target_lang=target_lang,
                ),
                timeout=timeout_seconds,
            )
            status_message = diagnostics.get("status_message")
            return _TargetResult(
                item=item,
                provider_latency_ms=(time.perf_counter() - started_at) * 1000.0,
                status_message=str(status_message) if status_message else None,
                outcome="done",
                reason="success",
            )
        except asyncio.TimeoutError:
            timeout_ms = int(timeout_seconds * 1000)
            return _TargetResult(
                item=TranslationItem(
                    target_lang=target_lang,
                    text="",
                    provider=prepared.provider_name,
                    cached=False,
                    success=False,
                    error=f"Translation timed out after {timeout_ms} ms.",
                ),
                provider_latency_ms=(time.perf_counter() - started_at) * 1000.0,
                status_message="Translation target timed out.",
                outcome="timeout",
                reason=f"timeout_after_{timeout_ms}_ms",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return _TargetResult(
                item=TranslationItem(
                    target_lang=target_lang,
                    text="",
                    provider=prepared.provider_name,
                    cached=False,
                    success=False,
                    error=str(exc),
                ),
                provider_latency_ms=(time.perf_counter() - started_at) * 1000.0,
                status_message=f"Translation target failed: {exc}",
                outcome="error",
                reason=str(exc),
            )

    async def _publish_event(self, event: TranslationEvent) -> None:
        try:
            await self._publish_callback(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Publishing translation event failed for sequence=%s", event.sequence)

    def _increment_metric_locked(self, key: str, amount: int) -> None:
        current = int(self._metrics.get(key, 0) or 0)
        self._metrics[key] = current + int(amount)

    def _set_metric_locked(self, key: str, value: Any) -> None:
        self._metrics[key] = value

    def _set_runtime_reason_locked(self, reason: str | None) -> None:
        self._set_metric_locked("translation_last_runtime_reason", reason)

    def _log_event(self, event: str, **fields: Any) -> None:
        if self._structured_logger is None:
            return
        payload = dict(fields)
        payload.setdefault("queue_depth", int(self._metrics.get("translation_queue_depth", 0) or 0))
        payload.setdefault("cancelled_count", int(self._metrics.get("translation_jobs_cancelled", 0) or 0))
        payload.setdefault("stale_drop_count", int(self._metrics.get("translation_stale_results_dropped", 0) or 0))
        self._structured_logger.log(
            "translation_dispatcher",
            event,
            source="translation_dispatcher",
            payload=payload,
        )

    def _log_event_locked(self, event: str, **fields: Any) -> None:
        self._log_event(event, **fields)

    def _emit_metrics_locked(self) -> None:
        self._metrics["translation_queue_depth"] = len(self._queue) + len(self._active_jobs)
        if self._structured_logger is not None:
            queue_depth = int(self._metrics.get("translation_queue_depth", 0) or 0)
            if self._last_logged_queue_depth != queue_depth:
                self._last_logged_queue_depth = queue_depth
                self._structured_logger.log(
                    "translation_dispatcher",
                    "translation_queue_depth_changed",
                    source="translation_dispatcher",
                    payload={
                        "queue_depth": queue_depth,
                        "jobs_started": int(self._metrics.get("translation_jobs_started", 0) or 0),
                        "jobs_cancelled": int(self._metrics.get("translation_jobs_cancelled", 0) or 0),
                        "stale_drop_count": int(self._metrics.get("translation_stale_results_dropped", 0) or 0),
                        "queue_latency_ms": self._metrics.get("translation_queue_latency_ms"),
                        "latency_ms": self._metrics.get("translation_provider_latency_ms"),
                        "reason": self._metrics.get("translation_last_runtime_reason"),
                    },
                )
        if self._metrics_callback is None:
            return
        snapshot = dict(self._metrics)
        try:
            self._metrics_callback(snapshot)
        except Exception:
            logger.exception("Translation dispatcher metrics callback failed")

    @staticmethod
    def _normalize_target_languages(target_languages: Any) -> list[str]:
        if not isinstance(target_languages, list):
            return []
        return [str(item).strip().lower() for item in target_languages if str(item).strip()]
