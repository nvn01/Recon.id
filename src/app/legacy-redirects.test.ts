import { describe, expect, it, vi } from "vitest";

const { permanentRedirectMock } = vi.hoisted(() => ({
  permanentRedirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  permanentRedirect: permanentRedirectMock,
}));

import LegacyHowItWorksPage from "~/app/cara-kerja/page";
import LegacyPrivacyPage from "~/app/privacy/page";

describe("legacy public route redirects", () => {
  it("redirects the old privacy URL to the current policy", () => {
    LegacyPrivacyPage();

    expect(permanentRedirectMock).toHaveBeenCalledWith("/privacy-policy");
  });

  it("redirects the old how-it-works URL to the current about page", () => {
    LegacyHowItWorksPage();

    expect(permanentRedirectMock).toHaveBeenCalledWith("/about-us");
  });
});
