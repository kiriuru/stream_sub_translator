import { describe, expect, it } from "vitest";
import {
  isUpdateBannerDismissedForVersion,
  shouldShowUpdateBanner,
} from "./update-banner-state";
import type { VersionInfo } from "./types";

describe("update-banner-state", () => {
  it("shows banner when remote 0.5.2 is newer than current 0.5.1", () => {
    const info: VersionInfo = {
      current_version: "0.5.1",
      sync: {
        update_available: true,
        latest_known_version: "0.5.2",
        github_repo: "kiriuru/VoiceSub",
      },
    };
    expect(shouldShowUpdateBanner(info, false)).toBe(true);
    expect(isUpdateBannerDismissedForVersion("0.5.2", "")).toBe(false);
  });

  it("hides banner when dismissed for the same latest version", () => {
    expect(isUpdateBannerDismissedForVersion("0.5.2", "0.5.2")).toBe(true);
    const info: VersionInfo = {
      sync: { update_available: true, latest_known_version: "0.5.2" },
    };
    expect(shouldShowUpdateBanner(info, true)).toBe(false);
  });

  it("shows banner again when a newer latest version appears", () => {
    expect(isUpdateBannerDismissedForVersion("0.6.0", "0.5.2")).toBe(false);
    const info: VersionInfo = {
      sync: { update_available: true, latest_known_version: "0.6.0" },
    };
    expect(shouldShowUpdateBanner(info, false)).toBe(true);
  });

  it("hides banner when github latest is behind local build", () => {
    const info: VersionInfo = {
      current_version: "0.5.1",
      sync: {
        update_available: false,
        latest_known_version: "0.5.0",
      },
    };
    expect(shouldShowUpdateBanner(info, false)).toBe(false);
  });
});
