import { createHash } from "node:crypto";

import { Prisma } from "../../../generated/prisma";
import {
  publicListingModerationJoins,
  publicListingVisibilityFilter,
} from "./visibility";

interface ListingVersionRow {
  rowCount: string;
  latestFirstFetchedAt: Date | null;
}

export interface ListingVersionDatabase {
  $queryRaw(query: Prisma.Sql): Promise<unknown>;
}

export async function getListingVersion(db: ListingVersionDatabase) {
  const result = (await db.$queryRaw(listingVersionQuery)) as ListingVersionRow[];
  const row = result[0] ?? { rowCount: "0", latestFirstFetchedAt: null };
  const fingerprint = `${row.rowCount}\0${row.latestFirstFetchedAt?.toISOString() ?? "empty"}`;

  return {
    revision: createHash("sha256").update(fingerprint).digest("base64url"),
    totalCount: Number.parseInt(row.rowCount, 10) || 0,
  };
}

const listingVersionQuery = Prisma.sql`
  SELECT
    COUNT(*)::text AS "rowCount",
    MAX(first_fetched_at) AS "latestFirstFetchedAt"
  FROM listings AS listing
  ${publicListingModerationJoins}
  WHERE TRUE
    ${publicListingVisibilityFilter}
`;
