import { describe, expect, it } from "vitest";

import {
  countActiveFilterGroups,
  parseListingFilters,
  setListingFilterParams,
} from "~/data/listing-filter";

describe("listing filters", () => {
  it("parses valid repeated filters and ignores unsupported values", () => {
    const params = new URLSearchParams(
      "platform=facebook&platform=facebook&platform=tiktok&status=available&status=removed&location=Bandung&condition=Bekas+-+baik&minPrice=1000000&maxPrice=nope",
    );

    expect(parseListingFilters(params)).toEqual({
      platforms: ["facebook"],
      statuses: ["available"],
      locations: ["Bandung"],
      conditions: ["Bekas - baik"],
      minPrice: 1_000_000,
      maxPrice: null,
    });
  });

  it("writes filter values without dropping search or sort state", () => {
    const params = new URLSearchParams("q=rtx&sort=price-low&platform=reddit");
    const next = setListingFilterParams(params, {
      platforms: ["facebook", "instagram"],
      statuses: ["available", "unknown"],
      locations: ["Bandung"],
      conditions: [],
      minPrice: 500_000,
      maxPrice: null,
    });

    expect(next.get("q")).toBe("rtx");
    expect(next.get("sort")).toBe("price-low");
    expect(next.getAll("platform")).toEqual(["facebook", "instagram"]);
    expect(next.getAll("status")).toEqual(["available", "unknown"]);
    expect(next.getAll("location")).toEqual(["Bandung"]);
    expect(next.get("minPrice")).toBe("500000");
    expect(next.has("maxPrice")).toBe(false);
  });

  it("counts active groups instead of every selected option", () => {
    expect(
      countActiveFilterGroups({
        platforms: ["facebook", "instagram"],
        statuses: ["available"],
        locations: ["Bandung", "Jakarta Selatan"],
        conditions: [],
        minPrice: null,
        maxPrice: 8_000_000,
      }),
    ).toBe(4);
  });
});
