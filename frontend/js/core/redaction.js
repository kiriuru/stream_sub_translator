(function attachRedaction(globalScope) {
  const REDACTED_VALUE = "[redacted]";
  const SENSITIVE_KEYS = new Set([
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
    "credentials",
    "pair_code",
    "local_admin_token",
    "bearer",
  ]);
  const SENSITIVE_FRAGMENTS = [
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
    "pair_code",
    "local_admin_token",
    "bearer",
  ];
  const BEARER_PATTERN = /\bbearer\s+([^\s,;]+)/gi;
  const QUERY_PARAM_PATTERN = /\b(api_key|token|secret|password|authorization|credential|credentials|pair_code|local_admin_token|bearer)=([^&\s]+)/gi;

  function isSensitiveKey(key) {
    const normalized = String(key || "").trim().toLowerCase();
    if (!normalized) {
      return false;
    }
    if (SENSITIVE_KEYS.has(normalized)) {
      return true;
    }
    return SENSITIVE_FRAGMENTS.some((fragment) => normalized.includes(fragment));
  }

  function redactText(value) {
    const text = String(value || "");
    if (!text) {
      return text;
    }
    return text
      .replace(BEARER_PATTERN, "Bearer [redacted]")
      .replace(QUERY_PARAM_PATTERN, (_match, key) => `${key}=${REDACTED_VALUE}`);
  }

  function redactUrl(value) {
    const raw = String(value || "").trim();
    if (!raw) {
      return raw;
    }
    try {
      const url = new URL(raw, globalScope.location?.href || "http://127.0.0.1/");
      let changed = false;
      [...url.searchParams.keys()].forEach((key) => {
        if (!isSensitiveKey(key)) {
          return;
        }
        url.searchParams.set(key, REDACTED_VALUE);
        changed = true;
      });
      if (!changed) {
        return raw;
      }
      return url.toString();
    } catch (_error) {
      return redactText(raw);
    }
  }

  function redactValue(value, key) {
    if (isSensitiveKey(key)) {
      return REDACTED_VALUE;
    }
    if (Array.isArray(value)) {
      return value.map((item) => redactValue(item));
    }
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.entries(value).map(([childKey, childValue]) => [childKey, redactValue(childValue, childKey)]));
    }
    if (typeof value === "string") {
      const normalizedKey = String(key || "").trim().toLowerCase();
      if (normalizedKey === "endpoint") {
        const redactedUrl = redactUrl(value);
        if (redactedUrl !== value) {
          return redactedUrl;
        }
        if (value.toLowerCase().includes("secret")) {
          return REDACTED_VALUE;
        }
      }
      return redactText(value);
    }
    return value;
  }

  function redactObject(value) {
    return redactValue(value);
  }

  globalScope.SSTRedaction = {
    REDACTED_VALUE,
    isSensitiveKey,
    redactText,
    redactUrl,
    redactValue,
    redactObject,
  };
})(window);
