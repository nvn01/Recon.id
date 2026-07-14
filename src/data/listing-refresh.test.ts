import { describe, expect, it } from "vitest";

import {
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

describe("hasUnseenListingRevision", () => {
  it("does not announce the initial or already-seen database revision", () => {
    expect(hasUnseenListingRevision(null, "revision-a")).toBe(false);
    expect(hasUnseenListingRevision("revision-a", "revision-a")).toBe(false);
  });

  it("announces a changed revision until the user refreshes", () => {
    expect(hasUnseenListingRevision("revision-a", "revision-b")).toBe(true);
  });
});
