<script lang="ts">
  import { locale, t } from "../i18n";
  import type { VersionInfo } from "../types";

  export let versionInfo: VersionInfo | null = null;
  export let visible = false;
  export let onClose: () => void = () => {};
  export let onDownload: (url: string) => void = () => {};

  $: loc = $locale;
  $: tr = (key: string, vars?: Record<string, string | number>) => t(key, vars, loc);
  $: sync = versionInfo?.sync;
  $: current = versionInfo?.current_version || versionInfo?.version || "";
  $: latest = sync?.latest_known_version || "";
  function releaseUrlForVersion(
    repo: string | null | undefined,
    version: string,
  ): string {
    const normalized = version.trim().replace(/^v/i, "");
    if (!normalized || !repo?.trim()) {
      return "";
    }
    return `https://github.com/${repo.trim()}/releases/tag/v${normalized}`;
  }

  $: releaseUrl =
    sync?.release_url
    || releaseUrlForVersion(
      typeof sync?.github_repo === "string" ? sync.github_repo : "",
      latest,
    );
</script>

{#if visible && sync?.update_available && latest}
  <div class="update-banner glass-panel" role="status" aria-live="polite">
    <p class="update-banner__text">
      {tr("updates.banner.message", { current, latest })}
    </p>
    <div class="update-banner__actions">
      <button type="button" class="btn" on:click={onClose}>
        {tr("updates.banner.close")}
      </button>
      <button
        type="button"
        class="btn btn-primary"
        disabled={!releaseUrl}
        on:click={() => releaseUrl && onDownload(releaseUrl)}
      >
        {tr("updates.banner.download")}
      </button>
    </div>
  </div>
{/if}

<style>
  .update-banner {
    position: fixed;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1200;
    display: flex;
    align-items: center;
    gap: var(--space-4);
    max-width: min(720px, calc(100vw - 24px));
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-lg);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
    border-color: rgba(255, 191, 87, 0.45);
  }

  .update-banner__text {
    margin: 0;
    flex: 1;
    font-size: 13px;
    line-height: 1.45;
    color: var(--text-primary);
  }

  .update-banner__actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
  }

  @media (max-width: 640px) {
    .update-banner {
      flex-direction: column;
      align-items: stretch;
    }

    .update-banner__actions {
      justify-content: flex-end;
    }
  }
</style>
