import { Prisma } from "../../../generated/prisma";

import {
  decodeListingCursor,
  encodeListingCursor,
  type ListingCursor,
} from "./cursor";
import { type ListingFeedInput } from "./feed-input";
import {
  listingFeedSelect,
  toListingDto,
  type ListingFeedRecord,
} from "./listing-dto";

interface RankedListingKey {
  id: string;
  statusRank: number;
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
          statusRank: lastKey.statusRank,
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
  const platformFilter = input.platforms
    ? Prisma.sql`AND platform::text IN (${Prisma.join(input.platforms)})`
    : Prisma.empty;
  const statusFilter = input.statuses
    ? Prisma.sql`AND status::text IN (${Prisma.join(input.statuses)})`
    : Prisma.empty;
  const categoryFilter = input.categories
    ? Prisma.sql`AND category IN (${Prisma.join(input.categories)})`
    : Prisma.empty;
  const locationFilter = input.locations
    ? Prisma.sql`AND location_texts && ARRAY[${Prisma.join(input.locations)}]::text[]`
    : Prisma.empty;
  const conditionFilter = input.conditions
    ? Prisma.sql`AND condition_text IN (${Prisma.join(input.conditions)})`
    : Prisma.empty;
  const searchPattern = input.q ? `%${escapeLikePattern(input.q)}%` : undefined;
  const searchFilter = searchPattern
    ? Prisma.sql`AND (
        title ILIKE ${searchPattern} ESCAPE CHR(92)
        OR description ILIKE ${searchPattern} ESCAPE CHR(92)
        OR COALESCE(brand, '') ILIKE ${searchPattern} ESCAPE CHR(92)
        OR COALESCE(category, '') ILIKE ${searchPattern} ESCAPE CHR(92)
        OR COALESCE(seller_name, '') ILIKE ${searchPattern} ESCAPE CHR(92)
      )`
    : Prisma.empty;
  const minPriceFilter =
    input.minPrice !== undefined
      ? Prisma.sql`AND price >= ${input.minPrice}`
      : Prisma.empty;
  const maxPriceFilter =
    input.maxPrice !== undefined
      ? Prisma.sql`AND price <= ${input.maxPrice}`
      : Prisma.empty;
  const cursorFilter = cursor
    ? Prisma.sql`
        WHERE
          "statusRank" > ${cursor.statusRank}
          OR (
            "statusRank" = ${cursor.statusRank}
            AND "effectiveAt" < ${cursor.effectiveAt}
          )
          OR (
            "statusRank" = ${cursor.statusRank}
            AND "effectiveAt" = ${cursor.effectiveAt}
            AND id < ${cursor.id}
          )
      `
    : Prisma.empty;

  return Prisma.sql`
    WITH ranked AS (
      SELECT
        id,
        CASE status::text
          WHEN 'sold' THEN 1
          ELSE 0
        END AS "statusRank",
        COALESCE(posted_at, first_fetched_at) AS "effectiveAt"
      FROM listings
      WHERE TRUE
        ${platformFilter}
        ${statusFilter}
        ${categoryFilter}
        ${locationFilter}
        ${conditionFilter}
        ${searchFilter}
        ${minPriceFilter}
        ${maxPriceFilter}
    )
    SELECT id, "statusRank", "effectiveAt"
    FROM ranked
    ${cursorFilter}
    ORDER BY "statusRank" ASC, "effectiveAt" DESC, id DESC
    LIMIT ${input.limit + 1}
  `;
}

function escapeLikePattern(value: string): string {
  return value.replace(/[\\%_]/g, "\\$&");
}
