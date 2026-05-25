from __future__ import annotations

import json


def build_handoff_resume_html(title: str, *, locale: str) -> str:
    """Minimal splash after venv re-exec — profile was already chosen on the first process."""
    normalized_locale = "ru" if str(locale or "").strip().lower() == "ru" else "en"
    title_escaped = json.dumps(title)
    status = (
        "Возобновление локального распознавания…"
        if normalized_locale == "ru"
        else "Resuming local speech recognition…"
    )
    subtitle = (
        "Завершаем установку окружения и запуск backend в venv Python."
        if normalized_locale == "ru"
        else "Finishing environment setup and starting the backend in venv Python."
    )
    log_title = "Журнал запуска" if normalized_locale == "ru" else "Startup log"
    return f"""<!doctype html>
<html lang="{normalized_locale}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #09111b;
        --panel: rgba(14, 24, 40, 0.92);
        --line: rgba(160, 193, 255, 0.18);
        --text: #f5f7fb;
        --muted: #9cb0d0;
        --accent: #6cc7ff;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        padding: 10px;
        font-family: "Segoe UI", Tahoma, sans-serif;
        background:
          radial-gradient(circle at top, rgba(108, 199, 255, 0.14), transparent 40%),
          linear-gradient(180deg, #0b1422 0%, var(--bg) 100%);
        color: var(--text);
      }}
      .splash {{
        width: 100%;
        margin: 0;
        padding: 20px 22px 16px;
        border-radius: 20px;
        border: 1px solid var(--line);
        background: var(--panel);
        box-shadow: 0 18px 56px rgba(0, 0, 0, 0.32);
      }}
      .eyebrow {{
        margin: 0 0 8px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 11px;
        color: var(--accent);
      }}
      h1 {{ margin: 0; font-size: 24px; line-height: 1.15; }}
      p {{ margin: 10px 0 0; color: var(--muted); line-height: 1.55; font-size: 14px; }}
      .loader {{
        display: grid;
        grid-template-columns: 16px 1fr;
        gap: 12px;
        margin-top: 16px;
      }}
      .status {{ margin: 0; color: #dce7ff; font-size: 13px; }}
      .log-panel {{
        margin-top: 14px;
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid rgba(160, 193, 255, 0.12);
        background: rgba(6, 12, 20, 0.72);
      }}
      .log-title {{
        margin: 0 0 6px;
        color: var(--muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.14em;
      }}
      #dev-log {{
        width: 100%;
        min-height: 56px;
        max-height: 140px;
        overflow: auto;
        white-space: pre-wrap;
        font-family: Consolas, "Cascadia Mono", monospace;
        font-size: 12px;
        line-height: 1.45;
        color: #d7e5ff;
        border: 0;
        background: transparent;
        resize: none;
        padding: 0;
      }}
      .spinner {{
        width: 16px;
        height: 16px;
        border: 2px solid rgba(255, 255, 255, 0.16);
        border-top-color: var(--accent);
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }}
      @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
  </head>
  <body>
    <main class="splash">
      <p class="eyebrow">Desktop Launcher</p>
      <h1 id="app-title"></h1>
      <p>{subtitle}</p>
      <div class="loader">
        <div class="spinner" aria-hidden="true"></div>
        <p id="status-line" class="status">{status}</p>
      </div>
      <section class="log-panel">
        <p class="log-title">{log_title}</p>
        <textarea id="dev-log" readonly spellcheck="false">launcher: resuming after venv handoff</textarea>
      </section>
    </main>
    <script>
      const APP_TITLE = {title_escaped};
      document.getElementById("app-title").textContent = APP_TITLE;
      window.__sstDesktopLog = function (message) {{
        const el = document.getElementById("dev-log");
        if (!el) return;
        el.value += `\\n${{message}}`;
        el.scrollTop = el.scrollHeight;
      }};
      window.__sstDesktopStatus = function (message, statusKey) {{
        const el = document.getElementById("status-line");
        if (!el) return;
        if (message) el.textContent = message;
      }};
    </script>
  </body>
</html>"""


def build_splash_html(
    title: str,
    *,
    locale: str,
    translations: dict[str, dict[str, str]],
    web_speech_only: bool = False,
) -> str:
    normalized_locale = "ru" if str(locale or "").strip().lower() == "ru" else "en"
    i18n_json = json.dumps(translations, ensure_ascii=False)
    title_escaped = json.dumps(title)
    body_class = "web-speech-only" if web_speech_only else ""
    initial_status_key = (
        "launcher.status.web_only_initial" if web_speech_only else "launcher.status.initial"
    )
    subtitle_key = "launcher.subtitle.web_only" if web_speech_only else "launcher.subtitle"
    return f"""<!doctype html>
<html lang="{normalized_locale}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #09111b;
        --panel: rgba(14, 24, 40, 0.92);
        --line: rgba(160, 193, 255, 0.18);
        --text: #f5f7fb;
        --muted: #9cb0d0;
        --accent: #6cc7ff;
        --button: rgba(108, 199, 255, 0.12);
        --button-active: rgba(108, 199, 255, 0.24);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        padding: 10px;
        font-family: "Segoe UI", Tahoma, sans-serif;
        background:
          radial-gradient(circle at top, rgba(108, 199, 255, 0.14), transparent 40%),
          linear-gradient(180deg, #0b1422 0%, var(--bg) 100%);
        color: var(--text);
      }}
      .splash {{
        width: 100%;
        margin: 0;
        padding: 20px 22px 16px;
        border-radius: 20px;
        border: 1px solid var(--line);
        background: var(--panel);
        box-shadow: 0 18px 56px rgba(0, 0, 0, 0.32);
      }}
      .splash-top {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
      }}
      .splash-brand {{ flex: 1 1 auto; min-width: 0; }}
      .locale-switcher {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        flex: 0 0 auto;
      }}
      .locale-switcher-label {{
        margin: 0;
        font-size: 11px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .locale-switch {{
        display: inline-flex;
        border-radius: 10px;
        border: 1px solid rgba(160, 193, 255, 0.22);
        overflow: hidden;
      }}
      .locale-btn {{
        appearance: none;
        border: 0;
        background: transparent;
        color: var(--muted);
        font-size: 12px;
        font-weight: 600;
        padding: 6px 10px;
        cursor: pointer;
      }}
      .locale-btn.active {{
        background: rgba(108, 199, 255, 0.22);
        color: var(--text);
      }}
      .eyebrow {{
        margin: 0 0 8px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 11px;
        color: var(--accent);
      }}
      h1 {{
        margin: 0;
        font-size: 28px;
        line-height: 1.1;
      }}
      p {{
        margin: 10px 0 0;
        color: var(--muted);
        line-height: 1.55;
        font-size: 14px;
      }}
      .loader {{
        display: grid;
        grid-template-columns: 16px 1fr;
        gap: 12px;
        margin-top: 16px;
      }}
      .status {{
        margin: 0;
        color: #dce7ff;
        font-size: 13px;
      }}
      .profile-panel {{
        margin-top: 16px;
        padding: 14px;
        border-radius: 16px;
        border: 1px solid rgba(160, 193, 255, 0.14);
        background: rgba(7, 14, 24, 0.84);
      }}
      .profile-title {{
        margin: 0 0 6px;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--muted);
      }}
      .profile-hint {{
        margin: 0 0 12px;
        color: var(--muted);
        font-size: 13px;
      }}
      .profile-actions {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }}
      .profile-secondary {{
        margin-top: 12px;
        border-top: 1px solid rgba(160, 193, 255, 0.1);
        padding-top: 10px;
      }}
      .profile-secondary summary {{
        cursor: pointer;
        color: var(--muted);
        font-size: 12px;
        font-weight: 600;
      }}
      .profile-secondary[open] summary {{ margin-bottom: 10px; }}
      .profile-secondary-actions {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }}
      .profile-button {{
        appearance: none;
        border: 1px solid rgba(160, 193, 255, 0.18);
        border-radius: 14px;
        background: var(--button);
        color: var(--text);
        padding: 12px;
        text-align: left;
        cursor: pointer;
      }}
      .profile-button:hover {{ border-color: rgba(124, 227, 173, 0.36); }}
      .profile-button.active {{
        background: var(--button-active);
        border-color: rgba(124, 227, 173, 0.42);
      }}
      .profile-button[data-mode="browser_google"].active {{
        border-color: rgba(108, 199, 255, 0.46);
      }}
      .profile-button strong {{
        display: block;
        font-size: 14px;
        margin-bottom: 4px;
      }}
      .profile-button small {{
        display: block;
        color: var(--muted);
        line-height: 1.4;
        font-size: 12px;
      }}
      .profile-button-minimal {{ padding: 10px 12px; }}
      .profile-button-minimal strong {{ font-size: 13px; }}
      .log-panel {{
        margin-top: 14px;
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid rgba(160, 193, 255, 0.12);
        background: rgba(6, 12, 20, 0.72);
      }}
      .log-title {{
        margin: 0 0 6px;
        color: var(--muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.14em;
      }}
      #dev-log {{
        width: 100%;
        min-height: 56px;
        max-height: 112px;
        overflow: auto;
        white-space: pre-wrap;
        font-family: Consolas, "Cascadia Mono", monospace;
        font-size: 12px;
        line-height: 1.45;
        color: #d7e5ff;
        border: 0;
        background: transparent;
        resize: none;
        padding: 0;
      }}
      .splash-footer {{
        margin-top: 12px;
        text-align: center;
        font-size: 11px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: rgba(156, 176, 208, 0.92);
      }}
      .spinner {{
        width: 16px;
        height: 16px;
        border: 2px solid rgba(255, 255, 255, 0.16);
        border-top-color: var(--accent);
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }}
      @media (max-width: 760px) {{
        .profile-actions {{ grid-template-columns: 1fr; }}
        .splash-top {{ flex-direction: column; }}
      }}
      @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
      body.web-speech-only .profile-panel {{
        display: none;
      }}
    </style>
  </head>
  <body class="{body_class}">
    <main class="splash">
      <div class="splash-top">
        <motion.div class="splash-brand">
          <p class="eyebrow" data-i18n="launcher.eyebrow">Desktop Launcher</p>
          <h1 id="app-title"></h1>
          <p data-i18n="{subtitle_key}">Preparing...</p>
        </div>
        <motion.div class="locale-switcher">
          <p class="locale-switcher-label" data-i18n="language.label">Interface language</p>
          <motion.div class="locale-switch" role="group" aria-labelledby="locale-switcher-label">
            <button type="button" class="locale-btn" data-locale="en">EN</button>
            <button type="button" class="locale-btn" data-locale="ru">RU</button>
          </div>
        </motion.div>
      </motion.div>
      <motion.div class="loader">
        <motion.div class="spinner" aria-hidden="true"></motion.div>
        <motion.div>
          <p id="status-line" class="status" data-i18n="{initial_status_key}">Starting...</p>
        </motion.div>
      </motion.div>
      <section class="profile-panel">
        <p class="profile-title" data-i18n="launcher.profile.title">Runtime Profile</p>
        <p id="profile-hint" class="profile-hint" data-i18n="launcher.profile.hint_default">Choose how this desktop session should start.</p>
        <motion.div class="profile-actions">
          <button id="profile-browser" class="profile-button" data-mode="browser_google" type="button">
            <strong data-i18n="launcher.profile.quick_start">Quick Start</strong>
            <small data-i18n="launcher.profile.quick_start_hint">Web Speech only.</small>
          </button>
          <button id="profile-nvidia" class="profile-button" data-mode="nvidia" type="button">
            <strong data-i18n="launcher.profile.nvidia">NVIDIA GPU (CUDA)</strong>
            <small data-i18n="launcher.profile.nvidia_hint">Recommended for NVIDIA cards.</small>
          </button>
          <button id="profile-cpu" class="profile-button" data-mode="cpu" type="button">
            <strong data-i18n="launcher.profile.cpu">CPU-only</strong>
            <small data-i18n="launcher.profile.cpu_hint">Recommended for AMD, Intel, or no-GPU machines.</small>
          </button>
        </motion.div>
        <details class="profile-secondary">
          <summary data-i18n="launcher.profile.remote_modes">Remote modes</summary>
          <motion.div class="profile-secondary-actions">
            <button id="profile-remote-controller" class="profile-button profile-button-minimal" data-mode="remote_controller" type="button">
              <strong data-i18n="launcher.profile.remote_controller">Remote Controller</strong>
              <small data-i18n="launcher.profile.remote_controller_hint">Lightweight controller session.</small>
            </button>
            <button id="profile-remote-worker" class="profile-button profile-button-minimal" data-mode="remote_worker" type="button">
              <strong data-i18n="launcher.profile.remote_worker">Remote Worker</strong>
              <small data-i18n="launcher.profile.remote_worker_hint">Local AI worker with LAN bind.</small>
            </button>
          </motion.div>
        </details>
      </section>
      <section class="log-panel">
        <p class="log-title" data-i18n="launcher.log.title">Startup Dev Log</p>
        <textarea id="dev-log" readonly spellcheck="false">launcher: splash ready</textarea>
      </section>
      <motion.div class="splash-footer" data-i18n="launcher.footer">Powered by Kiriuru</motion.div>
    </main>
    <script>
      const APP_TITLE = {title_escaped};
      const SPLASH_I18N = {i18n_json};
      let splashLocale = {json.dumps(normalized_locale)};

      function splashTranslate(key) {{
        const catalog = SPLASH_I18N[splashLocale] || SPLASH_I18N.en || {{}};
        return catalog[key] || (SPLASH_I18N.en && SPLASH_I18N.en[key]) || key;
      }}

      function applySplashLocale(nextLocale) {{
        splashLocale = nextLocale === "ru" ? "ru" : "en";
        document.documentElement.lang = splashLocale;
        document.querySelectorAll("[data-i18n]").forEach((element) => {{
          const key = element.getAttribute("data-i18n");
          if (key) {{
            element.textContent = splashTranslate(key);
          }}
        }});
        document.querySelectorAll(".locale-btn").forEach((button) => {{
          button.classList.toggle("active", button.dataset.locale === splashLocale);
        }});
        const statusEl = document.getElementById("status-line");
        if (statusEl && statusEl.dataset.statusKey) {{
          statusEl.textContent = splashTranslate(statusEl.dataset.statusKey);
        }}
      }}

      window.__sstApplySplashLocale = function (nextLocale) {{
        applySplashLocale(nextLocale);
      }};

      window.__sstSetLaunchOptionPrompt = function (payload) {{
        const normalized = payload || {{}};
        const hintEl = document.getElementById("profile-hint");
        const selected = String(normalized.selected || "").toLowerCase();
        if (hintEl) {{
          hintEl.textContent = normalized.hint || splashTranslate("launcher.profile.hint_default");
        }}
        ["profile-browser", "profile-nvidia", "profile-cpu", "profile-remote-controller", "profile-remote-worker"].forEach((id) => {{
          const button = document.getElementById(id);
          if (!button) return;
          const mode = String(button.dataset.mode || "").toLowerCase();
          button.classList.toggle("active", mode === selected);
          button.disabled = Boolean(normalized.locked);
        }});
      }};

      window.__sstChooseLaunchOption = function (selection) {{
        if (!window.pywebview?.api?.choose_launch_mode) {{
          return;
        }}
        const normalized = String(selection || "").toLowerCase();
        const hintKey = normalized === "browser_google"
          ? "launcher.profile.applying_browser"
          : normalized === "remote_controller"
          ? "launcher.profile.applying_remote_controller"
          : normalized === "remote_worker"
          ? "launcher.profile.applying_remote_worker"
          : "launcher.profile.applying_local";
        window.__sstSetLaunchOptionPrompt({{ selected: normalized, locked: true, hint: splashTranslate(hintKey) }});
        window.pywebview.api.choose_launch_mode(normalized);
      }};

      window.__sstDesktopLog = function (message) {{
        const el = document.getElementById("dev-log");
        if (!el) return;
        el.value += `\\n${{message}}`;
        el.scrollTop = el.scrollHeight;
      }};

      window.__sstDesktopStatus = function (message, statusKey) {{
        const el = document.getElementById("status-line");
        if (!el) return;
        if (statusKey) {{
          el.dataset.statusKey = statusKey;
          el.textContent = splashTranslate(statusKey);
          return;
        }}
        delete el.dataset.statusKey;
        el.textContent = message;
      }};

      document.getElementById("app-title").textContent = APP_TITLE;
      document.querySelectorAll(".profile-button[data-mode]").forEach((button) => {{
        button.addEventListener("click", () => window.__sstChooseLaunchOption(button.dataset.mode));
      }});
      document.querySelectorAll(".locale-btn").forEach((button) => {{
        button.addEventListener("click", () => {{
          const next = button.dataset.locale === "ru" ? "ru" : "en";
          if (window.pywebview?.api?.set_ui_language) {{
            try {{
              const saved = window.pywebview.api.set_ui_language(next);
              applySplashLocale(saved || next);
            }} catch (_error) {{
              applySplashLocale(next);
            }}
            return;
          }}
          applySplashLocale(next);
        }});
      }});

      applySplashLocale(splashLocale);
    </script>
  </body>
</html>"""
