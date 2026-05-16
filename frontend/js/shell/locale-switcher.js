export function initializeLocaleSwitcher(actions) {
  const selects = [...document.querySelectorAll("#ui-language-select, #ui-language-select-settings")];
  if (!selects.length) {
    return () => {};
  }

  const applyCurrentLocale = () => {
    const locale = window.I18n?.getLocale?.() || "en";
    selects.forEach((select) => {
      select.value = locale;
    });
  };

  const onChange = (event) => {
    actions.setUiLanguage(event.target?.value || "en");
    actions.saveCurrentConfig();
  };

  selects.forEach((select) => select.addEventListener("change", onChange));
  applyCurrentLocale();

  return () => {
    selects.forEach((select) => select.removeEventListener("change", onChange));
  };
}
