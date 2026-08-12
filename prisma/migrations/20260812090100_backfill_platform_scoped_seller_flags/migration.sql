-- Migrate legacy global flags only when one evidence platform can be proven.
-- Auto flags are Marketplace-only because the scanner has always queried
-- listing.platform = 'facebook'. Manual flags use the original moderation
-- event platform, falling back to the seller's single stored platform.

DO $$
DECLARE
  unresolved_count INTEGER;
BEGIN
  WITH event_platforms AS (
    SELECT
      normalize_seller_name(
        COALESCE(NULLIF(details->>'sellerName', ''), entity_id)
      ) AS normalized_seller_name,
      ARRAY_AGG(DISTINCT details->>'platform') FILTER (
        WHERE details->>'platform' IN ('facebook', 'facebook_group')
      ) AS platforms
    FROM moderation_events
    WHERE action IN ('block_seller', 'admin_backfill')
       OR entity_type = 'facebook_seller'
    GROUP BY 1
  ),
  listing_platforms AS (
    SELECT
      normalize_seller_name(
        COALESCE(moderation.seller_name_override, listing.seller_name)
      ) AS normalized_seller_name,
      ARRAY_AGG(DISTINCT listing.platform::text) AS platforms
    FROM listings AS listing
    LEFT JOIN listing_moderation AS moderation
      ON moderation.listing_id = listing.id
    WHERE listing.platform IN (
      'facebook'::listing_platform,
      'facebook_group'::listing_platform
    )
      AND NULLIF(
        BTRIM(COALESCE(moderation.seller_name_override, listing.seller_name)),
        ''
      ) IS NOT NULL
    GROUP BY 1
  ),
  mapped AS (
    SELECT
      legacy.normalized_seller_name,
      CASE
        WHEN legacy.source::text = 'auto' THEN 'facebook'
        WHEN CARDINALITY(event.platforms) = 1 THEN event.platforms[1]
        WHEN CARDINALITY(stored.platforms) = 1 THEN stored.platforms[1]
      END AS platform
    FROM facebook_seller_flags AS legacy
    LEFT JOIN event_platforms AS event
      ON event.normalized_seller_name = legacy.normalized_seller_name
    LEFT JOIN listing_platforms AS stored
      ON stored.normalized_seller_name = legacy.normalized_seller_name
  )
  SELECT COUNT(*) INTO unresolved_count
  FROM mapped
  WHERE platform IS NULL;

  IF unresolved_count > 0 THEN
    RAISE EXCEPTION
      'Cannot safely map % legacy Facebook seller flags to one platform',
      unresolved_count;
  END IF;
END $$;

WITH event_platforms AS (
  SELECT
    normalize_seller_name(
      COALESCE(NULLIF(details->>'sellerName', ''), entity_id)
    ) AS normalized_seller_name,
    ARRAY_AGG(DISTINCT details->>'platform') FILTER (
      WHERE details->>'platform' IN ('facebook', 'facebook_group')
    ) AS platforms
  FROM moderation_events
  WHERE action IN ('block_seller', 'admin_backfill')
     OR entity_type = 'facebook_seller'
  GROUP BY 1
),
listing_platforms AS (
  SELECT
    normalize_seller_name(
      COALESCE(moderation.seller_name_override, listing.seller_name)
    ) AS normalized_seller_name,
    ARRAY_AGG(DISTINCT listing.platform::text) AS platforms
  FROM listings AS listing
  LEFT JOIN listing_moderation AS moderation
    ON moderation.listing_id = listing.id
  WHERE listing.platform IN (
    'facebook'::listing_platform,
    'facebook_group'::listing_platform
  )
    AND NULLIF(
      BTRIM(COALESCE(moderation.seller_name_override, listing.seller_name)),
      ''
    ) IS NOT NULL
  GROUP BY 1
),
mapped AS (
  SELECT
    legacy.*,
    CASE
      WHEN legacy.source::text = 'auto' THEN 'facebook'
      WHEN CARDINALITY(event.platforms) = 1 THEN event.platforms[1]
      WHEN CARDINALITY(stored.platforms) = 1 THEN stored.platforms[1]
    END AS platform
  FROM facebook_seller_flags AS legacy
  LEFT JOIN event_platforms AS event
    ON event.normalized_seller_name = legacy.normalized_seller_name
  LEFT JOIN listing_platforms AS stored
    ON stored.normalized_seller_name = legacy.normalized_seller_name
)
INSERT INTO facebook_seller_platform_flags (
  id,
  platform,
  seller_name,
  normalized_seller_name,
  status,
  source,
  reason,
  recent_listing_count,
  duplicate_listing_count,
  duplicate_ratio,
  first_flagged_at,
  last_evaluated_at,
  created_at,
  updated_at
)
SELECT
  id,
  platform::listing_platform,
  seller_name,
  normalized_seller_name,
  status,
  source,
  reason,
  recent_listing_count,
  duplicate_listing_count,
  duplicate_ratio,
  first_flagged_at,
  last_evaluated_at,
  created_at,
  updated_at
FROM mapped;
