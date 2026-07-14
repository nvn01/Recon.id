import { describe, expect, it } from "vitest";

import {
  listingSortOptions,
  parseListingSort,
  sortListings,
} from "~/data/listing-sort";

const listings = [
  { id: "sold-new", status: "sold" as const, price: 500 },
  { id: "available-new", status: "available" as const, price: 300 },
  { id: "unknown", status: "unknown" as const, price: null },
  { id: "available-old", status: "available" as const, price: 100 },
  { id: "sold-old", status: "sold" as const, price: 700 },
];

function ids(sort: Parameters<typeof sortListings>[1]) {
  return sortListings(listings, sort).map((listing) => listing.id);
}

describe("listing sorting", () => {
  it("offers the five requested orders without an oldest option", () => {
    expect(listingSortOptions.map((option) => option.value)).toEqual([
      "newest",
      "price-high",
      "price-low",
      "available-first",
      "sold-first",
    ]);
    expect(listingSortOptions.slice(-2).map((option) => option.label)).toEqual([
      "Ready stock",
      "Sold out",
    ]);
  });

  it("keeps available and unknown together by freshness, then sold", () => {
    expect(ids("newest")).toEqual([
      "available-new",
      "unknown",
      "available-old",
      "sold-new",
      "sold-old",
    ]);
  });

  it("sorts both price directions while keeping sold at the bottom", () => {
    expect(ids("price-high")).toEqual([
      "available-new",
      "available-old",
      "unknown",
      "sold-old",
      "sold-new",
    ]);
    expect(ids("price-low")).toEqual([
      "available-old",
      "available-new",
      "unknown",
      "sold-new",
      "sold-old",
    ]);
  });

  it("can prioritize available or sold listings explicitly", () => {
    expect(ids("available-first")).toEqual([
      "available-new",
      "available-old",
      "unknown",
      "sold-new",
      "sold-old",
    ]);
    expect(ids("sold-first")).toEqual([
      "sold-new",
      "sold-old",
      "available-new",
      "unknown",
      "available-old",
    ]);
  });

  it("falls back to newest for missing or unsupported query values", () => {
    expect(parseListingSort(null)).toBe("newest");
    expect(parseListingSort("oldest")).toBe("newest");
  });
});
