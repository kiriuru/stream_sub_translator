import { subscribe } from "../core/store.js";
import { getCurrentLocale } from "../dashboard/helpers.js";

export function mountProfilesPanel(root, { store, actions, api, logger }) {
  const elements = {
    select: root.querySelector("#profiles-select"),
    loadBtn: root.querySelector("#profile-load-btn"),
    saveBtn: root.querySelector("#profile-save-btn"),
    deleteBtn: root.querySelector("#profile-delete-btn"),
    nameInput: root.querySelector("#profile-name-input"),
  };

  function render(snapshot) {
    if (!elements.select) {
      return;
    }
    const selected = elements.select.value;
    elements.select.innerHTML = "";
    (snapshot.profiles || []).forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      elements.select.appendChild(option);
    });
    elements.select.value = snapshot.config?.profile || selected || "";
    if (elements.nameInput && snapshot.config?.profile) {
      elements.nameInput.value = snapshot.config.profile;
    }
  }

  elements.loadBtn?.addEventListener("click", async () => {
    const name = elements.select?.value;
    if (!name) {
      return;
    }
    const data = await api.loadProfile(name);
    const response = await api.saveSettings(data.payload);
    actions.setConfig(response.payload || data.payload);
    await actions.refreshProfiles();
    logger(`[profiles] loaded '${name}'`);
  });

  elements.saveBtn?.addEventListener("click", async () => {
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
  });

  elements.deleteBtn?.addEventListener("click", async () => {
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
  });

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
