import { describe, expect, it } from "vitest";

import { buildListingFeedInput } from "~/data/listing-query";

describe("listing feed query mapping", () => {
  it("builds the 12-item collection request used by manual load-more", () => {
    expect(
      buildListingFeedInput(
        { type: "collection", slug: "gpu" },
        {
          platforms: ["facebook"],
          statuses: ["available", "unknown"],
          locations: ["Bandung"],
          conditions: ["Bekas - baik"],
          minPrice: 1_000_000,
          maxPrice: 8_000_000,
        },
        "rtx 4070",
      ),
    ).toEqual({
      limit: 12,
      platforms: ["facebook"],
      statuses: ["available", "unknown"],
      categories: ["GPU"],
      locations: ["Bandung"],
      conditions: ["Bekas - baik"],
      minPrice: 1_000_000,
      maxPrice: 8_000_000,
      q: "rtx 4070",
    });
  });

  it("locks a platform route to that platform and omits empty filters", () => {
    expect(
      buildListingFeedInput(
        { type: "platform", slug: "instagram" },
        {
          platforms: [],
          statuses: [],
          locations: [],
          conditions: [],
          minPrice: null,
          maxPrice: null,
        },
        "",
      ),
    ).toEqual({ limit: 12, platforms: ["instagram"] });
  });
});
