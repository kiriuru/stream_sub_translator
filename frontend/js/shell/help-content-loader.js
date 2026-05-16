const HELP_PARTIAL_URL = "/static/partials/dashboard-help-topics.html";

export async function loadDashboardHelpContent() {
  const root = document.querySelector("[data-help-content-mount]");
  if (!root) {
    return false;
  }
  if (root.querySelector("[data-help-topic-panel]")) {
    return true;
  }
  const response = await fetch(HELP_PARTIAL_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Help content failed (${response.status})`);
  }
  const html = await response.text();
  root.innerHTML = html.trim();
  return true;
}
