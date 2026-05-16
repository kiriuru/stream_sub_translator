import { clearElement } from "../../core/dom.js";
import { getSubtitleSlotLabel } from "../../dashboard/helpers.js";

export function renderSubtitleDisplayOrder(listElement, snapshot, { onSelect, onReorder }) {
  if (!listElement) {
    return;
  }
  const config = snapshot.config;
  if (!config) {
    return;
  }
  clearElement(listElement);
  const displayOrder = Array.isArray(config.subtitle_output?.display_order) ? config.subtitle_output.display_order : [];
  displayOrder.forEach((code) => {
    const li = document.createElement("li");
    li.dataset.code = code;
    li.textContent = getSubtitleSlotLabel(code);
    li.classList.toggle("active", code === snapshot.ui.selectedSubtitleOrderItem);
    li.addEventListener("click", () => onSelect?.(code));
    listElement.appendChild(li);
  });
}
