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
          coverAltText: "Laptop",
        },
        {
          value: "GPU",
          count: 4,
          minPrice: null,
          coverImageUrl: "javascript:alert(1)",
          coverAltText: null,
        },
      ])
      .mockResolvedValueOnce([
        { value: "Bandung", count: 8 },
        { value: "081234567890", count: 2 },
      ])
      .mockResolvedValueOnce([{ value: "Bekas - baik", count: 9 }]);

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
  });
});
