import { describe, expect, it } from "vitest";

import {
  countActiveFilterGroups,
  filterListings,
  parseListingFilters,
  setListingFilterParams,
  type ListingFilters,
} from "~/data/listing-filter";

const listings = [
  {
    id: "one",
    platform: "facebook" as const,
    location: "Bandung",
    condition: "Bekas - baik",
    price: 2_000_000,
  },
  {
    id: "two",
    platform: "instagram" as const,
    location: "Jakarta Selatan",
    condition: "Bekas - sangat baik",
    price: 5_000_000,
  },
  {
    id: "unknown-price",
    platform: "reddit" as const,
    location: "Bandung",
    condition: "Bekas - baik",
    price: null,
  },
];

describe("listing filters", () => {
  it("parses valid repeated filters and ignores unsupported values", () => {
    const params = new URLSearchParams(
      "platform=facebook&platform=facebook&platform=tiktok&location=Bandung&condition=Bekas+-+baik&minPrice=1000000&maxPrice=nope",
    );

    expect(parseListingFilters(params)).toEqual({
      platforms: ["facebook"],
      locations: ["Bandung"],
      conditions: ["Bekas - baik"],
      minPrice: 1_000_000,
      maxPrice: null,
    });
  });

  it("combines platform, location, condition, and price boundaries", () => {
    const filters: ListingFilters = {
      platforms: ["facebook", "reddit"],
      locations: ["Bandung"],
      conditions: ["Bekas - baik"],
      minPrice: 1_500_000,
      maxPrice: 3_000_000,
    };

    expect(
      filterListings(listings, filters).map((listing) => listing.id),
    ).toEqual(["one"]);
  });

  it("excludes unreadable prices only when a price boundary is active", () => {
    const filters: ListingFilters = {
      platforms: [],
      locations: ["Bandung"],
      conditions: [],
      minPrice: null,
      maxPrice: null,
    };

    expect(
      filterListings(listings, filters).map((listing) => listing.id),
    ).toEqual(["one", "unknown-price"]);
    expect(
      filterListings(listings, { ...filters, maxPrice: 4_000_000 }).map(
        (listing) => listing.id,
      ),
    ).toEqual(["one"]);
  });

  it("writes filter values without dropping search or sort state", () => {
    const params = new URLSearchParams("q=rtx&sort=price-low&platform=reddit");
    const next = setListingFilterParams(params, {
      platforms: ["facebook", "instagram"],
      locations: ["Bandung"],
      conditions: [],
      minPrice: 500_000,
      maxPrice: null,
    });

    expect(next.get("q")).toBe("rtx");
    expect(next.get("sort")).toBe("price-low");
    expect(next.getAll("platform")).toEqual(["facebook", "instagram"]);
    expect(next.getAll("location")).toEqual(["Bandung"]);
    expect(next.get("minPrice")).toBe("500000");
    expect(next.has("maxPrice")).toBe(false);
  });

  it("counts active groups instead of every selected option", () => {
    expect(
      countActiveFilterGroups({
        platforms: ["facebook", "instagram"],
        locations: ["Bandung", "Jakarta Selatan"],
        conditions: [],
        minPrice: null,
        maxPrice: 8_000_000,
      }),
    ).toBe(3);
  });
});
