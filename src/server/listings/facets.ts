import { Prisma } from "../../../generated/prisma";

import {
  isSafeHttpsUrl,
  normalizePublicPrice,
  sanitizePublicLocation,
} from "./listing-dto";

interface CategoryFacetRow {
  value: string;
  count: number;
  minPrice: number | null;
  coverImageUrl: string | null;
  coverAltText: string | null;
}

interface TextFacetRow {
  value: string;
  count: number;
}

export interface ListingFacetsDatabase {
  $queryRaw(query: Prisma.Sql): Promise<unknown>;
}

export async function getListingFacets(db: ListingFacetsDatabase) {
  const [categoryResult, locationResult, conditionResult] = await Promise.all([
    db.$queryRaw(categoryFacetQuery),
    db.$queryRaw(locationFacetQuery),
    db.$queryRaw(conditionFacetQuery),
  ]);

  const categories = (categoryResult as CategoryFacetRow[]).flatMap((row) => {
    const value = sanitizeFacetText(row.value, 64);
    if (!value) return [];

    return [
      {
        value,
        count: row.count,
        minPrice: normalizePublicPrice(row.minPrice),
        coverImageUrl:
          row.coverImageUrl && isSafeHttpsUrl(row.coverImageUrl)
            ? row.coverImageUrl
            : null,
        coverAltText: sanitizeFacetText(row.coverAltText, 160),
      },
    ];
  });
  const locations = (locationResult as TextFacetRow[]).flatMap((row) => {
    const value = sanitizePublicLocation(row.value);
    return value ? [{ value, count: row.count }] : [];
  });
  const conditions = (conditionResult as TextFacetRow[]).flatMap((row) => {
    const value = sanitizeFacetText(row.value, 80);
    return value ? [{ value, count: row.count }] : [];
  });

  return { categories, locations, conditions };
}

const categoryFacetQuery = Prisma.sql`
  WITH category_stats AS (
    SELECT
      category AS value,
      COUNT(*)::int AS count,
      (
        MIN(price) FILTER (
          WHERE price >= 10000 AND price NOT IN (12345, 123456)
        )
      )::int AS "minPrice"
    FROM listings
    WHERE category IS NOT NULL AND BTRIM(category) <> ''
    GROUP BY category
  ), ranked_covers AS (
    SELECT
      id,
      category,
      ROW_NUMBER() OVER (
        PARTITION BY category
        ORDER BY
          CASE status::text WHEN 'sold' THEN 1 ELSE 0 END ASC,
          COALESCE(posted_at, first_fetched_at) DESC,
          id DESC
      ) AS position
    FROM listings
    WHERE category IS NOT NULL AND BTRIM(category) <> ''
  )
  SELECT
    stats.value,
    stats.count,
    stats."minPrice",
    image.source_url AS "coverImageUrl",
    image.alt_text AS "coverAltText"
  FROM category_stats AS stats
  LEFT JOIN ranked_covers AS cover
    ON cover.category = stats.value AND cover.position = 1
  LEFT JOIN listing_images AS image
    ON image.listing_id = cover.id AND image.position = 0
  ORDER BY stats.count DESC, stats.value ASC
  LIMIT 50
`;

const locationFacetQuery = Prisma.sql`
  SELECT location AS value, COUNT(*)::int AS count
  FROM listings
  CROSS JOIN LATERAL UNNEST(location_texts) AS location
  WHERE BTRIM(location) <> ''
  GROUP BY location
  ORDER BY count DESC, location ASC
  LIMIT 100
`;

const conditionFacetQuery = Prisma.sql`
  SELECT condition_text AS value, COUNT(*)::int AS count
  FROM listings
  WHERE condition_text IS NOT NULL AND BTRIM(condition_text) <> ''
  GROUP BY condition_text
  ORDER BY count DESC, condition_text ASC
  LIMIT 50
`;

function sanitizeFacetText(
  value: string | null,
  maxLength: number,
): string | null {
  const text = value?.trim() ?? "";
  if (!text || text.length > maxLength || /[\r\n]/.test(text)) return null;
  return text;
}
