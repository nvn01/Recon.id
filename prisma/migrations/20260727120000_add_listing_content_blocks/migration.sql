CREATE TYPE "listing_block_field" AS ENUM ('title', 'description');

CREATE FUNCTION normalize_listing_content(value TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
  SELECT NULLIF(
    REGEXP_REPLACE(
      LOWER(BTRIM(value)),
      '[^[:alnum:]]+',
      ' ',
      'g'
    ),
    ''
  );
$$;

CREATE TABLE "listing_content_blocks" (
  "id" TEXT NOT NULL,
  "platform" "listing_platform" NOT NULL,
  "field" "listing_block_field" NOT NULL,
  "content_hash" TEXT NOT NULL,
  "normalized_value" TEXT NOT NULL,
  "display_value" TEXT NOT NULL,
  "reason" TEXT,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "listing_content_blocks_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "listing_content_blocks_hash_valid" CHECK (
    "content_hash" ~ '^[0-9a-f]{64}$'
  ),
  CONSTRAINT "listing_content_blocks_value_valid" CHECK (
    CHAR_LENGTH("normalized_value") BETWEEN 1 AND 10000
    AND CHAR_LENGTH("display_value") BETWEEN 1 AND 10000
  ),
  CONSTRAINT "listing_content_blocks_reason_length" CHECK (
    "reason" IS NULL OR CHAR_LENGTH("reason") <= 500
  )
);

CREATE UNIQUE INDEX "listing_content_blocks_platform_field_hash_key"
  ON "listing_content_blocks"("platform", "field", "content_hash");
CREATE INDEX "listing_content_blocks_platform_field_idx"
  ON "listing_content_blocks"("platform", "field");
