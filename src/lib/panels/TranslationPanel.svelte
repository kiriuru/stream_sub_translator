<script lang="ts">

  import { locale, t } from "../i18n";

  import { listRecommendedOpenAiModels } from "../api";

  import { LANGUAGES, PROVIDERS } from "../constants";

  import ProviderSelect from "../components/ProviderSelect.svelte";

  import {

    ensureLine,

    formatTranslationConfigError,

    getEnabledProviderNames,

    getLineCards,

    getLinesWithMissingSettings,

    getTranslationConfigErrors,

    getMissingProviderFields,

    getProviderFieldLabel,

    getProviderFieldPlaceholder,

    getProviderHintKey,

    getProviderSetting,

    getSlotDisplayLabel,

    getSlotNumber,

    nextAvailableSlot,

    normalizeDisplayOrder,

    normalizeProviderName,

    setProviderSetting,

  } from "../translation-helpers";

  import TranslationResults from "../components/TranslationResults.svelte";

  import type { ConfigPayload, TranslationLine, TranslationResultState } from "../types";



  export let config: ConfigPayload;

  export let translationResults: TranslationResultState | null = null;

  export let onChange: (next: ConfigPayload) => void;



  let selectedSlot = "translation_1";

  let settingsProvider = "";

  let newTargetLang = "en";

  let apiKeyVisible = false;

  let openAiModels: string[] = [];

  let openAiModelsLoading = false;

  let modelShowAll = false;

  let modelStatus = "";

  let lineValidationMessage = "";



  $: loc = $locale;

  $: tr = (key: string, vars?: Record<string, string | number>) => t(key, vars, loc);



  $: translation = config.translation || {};

  $: defaultProvider = normalizeProviderName(translation.provider);

  $: lineCards = getLineCards(config);

  $: translationConfigErrors = getTranslationConfigErrors(config, defaultProvider);

  $: selectedLine =

    lineCards.find((line) => line.slot_id === selectedSlot) ||

    lineCards[0] ||

    null;

  $: editingProvider = normalizeProviderName(

    settingsProvider || selectedLine?.provider || defaultProvider,

    defaultProvider,

  );

  $: providerMeta = PROVIDERS[editingProvider];

  $: providerSettings = (translation.provider_settings?.[editingProvider] || {}) as Record<string, unknown>;

  $: cache = (translation.cache || {}) as Record<string, unknown>;

  $: providerHint = tr(getProviderHintKey(editingProvider));

  $: enabledProviders = getEnabledProviderNames(config, defaultProvider);

  $: enabledProviderLabels = enabledProviders

    .map((name) => PROVIDERS[name]?.label || name)

    .join(", ");

  $: linesMissingSettings = getLinesWithMissingSettings(config, defaultProvider);

  $: providerStatusParts = [

    selectedLine

      ? tr("translation.provider_settings.scope.selected", {

          provider: providerMeta?.label || editingProvider,

          line: tr("translation.line.title", { number: getSlotNumber(selectedLine.slot_id) }),

        })

      : tr("translation.provider_settings.scope.default", {

          provider: providerMeta?.label || editingProvider,

          defaultProvider: PROVIDERS[defaultProvider]?.label || defaultProvider,

        }),

    enabledProviderLabels

      ? tr("translation.providers_in_use", { providers: enabledProviderLabels })

      : "",

  ].filter(Boolean);

  $: providerStatusText = providerStatusParts.join(" ");

  $: visibleOpenAiModels = modelShowAll

    ? openAiModels

    : openAiModels.filter((id) =>

        ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4.1"].includes(id),

      );



  function emit(next: ConfigPayload) {

    onChange(next);

  }



  function patchTranslation(partial: Record<string, unknown>) {

    emit({ ...config, translation: { ...translation, ...partial } });

  }



  function mutate(mutator: (draft: ConfigPayload) => void) {

    const draft = structuredClone(config);

    mutator(draft);

    emit(draft);

  }



  function fieldLabel(field: string): string {

    return getProviderFieldLabel(editingProvider, field, (key) => tr(key));

  }



  function updateProviderSetting(field: string, value: string) {

    const settings = { ...(translation.provider_settings || {}) };

    settings[editingProvider] = setProviderSetting(editingProvider, providerSettings, field, value);

    patchTranslation({ provider_settings: settings });

  }



  function patchCache(partial: Record<string, unknown>) {

    patchTranslation({ cache: { ...cache, ...partial } });

  }



  function targetLangTakenByOther(slotId: string, targetLang: string, draft: ConfigPayload): boolean {
    const normalized = String(targetLang || "").trim().toLowerCase();
    if (!normalized) return false;
    return getLineCards(draft).some(
      (line) =>
        line.slot_id !== slotId &&
        line.enabled &&
        String(line.target_lang || "").trim().toLowerCase() === normalized,
    );
  }



  function updateLine(slotId: string, patch: Partial<TranslationLine>) {
    if (patch.target_lang) {
      const draft = structuredClone(config);
      if (targetLangTakenByOther(slotId, String(patch.target_lang), draft)) {
        lineValidationMessage = tr("translation.validation.duplicate_target", {
          langs: String(patch.target_lang).toUpperCase(),
        });
        return;
      }
    }
    lineValidationMessage = "";

    mutate((draft) => {

      const line = ensureLine(draft, slotId, { provider: defaultProvider });

      Object.assign(line, patch);

      if (patch.target_lang) line.label = String(patch.label || patch.target_lang.toUpperCase());

      if (!draft.translation) draft.translation = {};

      draft.translation.target_languages = getLineCards(draft)

        .filter((row) => row.enabled)

        .map((row) => row.target_lang);

    });

  }



  function toggleLineEnabled(slotId: string, enabled: boolean) {

    mutate((draft) => {

      const line = ensureLine(draft, slotId, { provider: defaultProvider });

      line.enabled = enabled;

      const order = [...(draft.subtitle_output?.display_order || [])];

      if (enabled) {

        draft.subtitle_output = {

          ...(draft.subtitle_output || {}),

          display_order: normalizeDisplayOrder([...order, slotId]),

        };

      } else {

        draft.subtitle_output = {

          ...(draft.subtitle_output || {}),

          display_order: order.filter((item) => item !== slotId),

        };

      }

      draft.translation = draft.translation || {};

      draft.translation.target_languages = getLineCards(draft)

        .filter((row) => row.enabled)

        .map((row) => row.target_lang);

    });

  }



  function addLine() {

    const slotId = nextAvailableSlot(config);

    if (!slotId) return;

    const targetLang = newTargetLang || "en";

    if (targetLangTakenByOther(slotId, targetLang, config)) {
      lineValidationMessage = tr("translation.validation.duplicate_target", {
        langs: targetLang.toUpperCase(),
      });
      return;
    }
    lineValidationMessage = "";

    mutate((draft) => {

      ensureLine(draft, slotId, {

        enabled: true,

        target_lang: targetLang,

        provider: defaultProvider,

        label: targetLang.toUpperCase(),

      });

      draft.subtitle_output = {

        ...(draft.subtitle_output || {}),

        display_order: normalizeDisplayOrder([...(draft.subtitle_output?.display_order || []), slotId]),

      };

    });

    selectedSlot = slotId;

  }



  function removeSelectedLine() {
    if (!selectedLine || lineCards.length <= 1) return;
    const slotId = selectedLine.slot_id;
    const draft = structuredClone(config);
    draft.translation = draft.translation || {};
    draft.translation.lines = (draft.translation.lines || []).filter((line) => line.slot_id !== slotId);
    draft.subtitle_output = {
      ...(draft.subtitle_output || {}),
      display_order: (draft.subtitle_output?.display_order || []).filter((item) => item !== slotId),
    };
    const remaining = getLineCards(draft);
    selectedSlot = remaining[0]?.slot_id || "translation_1";
    emit(draft);
  }



  function selectLine(slotId: string, event: MouseEvent) {

    const target = event.target;

    if (target instanceof Element && target.closest("select, input, textarea, button, label, a")) {

      return;

    }

    selectedSlot = slotId;

    settingsProvider = "";

    apiKeyVisible = false;

  }



  function changeDefaultProvider(next: string) {

    patchTranslation({ provider: normalizeProviderName(next, defaultProvider) });

    settingsProvider = "";

  }



  function changeSettingsProvider(next: string) {

    const provider = normalizeProviderName(next, defaultProvider);

    if (selectedLine) {

      updateLine(selectedLine.slot_id, { provider });

      settingsProvider = "";

      return;

    }

    settingsProvider = provider;

    apiKeyVisible = false;

  }



  function toggleApiKeyVisible() {

    apiKeyVisible = !apiKeyVisible;

  }



  async function loadOpenAiModels() {

    if (editingProvider !== "openai") return;

    modelStatus = tr("translation.models.loading_recommended");

    openAiModelsLoading = true;

    try {

      const data = await listRecommendedOpenAiModels();

      openAiModels = Array.isArray(data.models) ? data.models.map((item) => String(item)) : [];

      modelStatus = tr("translation.models.list_loaded", { count: openAiModels.length });

    } catch (error) {

      const message = error instanceof Error ? error.message : String(error);

      modelStatus = tr("translation.models.error", { message });

    } finally {

      openAiModelsLoading = false;

    }

  }



  function pickOpenAiModel(modelId: string) {

    if (!modelId) return;

    updateProviderSetting("model", modelId);

  }

</script>



<section class="translation-layout bento-root stack">

  <div class="translation-top bento-grid">

    <article class="glass-panel panel-padding translation-lines-panel bento-tile stack">

      <div class="section-heading">

        <div>

          <p class="eyebrow">{tr("translation.lines.eyebrow")}</p>

          <h2>{tr("translation.lines.title")}</h2>

        </div>

      </div>



      <label class="checkbox-row">

        <input

          type="checkbox"

          checked={translation.enabled === true}

          on:change={(e) => patchTranslation({ enabled: (e.currentTarget as HTMLInputElement).checked })}

        />

        <span>{tr("translation.enable")}</span>

      </label>



      <div class="toggle-row">

        <label class="checkbox-row">

          <input

            type="checkbox"

            checked={cache.enabled !== false}

            on:change={(e) => patchCache({ enabled: (e.currentTarget as HTMLInputElement).checked })}

          />

          <span>{tr("translation.cache.enable")}</span>

        </label>

        <label class="checkbox-row">

          <input

            type="checkbox"

            checked={cache.persist !== false}

            on:change={(e) => patchCache({ persist: (e.currentTarget as HTMLInputElement).checked })}

          />

          <span>{tr("translation.cache.persist")}</span>

        </label>

      </div>



      <div class="translation-line-toolbar">

        <label class="stack-field grow">

          <span>{tr("translation.lines.new_target")}</span>

          <select class="control" bind:value={newTargetLang}>

            {#each LANGUAGES as lang}

              <option value={lang.code}>{lang.label}</option>

            {/each}

          </select>

        </label>

      </div>



      <div class="translation-action-grid">

        <button type="button" class="btn" disabled={!nextAvailableSlot(config)} on:click={addLine}>

          {tr("translation.add_line")}

        </button>

        <button

          type="button"

          class="btn btn-ghost"

          disabled={!selectedLine || lineCards.length <= 1}

          on:click={removeSelectedLine}

        >

          {tr("translation.remove_selected")}

        </button>

      </div>



      <p class="muted translation-lines-note">{tr("translation.lines.note")}</p>

      {#if lineValidationMessage}
        <p class="translation-validation error" role="alert">{lineValidationMessage}</p>
      {:else if translationConfigErrors.length > 0}
        <div class="translation-validation warn" role="status">
          {#each translationConfigErrors as errorKey}
            <p>{formatTranslationConfigError(errorKey, tr)}</p>
          {/each}
        </div>
      {/if}

      <ul class="ordered-list translation-line-list">

        {#each lineCards as line}

          {@const slotId = line.slot_id}

          {@const providerName = normalizeProviderName(line.provider, defaultProvider)}

          {@const missing = line.enabled ? getMissingProviderFields(providerName, translation.provider_settings?.[providerName] || {}) : []}

          <li>

            <div

              class="translation-line-card"

              class:active={selectedSlot === slotId}

              role="button"

              tabindex="0"

              on:click={(e) => selectLine(slotId, e)}

              on:keydown={(e) => {

                if (e.key === "Enter" || e.key === " ") selectLine(slotId, e as unknown as MouseEvent);

              }}

            >

              <div class="translation-line-head">

                <div class="translation-line-title-block">

                  <div class="translation-line-title-row">

                    <strong class="translation-line-title">{tr("translation.line.title", { number: getSlotNumber(slotId) })}</strong>

                    <span class="translation-line-slot">{getSlotDisplayLabel(slotId, loc)}</span>

                  </div>

                  <p class="muted translation-line-summary">

                    {String(line.target_lang || "en").toUpperCase()} · {PROVIDERS[providerName]?.label || providerName}

                  </p>

                </div>

                <div class="translation-line-badges">

                  <span class="translation-line-badge" data-tone={line.enabled ? "ready" : "muted"}>

                    {line.enabled ? tr("translation.line.state.enabled") : tr("translation.line.state.disabled")}

                  </span>

                  {#if missing.length}

                    <span class="translation-line-badge" data-tone="warn">{tr("translation.line.missing_settings.short")}</span>

                  {/if}

                </div>

              </div>



              <label class="checkbox-row translation-line-enabled">

                <input

                  type="checkbox"

                  checked={line.enabled}

                  on:change={(e) => toggleLineEnabled(slotId, (e.currentTarget as HTMLInputElement).checked)}

                />

                <span>{tr("translation.line.enabled")}</span>

              </label>



              <div class="translation-line-fields">

                <label class="stack-field">

                  <span>{tr("translation.line.target_lang")}</span>

                  <select

                    class="control"

                    value={line.target_lang}

                    on:change={(e) =>

                      updateLine(slotId, { target_lang: (e.currentTarget as HTMLSelectElement).value })}

                  >

                    {#each LANGUAGES as lang}

                      <option value={lang.code}>{lang.label}</option>

                    {/each}

                  </select>

                </label>

                <label class="stack-field">

                  <span>{tr("translation.line.provider")}</span>

                  <ProviderSelect

                    value={providerName}

                    onChange={(next) => updateLine(slotId, { provider: next })}

                  />

                </label>

              </div>



              {#if missing.length}

                <p class="muted translation-line-note">

                  {tr("translation.line.missing_settings", {

                    fields: missing

                      .map((field) => getProviderFieldLabel(providerName, field, (key) => tr(key)))

                      .join(", "),

                  })}

                </p>

              {/if}

            </div>

          </li>

        {/each}

      </ul>

    </article>



    <article class="glass-panel panel-padding translation-provider-panel stack">

      <div class="section-heading translation-provider-heading">

        <div>

          <p class="eyebrow">{tr("translation.eyebrow")}</p>

          <h2>{tr("translation.provider_settings.title")}</h2>

        </div>

      </div>

      <div class="translation-provider-picks">

        <label class="stack-field translation-provider-field">

          <span>{tr("translation.default_provider")}</span>

          <ProviderSelect value={defaultProvider} onChange={changeDefaultProvider} />

        </label>

        <label class="stack-field translation-provider-field">

          <span>{tr("translation.provider_settings.selector")}</span>

          <ProviderSelect value={editingProvider} onChange={changeSettingsProvider} />

        </label>

      </div>

      <p class="muted translation-provider-hint">{tr("translation.provider_settings.helper")}</p>

      {#if linesMissingSettings.length}

        <p class="translation-provider-warning">{tr("translation.provider_settings.warning")}</p>

      {/if}

      <div class="translation-provider-settings-heading">

        <h3>{tr("translation.provider_settings.for", { provider: providerMeta?.label || editingProvider })}</h3>

        <p class="muted translation-provider-meta-hint">{providerHint}</p>

      </div>

      {#each providerMeta.fields as field}

        {#if field === "custom_prompt"}

          <label class="stack-field translation-provider-field">

            <span>{fieldLabel(field)}</span>

            <textarea

              class="control translation-prompt"

              rows="4"

              placeholder={tr("translation.custom_prompt")}

              value={getProviderSetting(editingProvider, providerSettings, field)}

              on:input={(e) => updateProviderSetting(field, (e.currentTarget as HTMLTextAreaElement).value)}

            ></textarea>

          </label>

        {:else if field === "api_key"}

          <div class="translation-secret-row">

            <label class="stack-field translation-provider-field grow">

              <span>{fieldLabel(field)}</span>

              <input

                class="control"

                type={apiKeyVisible ? "text" : "password"}

                placeholder={getProviderFieldPlaceholder(editingProvider, field) || fieldLabel(field)}

                value={getProviderSetting(editingProvider, providerSettings, field)}

                on:input={(e) => updateProviderSetting(field, (e.currentTarget as HTMLInputElement).value)}

              />

            </label>

            <button type="button" class="btn btn-ghost secret-toggle" on:click={toggleApiKeyVisible}>

              {apiKeyVisible ? tr("security.hide") : tr("security.show")}

            </button>

          </div>

        {:else if field === "model" && editingProvider === "openai"}

          <div class="translation-model-row">

            <label class="stack-field translation-provider-field grow">

              <span>{fieldLabel(field)}</span>

              <input

                class="control"

                type="text"

                placeholder={getProviderFieldPlaceholder(editingProvider, field) || fieldLabel(field)}

                value={getProviderSetting(editingProvider, providerSettings, field)}

                on:input={(e) => updateProviderSetting(field, (e.currentTarget as HTMLInputElement).value)}

              />

            </label>

            <button

              type="button"

              class="btn btn-ghost"

              disabled={openAiModelsLoading}

              on:click={loadOpenAiModels}

            >

              {tr("translation.model.load_recommended")}

            </button>

          </div>

          {#if openAiModels.length}

            <div class="translation-model-picker">

              <label class="stack-field translation-provider-field grow">

                <span>{tr("translation.model.pick")}</span>

                <select

                  class="control"

                  value={getProviderSetting(editingProvider, providerSettings, "model")}

                  on:change={(e) => pickOpenAiModel((e.currentTarget as HTMLSelectElement).value)}

                >

                  {#each visibleOpenAiModels as modelId}

                    <option value={modelId}>{modelId}</option>

                  {/each}

                </select>

              </label>

              <label class="checkbox-row">

                <input type="checkbox" bind:checked={modelShowAll} />

                <span>{tr("translation.model.show_all")}</span>

              </label>

            </div>

          {/if}

          {#if modelStatus}

            <p class="muted translation-model-status">{modelStatus}</p>

          {/if}

        {:else}

          <label class="stack-field translation-provider-field">

            <span>{fieldLabel(field)}</span>

            <input

              class="control"

              type="text"

              placeholder={getProviderFieldPlaceholder(editingProvider, field) || fieldLabel(field)}

              value={getProviderSetting(editingProvider, providerSettings, field)}

              on:input={(e) => updateProviderSetting(field, (e.currentTarget as HTMLInputElement).value)}

            />

          </label>

        {/if}

      {/each}

      <p class="muted translation-provider-status">{providerStatusText}</p>

    </article>

  </div>



  {#if translationResults}

    <div class="translation-bottom bento-span-full">

      <article class="glass-panel panel-padding bento-tile">

        <TranslationResults
          results={translationResults}
          showPanel={config.ui?.show_translation_results !== false}
          onShowPanelChange={(enabled) =>
            onChange({
              ...config,
              ui: { ...(config.ui || {}), show_translation_results: enabled },
            })}
        />

      </article>

    </div>

  {/if}



  <p class="muted dashboard-prose-hint">{tr("translation.order.note")}</p>

</section>



<style>

  .translation-top {

    align-items: start;

  }

  .translation-provider-heading {
    margin-bottom: 0;
  }

  .translation-provider-panel {
    align-self: start;
    gap: var(--space-3);
  }

  .translation-provider-picks {
    display: grid;
    gap: var(--space-3);
  }

  .translation-provider-field > span {
    font-size: 13px;
    line-height: 1.35;
  }

  .translation-provider-field .control {
    width: 100%;
    min-height: 40px;
    max-height: 40px;
    font-size: 13px;
  }

  .translation-provider-field .translation-prompt {
    min-height: 96px;
    max-height: none;
    resize: vertical;
  }

  .translation-provider-hint {
    margin: 0;
    font-size: 12px;
    line-height: 1.45;
  }

  .translation-provider-settings-heading h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }

  .translation-provider-meta-hint {
    margin: 6px 0 0;
    font-size: 12px;
    line-height: 1.45;
  }

  .translation-provider-warning {
    margin: 0;
    color: var(--warning, #f5c542);
    font-size: 12px;
    line-height: 1.45;
  }

  .translation-provider-status,
  .translation-model-status {
    margin: 0;
    font-size: 12px;
    line-height: 1.45;
  }

  .translation-secret-row,
  .translation-model-row,
  .translation-model-picker {
    display: flex;
    align-items: end;
    gap: var(--space-2);
  }

  .translation-secret-row .grow,
  .translation-model-row .grow,
  .translation-model-picker .grow {
    flex: 1;
    min-width: 0;
  }

  .secret-toggle {
    flex-shrink: 0;
    min-height: 40px;
  }



  .toggle-row {

    display: flex;

    flex-wrap: wrap;

    gap: var(--space-3);

  }



  .translation-line-toolbar {

    display: flex;

    gap: var(--space-3);

  }



  .grow {

    flex: 1;

  }



  .translation-action-grid {

    display: grid;

    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));

    gap: var(--space-2);

  }



  .translation-lines-note {

    margin: 0;

  }



  .translation-line-list {

    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));

    gap: var(--space-3);

  }



  .translation-line-card {

    display: grid;

    gap: var(--space-3);

    padding: var(--space-4);

    border: 1px solid var(--line-subtle);

    border-radius: var(--radius-md);

    background: var(--bg-control);

    cursor: pointer;

  }



  .translation-line-card.active {

    border-color: color-mix(in srgb, var(--accent) 52%, transparent);

    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 18%, transparent);

  }

  .translation-line-card:focus-visible {
    outline: none;
    box-shadow: var(--shadow-focus);
  }

  .translation-validation {
    margin: 0;
    padding: var(--space-3);
    border-radius: var(--radius-md);
    font-size: 13px;
    line-height: 1.45;
  }

  .translation-validation.warn {
    border: 1px solid color-mix(in srgb, var(--warning, #ffbf57) 45%, transparent);
    background: color-mix(in srgb, var(--warning, #ffbf57) 10%, transparent);
    color: var(--text-primary);
  }

  .translation-validation.error {
    border: 1px solid color-mix(in srgb, var(--danger, #ff6b6b) 45%, transparent);
    background: color-mix(in srgb, var(--danger, #ff6b6b) 10%, transparent);
    color: var(--text-primary);
  }



  .translation-line-head {

    display: flex;

    align-items: flex-start;

    justify-content: space-between;

    gap: var(--space-3);

  }



  .translation-line-title-block {

    min-width: 0;

  }



  .translation-line-title-row {

    display: flex;

    align-items: baseline;

    justify-content: space-between;

    gap: var(--space-3);

  }



  .translation-line-title {

    font-size: 16px;

  }



  .translation-line-slot {

    color: var(--text-tertiary);

    font-family: var(--font-mono);

    font-size: 12px;

  }



  .translation-line-summary {

    margin: var(--space-2) 0 0;

    font-size: 13px;

  }



  .translation-line-badges {

    display: flex;

    flex-wrap: wrap;

    justify-content: flex-end;

    gap: var(--space-2);

  }



  .translation-line-badge {

    border: 1px solid var(--line-strong, var(--line-subtle));

    border-radius: 999px;

    padding: 6px 10px;

    font-size: 11px;

    line-height: 1;

    letter-spacing: 0.04em;

    text-transform: uppercase;

    color: var(--text-secondary);

  }



  .translation-line-badge[data-tone="ready"] {

    color: var(--text-positive);

    border-color: color-mix(in srgb, var(--text-positive) 28%, transparent);

  }



  .translation-line-badge[data-tone="muted"] {

    color: var(--text-tertiary);

  }



  .translation-line-badge[data-tone="warn"] {

    color: var(--sst-warning, #ffd166);

    border-color: color-mix(in srgb, #ffd166 32%, transparent);

  }



  .translation-line-enabled {

    width: fit-content;

  }



  .translation-line-fields {

    display: grid;

    gap: var(--space-3);

    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));

  }



  .translation-line-note {

    margin: 0;

    color: var(--sst-warning, #ffd166);

  }





  .checkbox-row {

    display: flex;

    flex-direction: row;

    align-items: center;

    gap: 8px;

  }

</style>


