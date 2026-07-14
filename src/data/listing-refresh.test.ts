import { describe, expect, it } from "vitest";

import {
  countUnseenListings,
  hasUnseenListingRevision,
  manualListingRefreshQueryOptions,
} from "./listing-refresh";

describe("manualListingRefreshQueryOptions", () => {
  it("prevents focus and reconnect events from replacing the visible feed", () => {
    expect(manualListingRefreshQueryOptions).toEqual({
      refetchOnReconnect: false,
      refetchOnWindowFocus: false,
      staleTime: Infinity,
    });
  });
});

describe("countUnseenListings", () => {
  it("counts only inserts after the visible-feed baseline", () => {
    expect(countUnseenListings(null, 20)).toBe(0);
    expect(countUnseenListings(20, 23)).toBe(3);
    expect(countUnseenListings(23, 22)).toBe(0);
  });
});

describe("hasUnseenListingRevision", () => {
  it("does not announce the initial or already-seen database revision", () => {
    expect(hasUnseenListingRevision(null, "revision-a")).toBe(false);
    expect(hasUnseenListingRevision("revision-a", "revision-a")).toBe(false);
  });

  it("announces a changed revision until the user refreshes", () => {
    expect(hasUnseenListingRevision("revision-a", "revision-b")).toBe(true);
  });
});
