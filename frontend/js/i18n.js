(function () {
  const STORAGE_KEY = "sst.ui.language";
  const SUPPORTED = ["en", "ru", "ja", "ko", "zh"];

  const bundles = window.__SST_I18N_LOCALES || {};
  const dynamic = window.__SST_I18N_DYNAMIC || {};
  const catalogByLocale = {};

  function buildCatalog(english, pack, dynamicPack) {
    const merged = Object.assign({}, english, pack || {});
    if (dynamicPack && typeof dynamicPack === "object") {
      Object.assign(merged, dynamicPack);
    }
    return merged;
  }

  function buildEnglishCatalog() {
    return buildCatalog({}, bundles.en || {}, dynamic.en);
  }

  function getCatalog(code) {
    const locale = SUPPORTED.includes(code) ? code : "en";
    if (catalogByLocale[locale]) {
      return catalogByLocale[locale];
    }
    const english = catalogByLocale.en || buildEnglishCatalog();
    if (locale === "en") {
      catalogByLocale.en = english;
      return english;
    }
    catalogByLocale[locale] = buildCatalog(english, bundles[locale], dynamic[locale]);
    return catalogByLocale[locale];
  }

  if (!Object.keys(bundles.en || {}).length) {
    console.error(
      "[i18n] English locale bundle missing; load locales-bundle.js (or en.js) before i18n.js"
    );
  }

  function resolveBrowserLocale(tag) {
    const normalized = String(tag || "en").trim().toLowerCase();
    if (normalized.startsWith("ru")) {
      return "ru";
    }
    if (normalized.startsWith("ja")) {
      return "ja";
    }
    if (normalized.startsWith("ko")) {
      return "ko";
    }
    if (normalized.startsWith("zh")) {
      return "zh";
    }
    return "en";
  }

  function getInitialLocale() {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (SUPPORTED.includes(stored)) {
        return stored;
      }
    } catch (_error) {
      // ignore storage errors
    }
    const browserLang = String(window.navigator.language || "en").toLowerCase();
    const resolved = resolveBrowserLocale(browserLang);
    return SUPPORTED.includes(resolved) ? resolved : "en";
  }

  let locale = getInitialLocale();

  function humanizeKey(key) {
    const source = String(key || "").trim();
    if (!source) {
      return "";
    }
    const lastSegment = source.split(".").pop() || source;
    const words = lastSegment
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!words) {
      return source;
    }
    return words.charAt(0).toUpperCase() + words.slice(1);
  }

  function format(template, variables) {
    return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, key) => {
      if (!variables || typeof variables[key] === "undefined" || variables[key] === null) {
        return "";
      }
      return String(variables[key]);
    });
  }

  function translate(key, variables) {
    const selected = getCatalog(locale);
    const fallback = getCatalog("en");
    const template = Object.prototype.hasOwnProperty.call(selected, key)
      ? selected[key]
      : Object.prototype.hasOwnProperty.call(fallback, key)
        ? fallback[key]
        : humanizeKey(key);
    return format(template, variables);
  }

  function apply(root = document) {
    if (root === document) {
      document.documentElement.lang = locale;
    }
    root.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = translate(element.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      element.setAttribute("placeholder", translate(element.dataset.i18nPlaceholder));
    });
    root.querySelectorAll("[data-i18n-title]").forEach((element) => {
      element.setAttribute("title", translate(element.dataset.i18nTitle));
    });
    root.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", translate(element.dataset.i18nAriaLabel));
    });
  }

  function setLocale(nextLocale) {
    locale = SUPPORTED.includes(nextLocale) ? nextLocale : "en";
    getCatalog(locale);
    try {
      window.localStorage.setItem(STORAGE_KEY, locale);
    } catch (_error) {
      // ignore storage errors
    }
    apply(document);
    window.dispatchEvent(new CustomEvent("sst:locale-changed", { detail: { locale } }));
  }

  window.I18n = {
    supported: SUPPORTED.slice(),
    getLocale() {
      return locale;
    },
    setLocale,
    t: translate,
    apply,
    get translations() {
      const snapshot = {};
      for (const code of SUPPORTED) {
        snapshot[code] = getCatalog(code);
      }
      return snapshot;
    },
  };

  getCatalog(locale);
  try {
    apply(document);
  } catch (error) {
    console.error("[i18n] initial apply failed", error);
  }
})();
