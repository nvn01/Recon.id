import { describe, expect, it, vi } from "vitest";

import { getListingFacets } from "./facets";

describe("getListingFacets", () => {
  it("returns bounded real filter values and safe category cover URLs", async () => {
    const queryRaw = vi
      .fn()
      .mockResolvedValueOnce([
        {
          value: "Laptop",
          count: 12,
          minPrice: 1_500_000,
          coverImageUrl: "https://example.com/laptop.jpg",
          coverImageCached: false,
          coverAltText: "Laptop",
        },
        {
          value: "GPU",
          count: 4,
          minPrice: 123_456,
          coverImageUrl: "javascript:alert(1)",
          coverImageCached: false,
          coverAltText: null,
        },
      ])
      .mockResolvedValueOnce([
        { value: "Bandung", count: 8 },
        { value: "081234567890", count: 2 },
        { value: "link oren maleman", count: 3 },
      ])
      .mockResolvedValueOnce([
        { value: "Bekas - baik", count: 9 },
        { value: "Laptop gaming mulus siap pakai harga nego", count: 2 },
      ]);

    await expect(getListingFacets({ $queryRaw: queryRaw })).resolves.toEqual({
      categories: [
        {
          value: "Laptop",
          count: 12,
          minPrice: 1_500_000,
          coverImageUrl: "https://example.com/laptop.jpg",
          coverAltText: "Laptop",
        },
        {
          value: "GPU",
          count: 4,
          minPrice: null,
          coverImageUrl: null,
          coverAltText: null,
        },
      ],
      locations: [{ value: "Bandung", count: 8 }],
      conditions: [{ value: "Bekas - baik", count: 9 }],
    });

    for (const [query] of queryRaw.mock.calls) {
      const sql = (query as { strings: string[] }).strings.join("?");
      expect(sql).toContain("facebook_seller_flags");
      expect(sql).toContain("platform_control.public_visible");
      expect(sql).toContain("listing_moderation.hidden");
    }
  });
});
