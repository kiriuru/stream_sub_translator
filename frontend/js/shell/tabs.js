export function initializeTabs(actions, store) {
  const buttons = [...document.querySelectorAll("[data-tab-target]")];
  const panels = [...document.querySelectorAll("[data-tab-panel]")];
  const availableTabs = new Set(panels.map((panel) => panel.dataset.tabPanel));
  const preferredTab = store.getState().ui.activeTab;
  const initialTab = availableTabs.has(preferredTab)
    ? preferredTab
    : availableTabs.has("translation")
      ? "translation"
      : panels.find((panel) => panel.dataset.tabPanel !== "recognition")?.dataset.tabPanel || panels[0]?.dataset.tabPanel || "translation";

  function applyActiveTab(tabName) {
    if (!availableTabs.has(tabName)) {
      return;
    }
    actions.setActiveTab(tabName);
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      applyActiveTab(button.dataset.tabTarget);
    });
  });
  applyActiveTab(initialTab);
}
