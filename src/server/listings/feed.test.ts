import { describe, expect, it, vi } from "vitest";

import { decodeListingCursor, encodeListingCursor } from "./cursor";
import { buildListingFeedQuery, getListingFeed } from "./feed";

const baseListing = {
  id: "listing-a",
  platform: "REDDIT",
  sourceUrl: "https://www.reddit.com/r/test/comments/a",
  title: "Listing A",
  description: "Description A",
  category: null,
  brand: null,
  price: null,
  locationTexts: [],
  conditionText: null,
  sellerName: null,
  moderation: null,
  status: "AVAILABLE",
  postedAt: new Date("2026-07-12T10:00:00Z"),
  firstFetchedAt: new Date("2026-07-12T10:01:00Z"),
  images: [
    {
      sourceUrl: "https://preview.redd.it/a.jpg",
      position: 0,
      altText: null,
    },
  ],
};

describe("getListingFeed", () => {
  it("keeps every status in one recency bucket for the default newest sort", () => {
    const query = buildListingFeedQuery({ limit: 24 });
    const sql = query.strings.join("?");

    expect(sql).toContain('0 AS "statusRank"');
    expect(sql).not.toContain("WHEN 'sold'");
    expect(sql).not.toContain("WHEN 'available'");
    expect(sql).not.toContain("WHEN 'unknown'");
  });

  it("preserves explicit ready-stock and sold-out status sorting", () => {
    const availableFirstSql = buildListingFeedQuery({
      limit: 24,
      sort: "available-first",
    }).strings.join("?");
    const soldFirstSql = buildListingFeedQuery({
      limit: 24,
      sort: "sold-first",
    }).strings.join("?");

    expect(availableFirstSql).toContain("WHEN 'available' THEN 0");
    expect(availableFirstSql).toContain("WHEN 'unknown' THEN 1");
    expect(soldFirstSql).toContain("WHEN 'sold' THEN 0");
  });

  it("filters hidden listings, content blocks, disabled platforms, and blocked seller names across Facebook sources", () => {
    const query = buildListingFeedQuery({ limit: 24 });
    const sql = query.strings.join("?");

    expect(sql).toContain("listing_moderation.hidden");
    expect(sql).toContain("listing_content_blocks");
    expect(sql).toContain("content_block.field::text = 'title'");
    expect(sql).toContain("content_block.field::text = 'description'");
    expect(sql).toContain("normalize_listing_content(listing.title)");
    expect(sql).toContain("normalize_listing_content(listing.description)");
    expect(sql).toContain("platform_control.public_visible");
    expect(sql).toContain("facebook_seller_flags");
    expect(sql).toContain("listing.platform::text IN ('facebook', 'facebook_group')");
    expect(sql).toContain("normalize_seller_name");
    expect(sql).toContain("seller_name_override");
  });

  it("preserves ranked query order, maps DTOs, and emits the last returned row as cursor", async () => {
    const queryRaw = vi.fn().mockResolvedValue([
      {
        id: "listing-b",
        statusRank: 0,
        sortValue: 0,
        effectiveAt: new Date("2026-07-12T11:00:00Z"),
      },
      {
        id: "listing-a",
        statusRank: 0,
        sortValue: 0,
        effectiveAt: new Date("2026-07-12T10:00:00Z"),
      },
      {
        id: "listing-c",
        statusRank: 0,
        sortValue: 0,
        effectiveAt: new Date("2026-07-12T09:00:00Z"),
      },
    ]);
    const findMany = vi.fn().mockResolvedValue([
      baseListing,
      {
        ...baseListing,
        id: "listing-b",
        sourceUrl: "https://www.reddit.com/r/test/comments/b",
        title: "Listing B",
        status: "SOLD",
      },
    ]);
    const db = { $queryRaw: queryRaw, listing: { findMany } };

    const result = await getListingFeed(db, { limit: 2 });

    expect(result.items.map((item) => item.id)).toEqual([
      "listing-b",
      "listing-a",
    ]);
    expect(result.items[0]?.status).toBe("sold");
    expect(result.hasNextPage).toBe(true);
    expect(result.nextCursor).not.toBeNull();
    expect(decodeListingCursor(result.nextCursor!)).toEqual({
      sort: "newest",
      statusRank: 0,
      sortValue: 0,
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
      sort: "newest",
      statusRank: 0,
      sortValue: 0,
      effectiveAt: new Date("2026-07-12T09:00:00Z"),
      id: "cursor-id",
    });

    await getListingFeed(db, {
      platforms: ["facebook"],
      statuses: ["available"],
      categories: ["Laptop"],
      locations: ["Bandung"],
      conditions: ["Bekas - baik"],
      q: "100% RTX_4070",
      minPrice: 1_000_000,
      maxPrice: 10_000_000,
      limit: 5,
      cursor,
    });

    const sql = queryRaw.mock.calls[0]?.[0] as { values?: unknown[] };
    const queryText = (
      queryRaw.mock.calls[0]?.[0] as { strings?: string[] }
    ).strings?.join("?");
    expect(queryText).toContain("category IN");
    expect(queryText).toContain("location_texts && ARRAY");
    expect(queryText).toContain("condition_text IN");
    expect(queryText).toContain("ILIKE");
    expect(queryText).toContain("price >=");
    expect(queryText).toContain("price <=");
    expect(sql.values).toEqual(
      expect.arrayContaining([
        "facebook",
        "available",
        "Laptop",
        "Bandung",
        "Bekas - baik",
        "%100\\% RTX\\_4070%",
        1_000_000,
        10_000_000,
        0,
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
          sortValue: 0,
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
