import { describe, expect, it } from "vitest";

import { dummyListings, platformMeta } from "~/data/dummy-listings";

describe("dummy listing source links", () => {
  it("keeps every posting URL HTTPS and separate from its image credit URL", () => {
    for (const listing of dummyListings) {
      expect(new URL(listing.sourceUrl).protocol).toBe("https:");
      expect(listing.sourceUrl).not.toBe(listing.imagePageUrl);
    }
  });

  it("uses the source platform host for every posting URL", () => {
    const hosts = {
      instagram: "www.instagram.com",
      facebook: "www.facebook.com",
      reddit: "www.reddit.com",
    } as const;

    for (const listing of dummyListings) {
      expect(new URL(listing.sourceUrl).host).toBe(hosts[listing.platform]);
      expect(platformMeta[listing.platform].label).toBeTruthy();
    }
  });
});
