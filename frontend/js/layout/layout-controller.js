const LAYOUT_STANDARD = "standard";
const LAYOUT_COMPACT = "compact";

const COMPACT_NAV_ITEMS = [
  { target: "recognition", icon: "🎙", labelKey: "compact.nav.recognition" },
  { target: "translation", icon: "⇄", labelKey: "compact.nav.translation" },
  { target: "subtitles", icon: "▭", labelKey: "compact.nav.subtitles" },
  { target: "style", icon: "Aa", labelKey: "compact.nav.style" },
  { target: "theme", icon: "◐", labelKey: "compact.nav.theme" },
  { target: "obs", icon: "▣", labelKey: "compact.nav.obs" },
  { target: "tuning", icon: "◎", labelKey: "compact.nav.tuning" },
  { target: "asr_advanced", icon: "⏱", labelKey: "compact.nav.asr_advanced" },
  { target: "replacement", icon: "✎", labelKey: "compact.nav.replacement" },
  { target: "settings", icon: "⚙", labelKey: "compact.nav.settings" },
];

const WINDOW_SIZES = {
  standard: { width: 1440, height: 940, minWidth: 1180, minHeight: 760 },
  compact: { width: 400, height: 844, minWidth: 360, minHeight: 640 },
};

function normalizeLayout(value) {
  return String(value || "").trim().toLowerCase() === LAYOUT_COMPACT ? LAYOUT_COMPACT : LAYOUT_STANDARD;
}

function t(key) {
  return window.I18n?.t?.(key) || key;
}

export function applyDashboardLayout(layout, { persistBodyClass = true } = {}) {
  const mode = normalizeLayout(layout);
  if (persistBodyClass) {
    document.body.classList.toggle("sst-layout-compact", mode === LAYOUT_COMPACT);
    document.body.classList.toggle("sst-layout-standard", mode === LAYOUT_STANDARD);
    document.body.dataset.sstLayout = mode;
  }
  const compactNav = document.getElementById("compact-nav-root");
  if (compactNav) {
    compactNav.hidden = mode !== LAYOUT_COMPACT;
  }
  document.querySelectorAll("#ui-layout-select").forEach((element) => {
    if (element.value !== mode) {
      element.value = mode;
    }
  });
  void requestDesktopWindowResize(mode);
  mountDashboardLayoutSections(mode);
  return mode;
}

function traceDesktopResize(event, fields) {
  if (typeof window.SstDesktopUiTrace === "function") {
    window.SstDesktopUiTrace(event, fields);
  }
}

async function requestDesktopWindowResize(layout) {
  const mode = normalizeLayout(layout);
  const sizes = WINDOW_SIZES[mode] || WINDOW_SIZES.standard;
  const resizeApi = window.pywebview?.api?.resize_main_window;
  if (typeof resizeApi === "function") {
    traceDesktopResize("resize_main_window_begin", {
      layout: mode,
      width: sizes.width,
      height: sizes.height,
      min_width: sizes.minWidth,
      min_height: sizes.minHeight,
    });
    try {
      const outcome = resizeApi.call(
        window.pywebview.api,
        mode,
        sizes.width,
        sizes.height,
        sizes.minWidth,
        sizes.minHeight,
      );
      if (outcome && typeof outcome.then === "function") {
        await outcome;
      }
      traceDesktopResize("resize_main_window_complete", { layout: mode, ok: true });
      return true;
    } catch (error) {
      traceDesktopResize("resize_main_window_failed", {
        layout: mode,
        error: error instanceof Error ? error.message : String(error || ""),
      });
    }
  }
  window.dispatchEvent(
    new CustomEvent("sst:layout-changed", {
      detail: { layout: mode, ...sizes },
    })
  );
  return false;
}

export function syncDesktopWindowSize(layout) {
  const mode = normalizeLayout(layout || document.body.dataset.sstLayout || LAYOUT_STANDARD);
  return requestDesktopWindowResize(mode);
}

function installDesktopWindowResizeHook() {
  if (installDesktopWindowResizeHook._installed) {
    return;
  }
  installDesktopWindowResizeHook._installed = true;
  const retry = () => {
    void syncDesktopWindowSize();
  };
  if (typeof window.pywebview?.api?.resize_main_window === "function") {
    retry();
    return;
  }
  document.addEventListener("pywebviewready", retry, { once: true });
}

function setCompactNavExpanded(root, expanded) {
  const expandBtn = root?.querySelector("#compact-nav-expand");
  const isExpanded = Boolean(expanded);
  root?.classList.toggle("compact-nav-expanded", isExpanded);
  document.body.classList.toggle("compact-nav-expanded", isExpanded);
  if (expandBtn) {
    expandBtn.setAttribute("aria-expanded", isExpanded ? "true" : "false");
  }
}

function closeCompactNav(root) {
  setCompactNavExpanded(root, false);
}

function toggleCompactNav(root) {
  const next = !root?.classList.contains("compact-nav-expanded");
  setCompactNavExpanded(root, next);
}

function syncCompactNavActiveTab(target) {
  const tab = String(target || "").trim().toLowerCase();
  document.querySelectorAll("[data-compact-tab-target]").forEach((element) => {
    const active = String(element.dataset.compactTabTarget || "").toLowerCase() === tab;
    element.classList.toggle("is-active", active);
  });
}

function applyCompactTabScope(target) {
  document.body.dataset.sstCompactTab = String(target || "");
  syncCompactNavActiveTab(target);
}

function appendChildUnique(parent, node) {
  if (!parent || !node || node.parentElement === parent) {
    return;
  }
  parent.appendChild(node);
}

function insertAfter(parent, referenceNode, node) {
  if (!parent || !node) {
    return;
  }
  if (referenceNode?.nextSibling) {
    parent.insertBefore(node, referenceNode.nextSibling);
  } else {
    parent.appendChild(node);
  }
}

function getToolsGrid() {
  return document.querySelector('[data-tab-panel="tools"] section.panel.grid');
}

export function mountDashboardLayoutSections(layout) {
  const mode = normalizeLayout(layout);
  const recognitionPanel = document.getElementById("dashboard-recognition-panel");
  const compactRecognitionAnchor = document.getElementById("compact-recognition-anchor");
  const overviewRecognitionAnchor = document.getElementById("overview-recognition-anchor");
  if (recognitionPanel && compactRecognitionAnchor && overviewRecognitionAnchor) {
    appendChildUnique(
      mode === LAYOUT_COMPACT ? compactRecognitionAnchor : overviewRecognitionAnchor,
      recognitionPanel
    );
  }

  const providerPanel = document.getElementById("translation-provider-panel");
  const translationProviderAnchor = document.getElementById("translation-provider-anchor");
  const settingsProviderAnchor = document.getElementById("settings-translation-provider-anchor");
  if (providerPanel && translationProviderAnchor && settingsProviderAnchor) {
    appendChildUnique(
      mode === LAYOUT_COMPACT ? settingsProviderAnchor : translationProviderAnchor,
      providerPanel
    );
  }

  const toolsGrid = getToolsGrid();
  const configBlock = document.getElementById("dashboard-config-block");
  const profilesBlock = document.getElementById("dashboard-profiles-block");
  const settingsConfigAnchor = document.getElementById("settings-config-anchor");
  const settingsProfilesAnchor = document.getElementById("settings-profiles-anchor");
  if (mode === LAYOUT_COMPACT) {
    appendChildUnique(settingsConfigAnchor, configBlock);
    appendChildUnique(settingsProfilesAnchor, profilesBlock);
    return;
  }
  if (toolsGrid) {
    const eventsArticle = toolsGrid.querySelector("article");
    if (configBlock) {
      insertAfter(toolsGrid, eventsArticle, configBlock);
    }
    if (profilesBlock) {
      insertAfter(toolsGrid, configBlock || eventsArticle, profilesBlock);
    }
  }
}

function getActiveCompactTabPanel() {
  return document.querySelector("body.sst-layout-compact .tab-panel.active");
}

function scrollActiveCompactPanelTo(selector) {
  const panel = getActiveCompactTabPanel();
  const target = document.querySelector(selector);
  if (!panel || !target) {
    target?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    return;
  }
  if (!panel.contains(target)) {
    target.scrollIntoView?.({ behavior: "smooth", block: "start" });
    return;
  }
  const top = target.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop;
  panel.scrollTo({ top: Math.max(0, top - 8), behavior: "smooth" });
}

function activateCompactTab(target, actions) {
  if (target === "replacement") {
    actions?.setActiveTab?.("replacement");
    applyCompactTabScope("replacement");
    scrollCompactContentToTop();
    return;
  }
  if (target === "theme") {
    actions?.setActiveTab?.("theme");
    applyCompactTabScope("theme");
    scrollCompactContentToTop();
    return;
  }
  if (target === "recognition") {
    actions?.setActiveTab?.("recognition");
    applyCompactTabScope("recognition");
    scrollCompactContentToTop();
    return;
  }
  actions?.setActiveTab?.(target);
  applyCompactTabScope(target);
  scrollCompactContentToTop();
}

function scrollCompactContentToTop() {
  const panel = getActiveCompactTabPanel();
  if (panel) {
    panel.scrollTop = 0;
    return;
  }
  const column = document.querySelector(".compact-main-column");
  if (column) {
    column.scrollTop = 0;
  }
}

function renderCompactNav(root, actions) {
  const iconList = root.querySelector(".compact-nav-icons");
  if (!iconList) {
    return;
  }
  iconList.textContent = "";
  COMPACT_NAV_ITEMS.forEach((item) => {
    const label = t(item.labelKey);
    const navBtn = document.createElement("button");
    navBtn.type = "button";
    navBtn.className = "compact-nav-item";
    navBtn.dataset.compactTabTarget = item.target;
    navBtn.title = label;
    navBtn.setAttribute("aria-label", label);
    navBtn.innerHTML = `<span class="compact-nav-item-icon" aria-hidden="true">${item.icon}</span><span class="compact-nav-item-label">${label}</span>`;
    navBtn.addEventListener("click", () => {
      activateCompactTab(item.target, actions);
      closeCompactNav(root);
    });
    iconList.appendChild(navBtn);
  });
}

function layoutSelectElements(documentRoot = document) {
  return [...documentRoot.querySelectorAll("#ui-layout-select")];
}

export function mountLayoutController(documentRoot, { actions } = {}) {
  const root = documentRoot.querySelector("#compact-nav-root");
  const cleanups = [];

  const onLayoutChange = (event) => {
    const nextLayout = normalizeLayout(event.target?.value);
    applyDashboardLayout(nextLayout);
    actions?.setUiLayout?.(nextLayout);
    void actions?.saveCurrentConfig?.().catch(() => {
      // layout already applied locally; save failure should not block UI mode switch
    });
  };
  layoutSelectElements(documentRoot).forEach((element) => {
    element.addEventListener("change", onLayoutChange);
    cleanups.push(() => element.removeEventListener("change", onLayoutChange));
  });

  if (root) {
    renderCompactNav(root, actions);

    const expandBtn = root.querySelector("#compact-nav-expand");
    const workspace = documentRoot.querySelector(".compact-workspace");
    const onExpand = (event) => {
      event.stopPropagation();
      toggleCompactNav(root);
    };
    const onWorkspacePointerDown = (event) => {
      if (!root.classList.contains("compact-nav-expanded")) {
        return;
      }
      if (root.contains(event.target)) {
        return;
      }
      closeCompactNav(root);
    };
    expandBtn?.addEventListener("click", onExpand);
    workspace?.addEventListener("pointerdown", onWorkspacePointerDown);
    cleanups.push(() => {
      expandBtn?.removeEventListener("click", onExpand);
      workspace?.removeEventListener("pointerdown", onWorkspacePointerDown);
    });
  }

  const remoteToggle = documentRoot.querySelector("#ui-show-remote-tools");
  const onRemoteToggle = () => {
    actions?.mutateConfig?.((draft) => {
      draft.ui.show_remote_tools = Boolean(remoteToggle?.checked);
    });
    actions?.saveCurrentConfig?.();
    applyRemoteToolsVisibility(Boolean(remoteToggle?.checked));
  };

  const onLocaleChanged = () => {
    if (root) {
      renderCompactNav(root, actions);
    }
  };
  window.addEventListener("sst:locale-changed", onLocaleChanged);
  cleanups.push(() => window.removeEventListener("sst:locale-changed", onLocaleChanged));

  remoteToggle?.addEventListener("change", onRemoteToggle);
  cleanups.push(() => remoteToggle?.removeEventListener("change", onRemoteToggle));

  installDesktopWindowResizeHook();

  return () => {
    cleanups.forEach((cleanup) => cleanup());
  };
}

export function applyRemoteToolsVisibility(enabled) {
  document.body.classList.toggle("sst-remote-tools-enabled", Boolean(enabled));
}

export function syncLayoutControlsFromConfig(config) {
  const layout = normalizeLayout(config?.ui?.layout);
  applyDashboardLayout(layout);
  if (layout === LAYOUT_COMPACT) {
    const activePanel = document.querySelector(".tab-panel.active")?.dataset?.tabPanel;
    if (activePanel) {
      applyCompactTabScope(activePanel);
    }
  }
  applyRemoteToolsVisibility(Boolean(config?.ui?.show_remote_tools));
  const remoteToggle = document.querySelector("#ui-show-remote-tools");
  if (remoteToggle) {
    remoteToggle.checked = Boolean(config?.ui?.show_remote_tools);
  }
}

window.SstLayout = {
  applyDashboardLayout,
  mountDashboardLayoutSections,
  syncLayoutControlsFromConfig,
  syncDesktopWindowSize,
  applyCompactTabScope,
  syncCompactNavActiveTab,
  normalizeLayout,
  LAYOUT_STANDARD,
  LAYOUT_COMPACT,
  WINDOW_SIZES,
};

export { LAYOUT_STANDARD, LAYOUT_COMPACT, normalizeLayout, WINDOW_SIZES };
