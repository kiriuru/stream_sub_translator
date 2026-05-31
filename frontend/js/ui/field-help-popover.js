let activePopover = null;
let activeButton = null;
let documentListenersBound = false;

function closeFieldHelpPopover() {
  if (activePopover) {
    activePopover.remove();
    activePopover = null;
  }
  if (activeButton) {
    activeButton.setAttribute("aria-expanded", "false");
    activeButton = null;
  }
}

function positionFieldHelpPopover(popover, button) {
  const rect = button.getBoundingClientRect();
  const margin = 8;
  popover.style.position = "fixed";
  popover.style.bottom = `${window.innerHeight - rect.bottom}px`;
  popover.style.left = `${rect.left}px`;
  popover.style.maxWidth = `${Math.min(320, window.innerWidth - margin * 2)}px`;

  const popoverRect = popover.getBoundingClientRect();
  let left = rect.left;
  if (left + popoverRect.width > window.innerWidth - margin) {
    left = Math.max(margin, window.innerWidth - popoverRect.width - margin);
  }
  popover.style.left = `${left}px`;

  if (popoverRect.top < margin) {
    popover.style.bottom = `${window.innerHeight - rect.top + margin}px`;
  }
}

function openFieldHelpPopover(button, translate) {
  const helpKey = button.dataset.fieldHelpKey;
  if (!helpKey) {
    return;
  }
  if (activeButton === button) {
    closeFieldHelpPopover();
    return;
  }
  closeFieldHelpPopover();

  const popover = document.createElement("div");
  popover.className = "field-help-popover";
  popover.setAttribute("role", "tooltip");
  popover.textContent = translate(helpKey);
  document.body.appendChild(popover);
  positionFieldHelpPopover(popover, button);
  button.setAttribute("aria-expanded", "true");
  activePopover = popover;
  activeButton = button;
}

function bindDocumentListeners() {
  if (documentListenersBound) {
    return;
  }
  documentListenersBound = true;
  document.addEventListener(
    "click",
    (event) => {
      if (!activePopover) {
        return;
      }
      const target = event.target;
      if (target instanceof Node && (activePopover.contains(target) || activeButton === target)) {
        return;
      }
      closeFieldHelpPopover();
    },
    true
  );
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeFieldHelpPopover();
    }
  });
  window.addEventListener("resize", closeFieldHelpPopover);
  window.addEventListener(
    "scroll",
    () => {
      if (activePopover && activeButton) {
        positionFieldHelpPopover(activePopover, activeButton);
      }
    },
    true
  );
}

export function mountFieldHelpButtons(root, translate) {
  if (!root) {
    return () => {};
  }
  bindDocumentListeners();
  const buttons = [...root.querySelectorAll(".field-help-btn[data-field-help-key]")];
  const handlers = buttons.map((button) => {
    const onClick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      openFieldHelpPopover(button, translate);
    };
    button.addEventListener("click", onClick);
    return () => button.removeEventListener("click", onClick);
  });
  const onLocaleChanged = () => {
    if (activePopover && activeButton) {
      const helpKey = activeButton.dataset.fieldHelpKey;
      if (helpKey) {
        activePopover.textContent = translate(helpKey);
        positionFieldHelpPopover(activePopover, activeButton);
      }
    }
  };
  window.addEventListener("sst:locale-changed", onLocaleChanged);
  return () => {
    handlers.forEach((off) => off());
    window.removeEventListener("sst:locale-changed", onLocaleChanged);
    if (activeButton && root.contains(activeButton)) {
      closeFieldHelpPopover();
    }
  };
}
