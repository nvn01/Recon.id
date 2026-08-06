import { describe, expect, it } from "vitest";

import {
  countUnseenListings,
  createListingRefreshStore,
  hasNewListingRevision,
  listingVersionQueryOptions,
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

describe("listingVersionQueryOptions", () => {
  it("checks for database inserts every 30 seconds in an active tab", () => {
    expect(listingVersionQueryOptions).toEqual({
      refetchInterval: 30_000,
      refetchIntervalInBackground: false,
      refetchOnReconnect: true,
      refetchOnWindowFocus: true,
      retry: 1,
      staleTime: 0,
    });
  });
});

describe("hasNewListingRevision", () => {
  it("only announces after an established database revision changes", () => {
    expect(hasNewListingRevision(null, "revision-a")).toBe(false);
    expect(hasNewListingRevision("revision-a", "revision-a")).toBe(false);
    expect(hasNewListingRevision("revision-a", "revision-b")).toBe(true);
  });
});

describe("createListingRefreshStore", () => {
  it("keeps new global items pending when a filtered page is refreshed", () => {
    const store = createListingRefreshStore();

    store.observe({ revision: "revision-a", totalCount: 20 });
    store.observe({ revision: "revision-b", totalCount: 23 });
    expect(store.getSnapshot().unseenCount).toBe(3);

    store.observe({ revision: "revision-b", totalCount: 23 });
    expect(store.getSnapshot().unseenCount).toBe(3);
  });

  it("clears the pending global items only when the all-feed acknowledges them", () => {
    const store = createListingRefreshStore();

    store.observe({ revision: "revision-a", totalCount: 20 });
    store.observe({ revision: "revision-b", totalCount: 23 });
    store.acknowledge();

    expect(store.getSnapshot().unseenCount).toBe(0);
    expect(store.getSnapshot().acknowledged?.revision).toBe("revision-b");
  });
});
