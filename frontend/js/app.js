// Legacy entry retained as a small compatibility shim.
// The dashboard now boots from /static/js/main.js as an ES module.

export async function bootLegacyDashboard() {
  const module = await import("./main.js");
  return module;
}
