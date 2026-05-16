import { getCurrentLocale } from "../dashboard/helpers.js";

export function initializeHelpTopics() {
  const buttons = [...document.querySelectorAll("[data-help-topic-target]")];
  const panels = [...document.querySelectorAll("[data-help-topic-panel]")];
  if (!buttons.length || !panels.length) {
    return () => {};
  }

  const availableTopics = new Set(panels.map((panel) => panel.dataset.helpTopicPanel));
  let activeTopic = buttons.find((button) => button.classList.contains("active"))?.dataset.helpTopicTarget;
  if (!availableTopics.has(activeTopic)) {
    activeTopic = panels[0]?.dataset.helpTopicPanel || "";
  }

  function applyHelpLocale() {
    const locale = getCurrentLocale();
    panels.forEach((panel) => {
      const localizedBlocks = [...panel.querySelectorAll("[data-help-locale]")];
      localizedBlocks.forEach((block) => {
        const active = block.dataset.helpLocale === locale;
        block.classList.toggle("active", active);
      });
      if (localizedBlocks.length && !localizedBlocks.some((block) => block.classList.contains("active"))) {
        localizedBlocks[0].classList.add("active");
      }
    });
  }

  function applyHelpTopic(topicName) {
    activeTopic = availableTopics.has(topicName) ? topicName : activeTopic;
    buttons.forEach((button) => {
      const active = button.dataset.helpTopicTarget === activeTopic;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    panels.forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.helpTopicPanel === activeTopic);
    });
    applyHelpLocale();
  }

  const listeners = buttons.map((button) => {
    const onClick = () => applyHelpTopic(button.dataset.helpTopicTarget);
    button.addEventListener("click", onClick);
    return () => button.removeEventListener("click", onClick);
  });
  const onLocaleChanged = () => applyHelpLocale();
  window.addEventListener("sst:locale-changed", onLocaleChanged);

  applyHelpTopic(activeTopic);

  return () => {
    listeners.forEach((destroy) => destroy());
    window.removeEventListener("sst:locale-changed", onLocaleChanged);
  };
}
