<script lang="ts">
  import { onMount } from "svelte";
  import { locale, t } from "../i18n";
  import {
    buildCommandPaletteItems,
    filterCommandItems,
    isEditableTarget,
    type CommandPaletteHandlers,
    type CommandPaletteItem,
  } from "../command-palette";

  export let open = false;
  export let handlers: CommandPaletteHandlers;

  let query = "";
  let selectedIndex = 0;
  let actionError = "";
  let inputEl: HTMLInputElement | null = null;

  $: loc = $locale;
  $: tr = (key: string) => t(key, undefined, loc);
  $: allItems = buildCommandPaletteItems(handlers);
  $: filtered = filterCommandItems(allItems, query, tr);
  $: selectedIndex = Math.min(selectedIndex, Math.max(0, filtered.length - 1));

  function close() {
    open = false;
    query = "";
    selectedIndex = 0;
    actionError = "";
  }

  async function runItem(item: CommandPaletteItem) {
    actionError = "";
    try {
      await item.run();
      close();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      actionError = message;
      handlers.onError?.(message);
    }
  }

  function onWindowKeydown(event: KeyboardEvent) {
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();

    if (mod && key === "k") {
      event.preventDefault();
      open = !open;
      if (open) {
        queueMicrotask(() => inputEl?.focus());
      } else {
        close();
      }
      return;
    }

    if (mod && key === "s") {
      event.preventDefault();
      if (open) {
        const save = filtered.find((item) => item.id === "save");
        if (save) void runItem(save);
      } else {
        void handlers.save();
      }
      return;
    }

    if (mod && event.key === "Enter" && !isEditableTarget(event.target)) {
      event.preventDefault();
      void handlers.start();
      return;
    }

    if (!open) return;

    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, filtered.length - 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
    } else if (event.key === "Enter" && filtered[selectedIndex]) {
      event.preventDefault();
      void runItem(filtered[selectedIndex]);
    }
  }

  onMount(() => {
    const onOpen = () => {
      open = true;
      queueMicrotask(() => inputEl?.focus());
    };
    window.addEventListener("voicesub:open-command-palette", onOpen);
    return () => window.removeEventListener("voicesub:open-command-palette", onOpen);
  });

  $: if (open) {
    queueMicrotask(() => inputEl?.focus());
  }
</script>

<svelte:window on:keydown={onWindowKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="command-palette-overlay" role="presentation" on:click={close}>
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div
      class="command-palette command-palette-panel"
      role="dialog"
      aria-modal="true"
      aria-label={tr("command_palette.title")}
      tabindex="-1"
      on:click|stopPropagation
    >
      <div class="command-palette__search">
        <span class="command-palette__search-icon" aria-hidden="true">⌕</span>
        <input
          bind:this={inputEl}
          class="command-palette__input"
          type="search"
          placeholder={tr("command_palette.placeholder")}
          bind:value={query}
          on:keydown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter" && filtered[selectedIndex]) {
              e.preventDefault();
              void runItem(filtered[selectedIndex]);
            }
          }}
        />
        <kbd class="command-palette__kbd">Esc</kbd>
      </div>

      <div class="command-palette__results" role="listbox">
        {#each filtered as item, index (item.id)}
          <button
            type="button"
            class="command-palette__item"
            class:is-selected={index === selectedIndex}
            role="option"
            aria-selected={index === selectedIndex}
            on:click={() => void runItem(item)}
            on:mouseenter={() => {
              selectedIndex = index;
            }}
          >
            <span class="command-palette__label">{tr(item.labelKey)}</span>
            <span class="command-palette__meta">
              <span class="command-palette__group">{tr(item.groupKey)}</span>
              {#if item.shortcut}
                <kbd class="command-palette__kbd">{item.shortcut}</kbd>
              {/if}
            </span>
          </button>
        {:else}
          <p class="command-palette__empty muted">{tr("command_palette.no_results")}</p>
        {/each}
      </div>

      {#if actionError}
        <p class="command-palette__error save-status error">{actionError}</p>
      {/if}

      <div class="command-palette__footer muted">
        <kbd class="command-palette__kbd">↑↓</kbd> {tr("command_palette.navigate")}
        <kbd class="command-palette__kbd">↵</kbd> {tr("command_palette.select")}
      </div>
    </div>
  </div>
{/if}

<style>
  .command-palette-overlay {
    position: fixed;
    inset: 0;
    z-index: var(--z-command-palette);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 18vh var(--space-4) var(--space-4);
    background: rgba(0, 0, 0, 0.5);
  }

  .command-palette-panel {
    width: min(640px, 100%);
    padding: 0;
    overflow: hidden;
    background: var(--glass-2);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--glass-highlight), var(--glass-shadow);
  }

  @supports ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
    .command-palette-overlay {
      -webkit-backdrop-filter: blur(4px);
      backdrop-filter: blur(4px);
    }

    .command-palette-panel {
      -webkit-backdrop-filter: var(--glass-blur);
      backdrop-filter: var(--glass-blur);
    }
  }

  .command-palette__search {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4);
    border-bottom: 1px solid var(--glass-border);
  }

  .command-palette__search-icon {
    color: var(--text-tertiary);
    font-size: 18px;
  }

  .command-palette__input {
    flex: 1;
    border: none;
    background: transparent;
    color: var(--text-primary);
    font-size: 15px;
    outline: none;
  }

  .command-palette__input:focus-visible {
    box-shadow: var(--shadow-focus);
    border-radius: var(--radius-sm);
  }

  .command-palette__results {
    max-height: 360px;
    overflow-y: auto;
    padding: var(--space-2);
  }

  .command-palette__item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--text-primary);
    cursor: pointer;
    text-align: left;
    transition: background var(--duration-fast) var(--ease-out);
  }

  .command-palette__item:hover,
  .command-palette__item.is-selected,
  .command-palette__item:focus-visible {
    background: rgb(var(--ui-accent-rgb) / 0.1);
    outline: none;
    box-shadow: var(--shadow-focus);
    border-color: rgb(var(--ui-accent-rgb) / 0.22);
  }

  .command-palette__label {
    font-size: 14px;
    font-weight: 500;
  }

  .command-palette__meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
  }

  .command-palette__group {
    font-size: 11px;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .command-palette__kbd {
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border);
    background: var(--glass-inset);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .command-palette__empty {
    padding: var(--space-6);
    text-align: center;
  }

  .command-palette__error {
    margin: 0;
    padding: 0 var(--space-4) var(--space-2);
    font-size: 13px;
  }

  .command-palette__footer {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-top: 1px solid var(--glass-border);
    font-size: 12px;
  }

  @media (prefers-reduced-transparency: reduce) {
    .command-palette-overlay {
      -webkit-backdrop-filter: none;
      backdrop-filter: none;
      background: rgba(0, 0, 0, 0.72);
    }

    .command-palette-panel {
      -webkit-backdrop-filter: none;
      backdrop-filter: none;
      background: var(--glass-3);
    }
  }
</style>
