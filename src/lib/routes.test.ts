import { describe, expect, it } from "vitest";

import { allListingsPath, collectionPath } from "~/lib/routes";

describe("public route helpers", () => {
  it("uses the root URL for the all-listings collection", () => {
    expect(allListingsPath).toBe("/");
    expect(collectionPath("all")).toBe("/");
  });

  it("keeps category collection routes unchanged", () => {
    expect(collectionPath("gpu")).toBe("/collection/gpu");
    expect(collectionPath("laptop")).toBe("/collection/laptop");
  });
});
