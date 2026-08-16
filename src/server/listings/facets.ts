import { Prisma } from "../../../generated/prisma";

import {
  isSafeCachedMediaUrl,
  isSafeHttpsUrl,
  normalizePublicPrice,
  sanitizePublicLocation,
} from "./listing-dto";
import {
  publicListingModerationJoins,
  publicListingVisibilityFilter,
} from "./visibility";

interface CategoryFacetRow {
  value: string;
  count: number;
  minPrice: number | null;
  coverImageUrl: string | null;
  coverImageCached: boolean;
  coverPlatform: string | null;
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
    const cachedPlatform = toDatabasePlatform(row.coverPlatform);

    return [
      {
        value,
        count: row.count,
        minPrice: normalizePublicPrice(row.minPrice),
        coverImageUrl:
          row.coverImageUrl &&
          (row.coverImageCached
            ? cachedPlatform !== null &&
              isSafeCachedMediaUrl(row.coverImageUrl, cachedPlatform)
            : isSafeHttpsUrl(row.coverImageUrl))
            ? row.coverImageUrl
            : null,
        coverAltText: sanitizeFacetText(row.coverAltText, 160),
      },
    ];
  });
  const locations = (locationResult as TextFacetRow[]).flatMap((row) => {
    const value = sanitizePublicLocation(row.value);
    return value && isPlausibleLocationFacet(value)
      ? [{ value, count: row.count }]
      : [];
  });
  const conditions = (conditionResult as TextFacetRow[]).flatMap((row) => {
    const value = sanitizeFacetText(row.value, 80);
    return value && isPlausibleConditionFacet(value)
      ? [{ value, count: row.count }]
      : [];
  });

  return { categories, locations, conditions };
}

function isPlausibleLocationFacet(value: string): boolean {
  if (value.length > 48 || /\d|%|https?:|www\.|@/i.test(value)) return false;
  return !/\b(?:harga|price|link|oren|cod|ongkir|kirim|ready|stok|stock|bekas|second|nego|wa|dm)\b/i.test(
    value,
  );
}

function isPlausibleConditionFacet(value: string): boolean {
  if (value.length > 32) return false;
  return /^(?:Baru(?:\s*\/\s*BNIB)?|BNIB|Like New|Second|Bekas(?:\s*-\s*(?:baik|normal|minus))?)$/i.test(
    value,
  );
}

function toDatabasePlatform(
  value: string | null,
): Parameters<typeof isSafeCachedMediaUrl>[1] | null {
  switch (value) {
    case "instagram":
      return "INSTAGRAM";
    case "reddit":
      return "REDDIT";
    case "facebook":
      return "FACEBOOK";
    case "facebook_group":
      return "FACEBOOK_GROUP";
    default:
      return null;
  }
}

const categoryFacetQuery = Prisma.sql`
  WITH visible_listings AS (
    SELECT listing.*
    FROM listings AS listing
    ${publicListingModerationJoins}
    WHERE TRUE
      ${publicListingVisibilityFilter}
  ), category_stats AS (
    SELECT
      category AS value,
      COUNT(*)::int AS count,
      (
        MIN(price) FILTER (
          WHERE price >= 10000 AND price NOT IN (12345, 123456)
        )
      )::int AS "minPrice"
    FROM visible_listings
    WHERE category IS NOT NULL AND BTRIM(category) <> ''
    GROUP BY category
  ), ranked_covers AS (
    SELECT
      id,
      category,
      platform,
      ROW_NUMBER() OVER (
        PARTITION BY category
        ORDER BY
          CASE status::text WHEN 'sold' THEN 1 ELSE 0 END ASC,
          COALESCE(posted_at, first_fetched_at) DESC,
          id DESC
      ) AS position
    FROM visible_listings
    WHERE category IS NOT NULL AND BTRIM(category) <> ''
  )
  SELECT
    stats.value,
    stats.count,
    stats."minPrice",
    CASE
      WHEN cover.platform IN (
        'instagram'::listing_platform,
        'reddit'::listing_platform,
        'facebook'::listing_platform,
        'facebook_group'::listing_platform
      )
        THEN COALESCE(image.cached_url, image.source_url)
      ELSE image.source_url
    END AS "coverImageUrl",
    (
      cover.platform IN (
        'instagram'::listing_platform,
        'reddit'::listing_platform,
        'facebook'::listing_platform,
        'facebook_group'::listing_platform
      )
      AND image.cached_url IS NOT NULL
    ) AS "coverImageCached",
    cover.platform::text AS "coverPlatform",
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
  WITH visible_listings AS (
    SELECT listing.*
    FROM listings AS listing
    ${publicListingModerationJoins}
    WHERE TRUE
      ${publicListingVisibilityFilter}
  )
  SELECT location AS value, COUNT(*)::int AS count
  FROM visible_listings
  CROSS JOIN LATERAL UNNEST(location_texts) AS location
  WHERE BTRIM(location) <> ''
  GROUP BY location
  ORDER BY count DESC, location ASC
  LIMIT 100
`;

const conditionFacetQuery = Prisma.sql`
  WITH visible_listings AS (
    SELECT listing.*
    FROM listings AS listing
    ${publicListingModerationJoins}
    WHERE TRUE
      ${publicListingVisibilityFilter}
  )
  SELECT condition_text AS value, COUNT(*)::int AS count
  FROM visible_listings
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
