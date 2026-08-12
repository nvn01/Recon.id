-- Expand: add a platform-scoped seller moderation table while preserving the
-- legacy cross-platform table for rollback compatibility.

CREATE TABLE "facebook_seller_platform_flags" (
  "id" TEXT NOT NULL,
  "platform" "listing_platform" NOT NULL,
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

  CONSTRAINT "facebook_seller_platform_flags_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "facebook_seller_platform_flags_seller_name_valid" CHECK (
    CHAR_LENGTH(BTRIM("seller_name")) BETWEEN 1 AND 120
    AND "normalized_seller_name" = normalize_seller_name("seller_name")
  ),
  CONSTRAINT "facebook_seller_platform_flags_reason_length" CHECK (
    "reason" IS NULL OR CHAR_LENGTH("reason") <= 500
  ),
  CONSTRAINT "facebook_seller_platform_flags_counts_valid" CHECK (
    ("recent_listing_count" IS NULL OR "recent_listing_count" >= 0)
    AND ("duplicate_listing_count" IS NULL OR "duplicate_listing_count" >= 0)
    AND ("duplicate_ratio" IS NULL OR "duplicate_ratio" BETWEEN 0 AND 1)
  ),
  CONSTRAINT "facebook_seller_platform_flags_facebook_only" CHECK (
    "platform" IN ('facebook'::"listing_platform", 'facebook_group'::"listing_platform")
  )
);

CREATE UNIQUE INDEX "facebook_seller_platform_flags_platform_normalized_key"
  ON "facebook_seller_platform_flags"("platform", "normalized_seller_name");
CREATE INDEX "facebook_seller_platform_flags_status_idx"
  ON "facebook_seller_platform_flags"("status");
CREATE INDEX "facebook_seller_platform_flags_platform_status_idx"
  ON "facebook_seller_platform_flags"("platform", "status");

-- The private Tailnet control room uses a separately scoped runtime role in
-- production. Staging does not necessarily provision this role.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'recon_admin') THEN
    GRANT SELECT, INSERT, UPDATE
      ON TABLE "facebook_seller_platform_flags" TO recon_admin;
  END IF;
END $$;
