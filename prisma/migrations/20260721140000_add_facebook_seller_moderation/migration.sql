CREATE TYPE "seller_moderation_status" AS ENUM ('review', 'blocked', 'allowlisted');
CREATE TYPE "moderation_source" AS ENUM ('auto', 'manual');

CREATE FUNCTION normalize_seller_name(value TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
  SELECT NULLIF(REGEXP_REPLACE(LOWER(BTRIM(value)), '\s+', ' ', 'g'), '');
$$;

CREATE TABLE "listing_moderation" (
  "listing_id" TEXT NOT NULL,
  "hidden" BOOLEAN NOT NULL DEFAULT false,
  "seller_name_override" TEXT,
  "reason" TEXT,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "listing_moderation_pkey" PRIMARY KEY ("listing_id"),
  CONSTRAINT "listing_moderation_seller_name_override_valid" CHECK (
    "seller_name_override" IS NULL
    OR (CHAR_LENGTH(BTRIM("seller_name_override")) BETWEEN 1 AND 120)
  ),
  CONSTRAINT "listing_moderation_reason_length" CHECK (
    "reason" IS NULL OR CHAR_LENGTH("reason") <= 500
  )
);

CREATE TABLE "facebook_seller_flags" (
  "id" TEXT NOT NULL,
  "seller_name" TEXT NOT NULL,
  "normalized_seller_name" TEXT NOT NULL,
  "status" "seller_moderation_status" NOT NULL,
  "source" "moderation_source" NOT NULL,
  "reason" TEXT,
  "recent_listing_count" INTEGER,
  "duplicate_listing_count" INTEGER,
  "duplicate_ratio" DOUBLE PRECISION,
  "first_flagged_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "last_evaluated_at" TIMESTAMP(3),
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "facebook_seller_flags_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "facebook_seller_flags_seller_name_valid" CHECK (
    CHAR_LENGTH(BTRIM("seller_name")) BETWEEN 1 AND 120
    AND "normalized_seller_name" = normalize_seller_name("seller_name")
  ),
  CONSTRAINT "facebook_seller_flags_reason_length" CHECK (
    "reason" IS NULL OR CHAR_LENGTH("reason") <= 500
  ),
  CONSTRAINT "facebook_seller_flags_counts_valid" CHECK (
    ("recent_listing_count" IS NULL OR "recent_listing_count" >= 0)
    AND ("duplicate_listing_count" IS NULL OR "duplicate_listing_count" >= 0)
    AND ("duplicate_ratio" IS NULL OR "duplicate_ratio" BETWEEN 0 AND 1)
  )
);

CREATE TABLE "platform_controls" (
  "platform" "listing_platform" NOT NULL,
  "public_visible" BOOLEAN NOT NULL DEFAULT true,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "platform_controls_pkey" PRIMARY KEY ("platform")
);

CREATE TABLE "facebook_spam_settings" (
  "id" INTEGER NOT NULL DEFAULT 1,
  "enabled" BOOLEAN NOT NULL DEFAULT true,
  "auto_block_enabled" BOOLEAN NOT NULL DEFAULT true,
  "window_days" INTEGER NOT NULL DEFAULT 7,
  "min_listings" INTEGER NOT NULL DEFAULT 5,
  "min_duplicate_listings" INTEGER NOT NULL DEFAULT 4,
  "min_duplicate_ratio" DOUBLE PRECISION NOT NULL DEFAULT 0.7,
  "scan_interval_minutes" INTEGER NOT NULL DEFAULT 15,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "facebook_spam_settings_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "facebook_spam_settings_singleton" CHECK ("id" = 1),
  CONSTRAINT "facebook_spam_settings_bounds" CHECK (
    "window_days" BETWEEN 1 AND 30
    AND "min_listings" BETWEEN 2 AND 100
    AND "min_duplicate_listings" BETWEEN 2 AND 100
    AND "min_duplicate_ratio" BETWEEN 0.5 AND 1
    AND "scan_interval_minutes" BETWEEN 5 AND 1440
  )
);

CREATE TABLE "moderation_events" (
  "id" BIGSERIAL NOT NULL,
  "actor" TEXT NOT NULL,
  "action" TEXT NOT NULL,
  "entity_type" TEXT NOT NULL,
  "entity_id" TEXT NOT NULL,
  "details" JSONB NOT NULL DEFAULT '{}',
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "moderation_events_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "moderation_events_text_valid" CHECK (
    CHAR_LENGTH("actor") BETWEEN 1 AND 80
    AND CHAR_LENGTH("action") BETWEEN 1 AND 80
    AND CHAR_LENGTH("entity_type") BETWEEN 1 AND 80
    AND CHAR_LENGTH("entity_id") BETWEEN 1 AND 200
  )
);

CREATE INDEX "listing_moderation_hidden_idx" ON "listing_moderation"("hidden");
CREATE UNIQUE INDEX "facebook_seller_flags_normalized_seller_name_key"
  ON "facebook_seller_flags"("normalized_seller_name");
CREATE INDEX "facebook_seller_flags_status_idx" ON "facebook_seller_flags"("status");
CREATE INDEX "moderation_events_created_at_idx" ON "moderation_events"("created_at");

ALTER TABLE "listing_moderation"
  ADD CONSTRAINT "listing_moderation_listing_id_fkey"
  FOREIGN KEY ("listing_id") REFERENCES "listings"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

INSERT INTO "platform_controls" ("platform")
VALUES ('reddit'), ('instagram'), ('facebook');

INSERT INTO "facebook_spam_settings" ("id") VALUES (1);
