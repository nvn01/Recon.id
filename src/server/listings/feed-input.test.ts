import { describe, expect, it } from "vitest";

import { listingFeedInputSchema } from "./feed-input";

describe("listingFeedInputSchema", () => {
  it("applies the feed defaults", () => {
    expect(listingFeedInputSchema.parse(undefined)).toEqual({ limit: 24 });
  });

  it("accepts supported platform and status filters", () => {
    expect(
      listingFeedInputSchema.parse({
        platforms: ["instagram", "facebook"],
        statuses: ["available", "sold"],
        limit: 50,
      }),
    ).toEqual({
      platforms: ["instagram", "facebook"],
      statuses: ["available", "sold"],
      limit: 50,
    });
  });

  it.each([
    { limit: 0 },
    { limit: 51 },
    { platforms: [] },
    { statuses: [] },
    { platforms: ["instagram", "instagram"] },
    { statuses: ["available", "available"] },
    { platforms: ["tiktok"] },
    { statuses: ["removed"] },
    { cursor: "x".repeat(513) },
    { unexpected: true },
  ])("rejects invalid or excessive input: %j", (input) => {
    expect(() => listingFeedInputSchema.parse(input)).toThrow();
  });
});
