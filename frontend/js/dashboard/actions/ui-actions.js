export function createUiActions({ store, events }) {
  function updateTranslationSelection(code) {
    store.updateState({ ui: { selectedTranslationLanguage: code || null } });
  }

  function updateSubtitleSelection(code) {
    store.updateState({ ui: { selectedSubtitleOrderItem: code || null } });
  }

  function updateStyleSlot(slotName) {
    store.updateState({ ui: { selectedStyleLineSlot: slotName || "source" } });
  }

  function setActiveTab(tabName) {
    const normalized = String(tabName || "").trim();
    if (!normalized) {
      return;
    }
    store.updateState({ ui: { activeTab: normalized } });
    document.querySelectorAll("[data-tab-target]").forEach((button) => {
      const active = button.dataset.tabTarget === normalized;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.tabPanel === normalized);
    });
    if (document.body.classList.contains("sst-layout-compact")) {
      window.SstLayout?.applyCompactTabScope?.(normalized);
      const activePanel = document.querySelector(".tab-panel.active");
      if (activePanel) {
        activePanel.scrollTop = 0;
      }
    }
    events?.emit?.("tab:changed", { tab: normalized });
  }

  return {
    updateTranslationSelection,
    updateSubtitleSelection,
    updateStyleSlot,
    setActiveTab,
  };
}
