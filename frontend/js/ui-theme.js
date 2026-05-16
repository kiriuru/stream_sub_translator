function clampByte(value) {
  return Math.max(0, Math.min(255, Number(value) || 0));
}

function hexToRgbTriplet(hex) {
  const raw = String(hex || "").trim().replace("#", "");
  if (/^[0-9a-fA-F]{3}$/.test(raw)) {
    const r = Number.parseInt(raw[0] + raw[0], 16);
    const g = Number.parseInt(raw[1] + raw[1], 16);
    const b = Number.parseInt(raw[2] + raw[2], 16);
    return `${clampByte(r)} ${clampByte(g)} ${clampByte(b)}`;
  }
  if (/^[0-9a-fA-F]{6}$/.test(raw)) {
    const r = Number.parseInt(raw.slice(0, 2), 16);
    const g = Number.parseInt(raw.slice(2, 4), 16);
    const b = Number.parseInt(raw.slice(4, 6), 16);
    return `${clampByte(r)} ${clampByte(g)} ${clampByte(b)}`;
  }
  return null;
}

function safeThemeConfig(configPayload) {
  const ui = configPayload?.ui && typeof configPayload.ui === "object" ? configPayload.ui : {};
  const palette = ui.palette && typeof ui.palette === "object" ? ui.palette : {};
  return {
    theme: ui.theme === "light" ? "light" : "dark",
    palette: {
      accent: String(palette.accent || "#6cc7ff"),
      accent_secondary: String(palette.accent_secondary || "#ff6ce6"),
      accent_tertiary: String(palette.accent_tertiary || "#7ce3ad"),
    },
  };
}

export function applyUiThemeFromConfigPayload(configPayload, targetDocument = document) {
  const resolved = safeThemeConfig(configPayload || {});
  const root = targetDocument?.documentElement;
  if (!root) {
    return resolved;
  }

  root.dataset.uiTheme = resolved.theme;

  const accentRgb = hexToRgbTriplet(resolved.palette.accent) || "108 199 255";
  const accent2Rgb = hexToRgbTriplet(resolved.palette.accent_secondary) || "255 108 230";
  const accent3Rgb = hexToRgbTriplet(resolved.palette.accent_tertiary) || "124 227 173";

  root.style.setProperty("--ui-accent", resolved.palette.accent);
  root.style.setProperty("--ui-accent-secondary", resolved.palette.accent_secondary);
  root.style.setProperty("--ui-accent-tertiary", resolved.palette.accent_tertiary);
  root.style.setProperty("--ui-accent-rgb", accentRgb);
  root.style.setProperty("--ui-accent-secondary-rgb", accent2Rgb);
  root.style.setProperty("--ui-accent-tertiary-rgb", accent3Rgb);

  // Dashboard/app CSS variables (app.css) – override key tokens.
  root.style.setProperty(
    "--bg-app",
    resolved.theme === "light" ? "#ffffff" : "#0b1422",
  );
  root.style.setProperty(
    "--bg-canvas",
    resolved.theme === "light" ? "#f6f8ff" : "#080a12",
  );
  root.style.setProperty(
    "--bg-control",
    resolved.theme === "light" ? "rgba(255, 255, 255, 0.96)" : "rgba(8, 14, 24, 0.92)",
  );
  root.style.setProperty(
    "--bg-panel-elevated",
    resolved.theme === "light" ? "rgba(255, 255, 255, 0.92)" : "rgba(7, 14, 24, 0.82)",
  );
  root.style.setProperty("--accent", resolved.palette.accent);
  root.style.setProperty("--accent-secondary", resolved.palette.accent_secondary);
  root.style.setProperty("--accent-strong", resolved.palette.accent_secondary);
  root.style.setProperty("--sst-info", resolved.palette.accent);

  // Soft tokens used in gradients/highlights.
  root.style.setProperty("--accent-soft", `rgb(${accentRgb} / 0.14)`);
  root.style.setProperty("--accent-secondary-soft", `rgb(${accent2Rgb} / 0.14)`);

  // Browser worker pages rely on their own var naming.
  root.style.setProperty("--bg", resolved.theme === "light" ? "#f6f8ff" : "#09111b");
  root.style.setProperty("--bg-top", resolved.theme === "light" ? "#ffffff" : "#0b1422");
  root.style.setProperty("--panel", resolved.theme === "light" ? "rgba(255, 255, 255, 0.82)" : "rgba(14, 24, 40, 0.84)");
  root.style.setProperty("--panel-strong", resolved.theme === "light" ? "rgba(255, 255, 255, 0.92)" : "rgba(7, 14, 24, 0.82)");
  root.style.setProperty("--line", resolved.theme === "light" ? "rgba(24, 44, 82, 0.14)" : "rgba(160, 193, 255, 0.14)");
  root.style.setProperty("--line-strong", resolved.theme === "light" ? "rgba(24, 44, 82, 0.22)" : "rgba(160, 193, 255, 0.24)");
  root.style.setProperty("--text", resolved.theme === "light" ? "#0b1422" : "#f5f7fb");
  root.style.setProperty("--muted", resolved.theme === "light" ? "#3a4a66" : "#9cb0d0");
  root.style.setProperty("--accent", resolved.palette.accent);
  root.style.setProperty("--accent-strong", resolved.palette.accent_secondary);

  // Remote bridge pages use sst vars.
  root.style.setProperty("--sst-bg", resolved.theme === "light" ? "#f6f8ff" : "#080a12");
  root.style.setProperty("--sst-panel", resolved.theme === "light" ? "rgba(255, 255, 255, 0.78)" : "rgba(12, 18, 32, 0.82)");
  root.style.setProperty("--sst-panel-strong", resolved.theme === "light" ? "rgba(255, 255, 255, 0.9)" : "rgba(16, 24, 42, 0.95)");
  root.style.setProperty("--sst-text", resolved.theme === "light" ? "#0b1422" : "#eef8ff");
  root.style.setProperty("--sst-muted", resolved.theme === "light" ? "#3a4a66" : "#91a4b8");
  root.style.setProperty("--sst-border", resolved.theme === "light" ? "rgba(24, 44, 82, 0.18)" : "rgba(120, 220, 255, 0.25)");
  root.style.setProperty("--sst-info", resolved.palette.accent);

  try {
    root.style.setProperty("color-scheme", resolved.theme);
  } catch (_error) {
    // ignore
  }

  return resolved;
}

export async function autoLoadAndApplyUiTheme(options = {}) {
  const targetDocument = options.targetDocument || document;
  try {
    const response = await fetch("/api/settings/load");
    const data = await response.json().catch(() => null);
    const payload = data?.payload || null;
    if (payload && typeof payload === "object") {
      return applyUiThemeFromConfigPayload(payload, targetDocument);
    }
  } catch (_error) {
    // best-effort
  }
  return applyUiThemeFromConfigPayload({}, targetDocument);
}

window.SSTUiTheme = {
  applyUiThemeFromConfigPayload,
  autoLoadAndApplyUiTheme,
};
