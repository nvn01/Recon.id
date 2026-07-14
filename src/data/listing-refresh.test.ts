import { describe, expect, it } from "vitest";

import { hasUnseenListingRevision } from "./listing-refresh";

describe("hasUnseenListingRevision", () => {
  it("does not announce the initial or already-seen database revision", () => {
    expect(hasUnseenListingRevision(null, "revision-a")).toBe(false);
    expect(hasUnseenListingRevision("revision-a", "revision-a")).toBe(false);
  });

  it("announces a changed revision until the user refreshes", () => {
    expect(hasUnseenListingRevision("revision-a", "revision-b")).toBe(true);
  });
});
