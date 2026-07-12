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
          WHEN 'available' THEN 0
          WHEN 'unknown' THEN 1
          ELSE 2
        END AS "statusRank",
        COALESCE(posted_at, first_fetched_at) AS "effectiveAt"
      FROM listings
      WHERE TRUE
        ${platformFilter}
        ${statusFilter}
    )
    SELECT id, "statusRank", "effectiveAt"
    FROM ranked
    ${cursorFilter}
    ORDER BY "statusRank" ASC, "effectiveAt" DESC, id DESC
    LIMIT ${input.limit + 1}
  `;
}
