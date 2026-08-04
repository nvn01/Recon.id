import { describe, expect, it } from "vitest";

import {
  automaticListingRefreshQueryOptions,
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

describe("automaticListingRefreshQueryOptions", () => {
  it("reconciles cached feeds whenever they mount or become active", () => {
    expect(automaticListingRefreshQueryOptions).toEqual({
      refetchOnMount: "always",
      refetchOnReconnect: true,
      refetchOnWindowFocus: true,
      staleTime: 0,
    });
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
  it("only resets after an established database revision changes", () => {
    expect(hasNewListingRevision(null, "revision-a")).toBe(false);
    expect(hasNewListingRevision("revision-a", "revision-a")).toBe(false);
    expect(hasNewListingRevision("revision-a", "revision-b")).toBe(true);
  });
});
