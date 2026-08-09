-- Persist Facebook account identity privately so a blocked seller remains
-- blocked after changing the public display name. Existing name-only flags
-- remain the fallback for historical listings without an account ID.

ALTER TABLE "listings"
  ADD COLUMN "seller_external_id" TEXT;

CREATE INDEX "listings_platform_seller_external_id_idx"
  ON "listings"("platform", "seller_external_id");

CREATE TABLE "facebook_seller_identity_flags" (
  "id" TEXT NOT NULL,
  "seller_external_id" TEXT NOT NULL,
  "seller_name" TEXT NOT NULL,
  "name_flag_id" TEXT NOT NULL,
  "status" "seller_moderation_status" NOT NULL,
  "source" "moderation_source" NOT NULL,
  "reason" TEXT,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "facebook_seller_identity_flags_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "facebook_seller_identity_flags_seller_external_id_valid" CHECK (
    CHAR_LENGTH(BTRIM("seller_external_id")) BETWEEN 1 AND 120
  ),
  CONSTRAINT "facebook_seller_identity_flags_seller_name_valid" CHECK (
    CHAR_LENGTH(BTRIM("seller_name")) BETWEEN 1 AND 120
  ),
  CONSTRAINT "facebook_seller_identity_flags_reason_length" CHECK (
    "reason" IS NULL OR CHAR_LENGTH("reason") <= 500
  ),
  CONSTRAINT "facebook_seller_identity_flags_name_flag_id_fkey"
    FOREIGN KEY ("name_flag_id") REFERENCES "facebook_seller_flags"("id")
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "facebook_seller_identity_flags_seller_external_id_key"
  ON "facebook_seller_identity_flags"("seller_external_id");
CREATE INDEX "facebook_seller_identity_flags_status_idx"
  ON "facebook_seller_identity_flags"("status");
CREATE INDEX "facebook_seller_identity_flags_name_flag_id_idx"
  ON "facebook_seller_identity_flags"("name_flag_id");

CREATE FUNCTION sync_facebook_name_flag_identities()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE "facebook_seller_identity_flags"
  SET "seller_name" = NEW."seller_name",
      "status" = NEW."status",
      "source" = NEW."source",
      "reason" = NEW."reason",
      "updated_at" = CURRENT_TIMESTAMP
  WHERE "name_flag_id" = NEW."id";

  INSERT INTO "facebook_seller_identity_flags" (
    "id", "seller_external_id", "seller_name", "name_flag_id",
    "status", "source", "reason"
  )
  SELECT DISTINCT ON (listing."seller_external_id")
    'fsi_' || MD5(NEW."id" || ':' || listing."seller_external_id"),
    listing."seller_external_id",
    COALESCE(listing."seller_name", NEW."seller_name"),
    NEW."id",
    NEW."status",
    NEW."source",
    NEW."reason"
  FROM "listings" AS listing
  WHERE listing."platform" = 'facebook'::"listing_platform"
    AND listing."seller_external_id" IS NOT NULL
    AND normalize_seller_name(listing."seller_name") = NEW."normalized_seller_name"
  ON CONFLICT ("seller_external_id") DO UPDATE SET
    "seller_name" = EXCLUDED."seller_name",
    "name_flag_id" = EXCLUDED."name_flag_id",
    "status" = EXCLUDED."status",
    "source" = EXCLUDED."source",
    "reason" = EXCLUDED."reason",
    "updated_at" = CURRENT_TIMESTAMP;

  RETURN NEW;
END;
$$;

CREATE TRIGGER "facebook_name_flag_identities_sync"
AFTER INSERT OR UPDATE OF "seller_name", "normalized_seller_name", "status", "source", "reason"
ON "facebook_seller_flags"
FOR EACH ROW
EXECUTE FUNCTION sync_facebook_name_flag_identities();

CREATE FUNCTION sync_facebook_listing_identity_flag()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW."platform" = 'facebook'::"listing_platform"
     AND NEW."seller_external_id" IS NOT NULL
     AND NEW."seller_name" IS NOT NULL THEN
    INSERT INTO "facebook_seller_identity_flags" (
      "id", "seller_external_id", "seller_name", "name_flag_id",
      "status", "source", "reason"
    )
    SELECT
      'fsi_' || MD5(name_flag."id" || ':' || NEW."seller_external_id"),
      NEW."seller_external_id",
      NEW."seller_name",
      name_flag."id",
      name_flag."status",
      name_flag."source",
      name_flag."reason"
    FROM "facebook_seller_flags" AS name_flag
    WHERE name_flag."normalized_seller_name" = normalize_seller_name(NEW."seller_name")
    ON CONFLICT ("seller_external_id") DO UPDATE SET
      "seller_name" = EXCLUDED."seller_name",
      "name_flag_id" = EXCLUDED."name_flag_id",
      "status" = EXCLUDED."status",
      "source" = EXCLUDED."source",
      "reason" = EXCLUDED."reason",
      "updated_at" = CURRENT_TIMESTAMP;
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER "facebook_listing_identity_flag_sync"
AFTER INSERT OR UPDATE OF "seller_external_id", "seller_name"
ON "listings"
FOR EACH ROW
EXECUTE FUNCTION sync_facebook_listing_identity_flag();

-- Backfill identity flags for seller names that are already moderated.
UPDATE "facebook_seller_flags"
SET "status" = "status";
