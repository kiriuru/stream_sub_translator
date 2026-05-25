const LIFECYCLE_STATES = new Set([
  "idle",
  "partial_only",
  "completed_only",
  "completed_with_partial",
]);

export function normalizeOverlayPayload(payload) {
  const current = payload && typeof payload === "object" ? payload : {};
  const rawLifecycle = String(current.lifecycle_state || "idle");
  // The renderer's composeRenderRows uses lifecycle_state to detect the
  // "completed_with_partial" mix and mark the live partial text (sitting
  // inside visible_items[source]) as transient. Dropping the field here
  // would silently downgrade every dashboard render to the legacy
  // completed-text-changes-every-frame behaviour that re-renders the
  // source row continuously whenever a translation is visible.
  const lifecycle_state = LIFECYCLE_STATES.has(rawLifecycle) ? rawLifecycle : "idle";
  return {
    sequence: Number.isFinite(Number(current.sequence)) ? Number(current.sequence) : 0,
    event_sequence: Number.isFinite(Number(current.event_sequence)) ? Number(current.event_sequence) : 0,
    created_at_ms: Number.isFinite(Number(current.created_at_ms)) ? Number(current.created_at_ms) : 0,
    preset: ["single", "dual-line", "stacked"].includes(String(current.preset || "stacked"))
      ? String(current.preset || "stacked")
      : "stacked",
    compact: current.compact === true,
    completed_block_visible: current.completed_block_visible !== false,
    lifecycle_state,
    active_partial_text: String(current.active_partial_text || ""),
    visible_items: (Array.isArray(current.visible_items) ? current.visible_items : []).map((item) => ({
      kind: String(item?.kind || "source"),
      lang: String(item?.lang || ""),
      slot_id: String(item?.slot_id || ""),
      target_lang: String(item?.target_lang || ""),
      label: String(item?.label || ""),
      provider: String(item?.provider || ""),
      text: String(item?.text || ""),
      style_slot: String(item?.style_slot || ""),
    })),
    style: current.style && typeof current.style === "object" ? { ...current.style } : {},
  };
}
