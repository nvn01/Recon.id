import { describe, expect, it } from "vitest";

import {
  priceBucket,
  queryLengthBucket,
  resultCountBucket,
  sanitizedPagePath,
} from "~/lib/analytics";

describe("privacy-safe analytics helpers", () => {
  it("keeps only a pathname for page measurement", () => {
    expect(sanitizedPagePath("/collection/all")).toBe("/collection/all");
    expect(sanitizedPagePath("https://example.com/?q=secret")).toBe("/");
  });

  it("buckets values without preserving sensitive raw input", () => {
    expect(queryLengthBucket(14)).toBe("6-15");
    expect(resultCountBucket(19)).toBe("13-24");
    expect(priceBucket(7_500_000)).toBe("5m-15m");
    expect(priceBucket(null)).toBe("unknown");
  });
});
