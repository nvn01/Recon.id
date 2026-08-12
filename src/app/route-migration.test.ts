import { describe, expect, it } from "vitest";

import config from "../../next.config.js";

describe("all-listings route migration", () => {
  it("permanently redirects the retired all-collection URL to the root", async () => {
    const redirects = await config.redirects?.();

    expect(redirects).toContainEqual({
      source: "/collection/all",
      destination: "/",
      permanent: true,
    });
  });
});
