import { describe, expect, it, vi } from "vitest";

import { decodeListingCursor, encodeListingCursor } from "./cursor";
import { getListingFeed } from "./feed";

const baseListing = {
  id: "listing-a",
  platform: "REDDIT",
  sourceUrl: "https://www.reddit.com/r/test/comments/a",
  externalId: "a",
  title: "Listing A",
  description: "Description A",
  category: null,
  brand: null,
  price: null,
  locationTexts: [],
  conditionText: null,
  sellerName: null,
  status: "AVAILABLE",
  postedAt: new Date("2026-07-12T10:00:00Z"),
  firstFetchedAt: new Date("2026-07-12T10:01:00Z"),
  lastFetchedAt: new Date("2026-07-12T10:05:00Z"),
  images: [
    {
      sourceUrl: "https://preview.redd.it/a.jpg",
      position: 0,
      altText: null,
    },
  ],
};

describe("getListingFeed", () => {
  it("preserves ranked query order, maps DTOs, and emits the last returned row as cursor", async () => {
    const queryRaw = vi.fn().mockResolvedValue([
      {
        id: "listing-b",
        statusRank: 0,
        effectiveAt: new Date("2026-07-12T11:00:00Z"),
      },
      {
        id: "listing-a",
        statusRank: 0,
        effectiveAt: new Date("2026-07-12T10:00:00Z"),
      },
      {
        id: "listing-c",
        statusRank: 1,
        effectiveAt: new Date("2026-07-12T09:00:00Z"),
      },
    ]);
    const findMany = vi.fn().mockResolvedValue([
      baseListing,
      {
        ...baseListing,
        id: "listing-b",
        sourceUrl: "https://www.reddit.com/r/test/comments/b",
        externalId: "b",
        title: "Listing B",
      },
    ]);
    const db = { $queryRaw: queryRaw, listing: { findMany } };

    const result = await getListingFeed(db, { limit: 2 });

    expect(result.items.map((item) => item.id)).toEqual([
      "listing-b",
      "listing-a",
    ]);
    expect(result.hasNextPage).toBe(true);
    expect(result.nextCursor).not.toBeNull();
    expect(decodeListingCursor(result.nextCursor!)).toEqual({
      statusRank: 0,
      effectiveAt: new Date("2026-07-12T10:00:00Z"),
      id: "listing-a",
    });
    expect(findMany).toHaveBeenCalledOnce();
  });

  it("returns an empty page without issuing the record query", async () => {
    const queryRaw = vi.fn().mockResolvedValue([]);
    const findMany = vi.fn();
    const db = { $queryRaw: queryRaw, listing: { findMany } };

    await expect(getListingFeed(db, { limit: 24 })).resolves.toEqual({
      items: [],
      nextCursor: null,
      hasNextPage: false,
    });
    expect(findMany).not.toHaveBeenCalled();
  });

  it("parameterizes filters and cursor values instead of interpolating them", async () => {
    const queryRaw = vi.fn().mockResolvedValue([]);
    const db = { $queryRaw: queryRaw, listing: { findMany: vi.fn() } };

    const cursor = encodeListingCursor({
      statusRank: 1,
      effectiveAt: new Date("2026-07-12T09:00:00Z"),
      id: "cursor-id",
    });

    await getListingFeed(db, {
      platforms: ["facebook"],
      statuses: ["available"],
      limit: 5,
      cursor,
    });

    const sql = queryRaw.mock.calls[0]?.[0] as { values?: unknown[] };
    expect(sql.values).toEqual(
      expect.arrayContaining([
        "facebook",
        "available",
        1,
        new Date("2026-07-12T09:00:00Z"),
        "cursor-id",
        6,
      ]),
    );
  });

  it("fails rather than silently returning a partial page when a ranked row disappears", async () => {
    const db = {
      $queryRaw: vi.fn().mockResolvedValue([
        {
          id: "missing",
          statusRank: 0,
          effectiveAt: new Date("2026-07-12T10:00:00Z"),
        },
      ]),
      listing: { findMany: vi.fn().mockResolvedValue([]) },
    };

    await expect(getListingFeed(db, { limit: 24 })).rejects.toThrow(
      "Ranked listing disappeared",
    );
  });
});
