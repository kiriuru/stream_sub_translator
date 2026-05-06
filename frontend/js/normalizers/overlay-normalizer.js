export function normalizeOverlayPayload(payload) {
  const current = payload && typeof payload === "object" ? payload : {};
  return {
    sequence: Number.isFinite(Number(current.sequence)) ? Number(current.sequence) : 0,
    event_sequence: Number.isFinite(Number(current.event_sequence)) ? Number(current.event_sequence) : 0,
    created_at_ms: Number.isFinite(Number(current.created_at_ms)) ? Number(current.created_at_ms) : 0,
    preset: ["single", "dual-line", "stacked"].includes(String(current.preset || "stacked"))
      ? String(current.preset || "stacked")
      : "stacked",
    compact: current.compact === true,
    completed_block_visible: current.completed_block_visible !== false,
    active_partial_text: String(current.active_partial_text || ""),
    visible_items: (Array.isArray(current.visible_items) ? current.visible_items : []).map((item) => ({
      kind: String(item?.kind || "source"),
      lang: String(item?.lang || ""),
      text: String(item?.text || ""),
      style_slot: String(item?.style_slot || ""),
    })),
    style: current.style && typeof current.style === "object" ? { ...current.style } : {},
  };
}
