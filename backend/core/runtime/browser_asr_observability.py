"""
Browser ASR observability — causality domains and trace scope (Domain A only).

This module documents architecture constraints; it does not implement tracing logic.

**Domain A — ASR operational trace (this subsystem)**

Required causal chain for the browser worker → backend ingest → FSM → recovery policy path:
`event_id`, `causal_parent_id`, `generation_id`, `session_id`, `transport_id`.
Applies to [`StructuredRuntimeLogger`](../../core/structured_runtime_logger.py) events
prefixed with [`BASR_EVENT_PREFIX`](BASR_EVENT_PREFIX).

**Not in scope:** mandatory end-to-end distributed tracing through translation, subtitle
routing, overlay, or generic WebSocket fan-out. Those subsystems may use *reference*
links to Domain A where needed, but must not require a single merged causal graph.

**Domain B — Transcript revision lineage**

Segment `revision` and identity; links to Domain A via optional reference fields on
[`TranscriptSegment`](../../models.py), not a unified graph with Domain A.

**Domain C — Translation preview lineage (when used)**

Preview/supersession jobs reference Domain B keys only.

See also: repo doc ``docs/plans/browser_asr_observability_roadmap.md``.
"""

from __future__ import annotations

# Machine-oriented event names for runtime-events.log (browser ASR operational path).
BASR_EVENT_PREFIX = "basr."

# Domain labels for structured log `causal_domain` when forwarding references.
CAUSAL_DOMAIN_ASR_OPERATIONAL = "asr_operational"
CAUSAL_DOMAIN_TRANSCRIPT_LINEAGE = "transcript_lineage"
CAUSAL_DOMAIN_TRANSLATION_PREVIEW = "translation_preview"

__all__ = [
    "BASR_EVENT_PREFIX",
    "CAUSAL_DOMAIN_ASR_OPERATIONAL",
    "CAUSAL_DOMAIN_TRANSCRIPT_LINEAGE",
    "CAUSAL_DOMAIN_TRANSLATION_PREVIEW",
]
