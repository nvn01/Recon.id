import { describe, expect, it } from "vitest";

import { listingFeedInputSchema } from "./feed-input";

describe("listingFeedInputSchema", () => {
  it("applies the feed defaults", () => {
    expect(listingFeedInputSchema.parse(undefined)).toEqual({ limit: 24 });
  });

  it("accepts the bounded filters required by the public UI", () => {
    expect(
      listingFeedInputSchema.parse({
        platforms: ["instagram", "facebook"],
        statuses: ["available", "sold"],
        categories: ["Laptop", "GPU"],
        locations: ["Bandung", "Jakarta Selatan"],
        conditions: ["Bekas - baik"],
        q: "  RTX 4070  ",
        minPrice: 1_000_000,
        maxPrice: 10_000_000,
        limit: 12,
      }),
    ).toEqual({
      platforms: ["instagram", "facebook"],
      statuses: ["available", "sold"],
      categories: ["Laptop", "GPU"],
      locations: ["Bandung", "Jakarta Selatan"],
      conditions: ["Bekas - baik"],
      q: "RTX 4070",
      minPrice: 1_000_000,
      maxPrice: 10_000_000,
      limit: 12,
    });
  });

  it.each([
    { limit: 0 },
    { limit: 51 },
    { platforms: [] },
    { statuses: [] },
    { categories: [] },
    { locations: [] },
    { conditions: [] },
    { platforms: ["instagram", "instagram"] },
    { statuses: ["available", "available"] },
    { categories: ["GPU", "GPU"] },
    { locations: ["Bandung", "Bandung"] },
    { conditions: ["Bekas", "Bekas"] },
    { platforms: ["tiktok"] },
    { statuses: ["removed"] },
    { q: " " },
    { q: "x".repeat(81) },
    { minPrice: -1 },
    { maxPrice: 2_000_000_001 },
    { minPrice: 5_000_000, maxPrice: 1_000_000 },
    { cursor: "x".repeat(513) },
    { unexpected: true },
  ])("rejects invalid or excessive input: %j", (input) => {
    expect(() => listingFeedInputSchema.parse(input)).toThrow();
  });
});
