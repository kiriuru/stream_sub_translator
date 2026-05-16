import { collectElements, fillSelectOptions } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { selectConfig, selectProfiles } from "../core/selectors.js";

const collectProfilesElements = (root) =>
  collectElements(root, {
    select: "#profiles-select",
    loadBtn: "#profile-load-btn",
    saveBtn: "#profile-save-btn",
    deleteBtn: "#profile-delete-btn",
    nameInput: "#profile-name-input",
  });

function renderProfiles(snapshot, elements) {
  if (!elements.select) {
    return;
  }
  const profiles = selectProfiles(snapshot);
  const config = selectConfig(snapshot);
  fillSelectOptions(
    elements.select,
    profiles.map((name) => ({ value: name, label: name })),
    { selectedValue: config?.profile || elements.select.value }
  );
  if (elements.nameInput && config?.profile) {
    elements.nameInput.value = config.profile;
  }
}

function bindProfilesEvents(elements, { store, actions, api, logger }) {
  const handlers = [];

  const onLoad = async () => {
    const name = elements.select?.value;
    if (!name) {
      return;
    }
    const data = await api.loadProfile(name);
    const response = await api.saveSettings(data.payload);
    actions.setConfig(response.payload || data.payload);
    await actions.refreshProfiles();
    logger(`[profiles] loaded '${name}'`);
  };

  const onSave = async () => {
    const name = elements.nameInput?.value?.trim();
    if (!name) {
      return;
    }
    const payload = store.getState().config;
    await api.saveProfile(name, payload);
    actions.mutateConfig((draft) => {
      draft.profile = name;
    });
    await actions.refreshProfiles();
    logger(`[profiles] saved '${name}'`);
  };

  const onDelete = async () => {
    const name = elements.select?.value;
    if (!name) {
      return;
    }
    const result = await api.deleteProfile(name);
    if (!result.deleted) {
      return;
    }
    await actions.refreshProfiles();
    logger(`[profiles] deleted '${name}'`);
  };

  if (elements.loadBtn) {
    elements.loadBtn.addEventListener("click", onLoad);
    handlers.push(() => elements.loadBtn.removeEventListener("click", onLoad));
  }
  if (elements.saveBtn) {
    elements.saveBtn.addEventListener("click", onSave);
    handlers.push(() => elements.saveBtn.removeEventListener("click", onSave));
  }
  if (elements.deleteBtn) {
    elements.deleteBtn.addEventListener("click", onDelete);
    handlers.push(() => elements.deleteBtn.removeEventListener("click", onDelete));
  }

  return () => handlers.forEach((off) => off());
}

const mountProfilesPanelImpl = createPanelMount({
  collectElements: collectProfilesElements,
  render: renderProfiles,
  bindEvents: bindProfilesEvents,
});

export function mountProfilesPanel(root, context) {
  return mountProfilesPanelImpl(root, context);
}
