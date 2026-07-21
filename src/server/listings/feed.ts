import { Prisma } from "../../../generated/prisma";

import {
  decodeListingCursor,
  encodeListingCursor,
  InvalidListingCursorError,
  type ListingCursor,
} from "./cursor";
import { type ListingFeedInput } from "./feed-input";
import { defaultListingSort, type ListingSort } from "~/data/listing-sort";
import {
  listingFeedSelect,
  toListingDto,
  type ListingFeedRecord,
} from "./listing-dto";
import {
  publicListingModerationJoins,
  publicListingVisibilityFilter,
} from "./visibility";

interface RankedListingKey {
  id: string;
  statusRank: number;
  sortValue: number;
  effectiveAt: Date;
}

export interface ListingFeedDatabase {
  $queryRaw(query: Prisma.Sql): Promise<RankedListingKey[]>;
  listing: {
    findMany(args: {
      where: { id: { in: string[] } };
      select: typeof listingFeedSelect;
    }): Promise<ListingFeedRecord[]>;
  };
}

export async function getListingFeed(
  db: ListingFeedDatabase,
  input: ListingFeedInput,
) {
  const cursor = input.cursor ? decodeListingCursor(input.cursor) : undefined;
  const sort = input.sort ?? defaultListingSort;
  if (cursor && cursor.sort !== sort) {
    throw new InvalidListingCursorError();
  }
  const rankedKeys = await db.$queryRaw(buildListingFeedQuery(input, cursor));
  const pageKeys = rankedKeys.slice(0, input.limit);

  if (pageKeys.length === 0) {
    return {
      items: [],
      nextCursor: null,
      hasNextPage: false,
    };
  }

  const records = await db.listing.findMany({
    where: {
      id: { in: pageKeys.map((key) => key.id) },
    },
    select: listingFeedSelect,
  });
  const recordsById = new Map(records.map((record) => [record.id, record]));
  const orderedRecords = pageKeys.map((key) => {
    const record = recordsById.get(key.id);
    if (!record) {
      throw new Error("Ranked listing disappeared before DTO readback");
    }
    return record;
  });
  const hasNextPage = rankedKeys.length > input.limit;
  const lastKey = pageKeys.at(-1)!;

  return {
    items: orderedRecords.map((record) => toListingDto(record)),
    nextCursor: hasNextPage
      ? encodeListingCursor({
          sort,
          statusRank: lastKey.statusRank,
          sortValue: lastKey.sortValue,
          effectiveAt: lastKey.effectiveAt,
          id: lastKey.id,
        })
      : null,
    hasNextPage,
  };
}

export function buildListingFeedQuery(
  input: ListingFeedInput,
  cursor?: ListingCursor,
): Prisma.Sql {
  const sort = input.sort ?? defaultListingSort;
  const platformFilter = input.platforms
    ? Prisma.sql`AND listing.platform::text IN (${Prisma.join(input.platforms)})`
    : Prisma.empty;
  const statusFilter = input.statuses
    ? Prisma.sql`AND listing.status::text IN (${Prisma.join(input.statuses)})`
    : Prisma.empty;
  const categoryFilter = input.categories
    ? Prisma.sql`AND listing.category IN (${Prisma.join(input.categories)})`
    : Prisma.empty;
  const locationFilter = input.locations
    ? Prisma.sql`AND listing.location_texts && ARRAY[${Prisma.join(input.locations)}]::text[]`
    : Prisma.empty;
  const conditionFilter = input.conditions
    ? Prisma.sql`AND listing.condition_text IN (${Prisma.join(input.conditions)})`
    : Prisma.empty;
  const searchPattern = input.q ? `%${escapeLikePattern(input.q)}%` : undefined;
  const searchFilter = searchPattern
    ? Prisma.sql`AND (
        listing.title ILIKE ${searchPattern} ESCAPE CHR(92)
        OR listing.description ILIKE ${searchPattern} ESCAPE CHR(92)
        OR COALESCE(listing.brand, '') ILIKE ${searchPattern} ESCAPE CHR(92)
        OR COALESCE(listing.category, '') ILIKE ${searchPattern} ESCAPE CHR(92)
        OR COALESCE(listing_moderation.seller_name_override, listing.seller_name, '')
          ILIKE ${searchPattern} ESCAPE CHR(92)
      )`
    : Prisma.empty;
  const minPriceFilter =
    input.minPrice !== undefined
      ? Prisma.sql`AND listing.price >= ${input.minPrice}`
      : Prisma.empty;
  const maxPriceFilter =
    input.maxPrice !== undefined
      ? Prisma.sql`AND listing.price <= ${input.maxPrice}`
      : Prisma.empty;
  const rankExpression = statusRankExpression(sort);
  const sortValueExpression = listingSortValueExpression(sort);
  const sortValueDirection =
    sort === "price-low" ? Prisma.sql`ASC` : Prisma.sql`DESC`;
  const cursorSortComparison =
    sort === "price-low"
      ? Prisma.sql`"sortValue" > ${cursor?.sortValue ?? 0}`
      : Prisma.sql`"sortValue" < ${cursor?.sortValue ?? 0}`;
  const cursorFilter = cursor
    ? Prisma.sql`
        WHERE
          "statusRank" > ${cursor.statusRank}
          OR (
            "statusRank" = ${cursor.statusRank}
            AND ${cursorSortComparison}
          )
          OR (
            "statusRank" = ${cursor.statusRank}
            AND "sortValue" = ${cursor.sortValue}
            AND "effectiveAt" < ${cursor.effectiveAt}
          )
          OR (
            "statusRank" = ${cursor.statusRank}
            AND "sortValue" = ${cursor.sortValue}
            AND "effectiveAt" = ${cursor.effectiveAt}
            AND id < ${cursor.id}
          )
      `
    : Prisma.empty;

  return Prisma.sql`
    WITH ranked AS (
      SELECT
        listing.id,
        ${rankExpression} AS "statusRank",
        ${sortValueExpression} AS "sortValue",
        COALESCE(listing.posted_at, listing.first_fetched_at) AS "effectiveAt"
      FROM listings AS listing
      ${publicListingModerationJoins}
      WHERE TRUE
        ${publicListingVisibilityFilter}
        ${platformFilter}
        ${statusFilter}
        ${categoryFilter}
        ${locationFilter}
        ${conditionFilter}
        ${searchFilter}
        ${minPriceFilter}
        ${maxPriceFilter}
    )
    SELECT id, "statusRank", "sortValue", "effectiveAt"
    FROM ranked
    ${cursorFilter}
    ORDER BY
      "statusRank" ASC,
      "sortValue" ${sortValueDirection},
      "effectiveAt" DESC,
      id DESC
    LIMIT ${input.limit + 1}
  `;
}

function statusRankExpression(sort: ListingSort): Prisma.Sql {
  if (sort === "available-first") {
    return Prisma.sql`CASE listing.status::text
      WHEN 'available' THEN 0
      WHEN 'unknown' THEN 1
      ELSE 2
    END`;
  }

  if (sort === "sold-first") {
    return Prisma.sql`CASE listing.status::text
      WHEN 'sold' THEN 0
      ELSE 1
    END`;
  }

  return Prisma.sql`CASE listing.status::text
    WHEN 'sold' THEN 1
    ELSE 0
  END`;
}

function listingSortValueExpression(sort: ListingSort): Prisma.Sql {
  if (sort === "price-high") return Prisma.sql`COALESCE(listing.price, -1)`;
  if (sort === "price-low") return Prisma.sql`COALESCE(listing.price, 2147483647)`;
  return Prisma.sql`0`;
}

function escapeLikePattern(value: string): string {
  return value.replace(/[\\%_]/g, "\\$&");
}
