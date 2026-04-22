window.Api = {
  async getHealth() {
    const response = await fetch("/api/health");
    return response.json();
  },

  async getObsUrl() {
    const response = await fetch("/api/obs/url");
    return response.json();
  },

  async getAudioInputs() {
    const response = await fetch("/api/devices/audio-inputs");
    return response.json();
  },

  async startRuntime(deviceId) {
    const response = await fetch("/api/runtime/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId || null }),
    });
    return response.json();
  },

  async stopRuntime() {
    const response = await fetch("/api/runtime/stop", { method: "POST" });
    return response.json();
  },

  async getRuntimeStatus() {
    const response = await fetch("/api/runtime/status");
    return response.json();
  },

  async loadSettings() {
    const response = await fetch("/api/settings/load");
    return response.json();
  },

  async saveSettings(payload) {
    const response = await fetch("/api/settings/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    });
    return response.json();
  },

  async listProfiles() {
    const response = await fetch("/api/profiles");
    return response.json();
  },

  async loadProfile(name) {
    const response = await fetch(`/api/profiles/${encodeURIComponent(name)}`);
    return response.json();
  },

  async saveProfile(name, payload) {
    const response = await fetch(`/api/profiles/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    });
    return response.json();
  },

  async deleteProfile(name) {
    const response = await fetch(`/api/profiles/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
    return response.json();
  },
};
