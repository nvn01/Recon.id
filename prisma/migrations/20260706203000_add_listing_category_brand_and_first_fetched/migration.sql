-- Align listing storage with the Phase 2 parser contract.
-- Preserve existing timestamps and single-location values while moving to
-- scraper terminology and multi-location storage.

ALTER TABLE "listings"
    RENAME COLUMN "first_seen_at" TO "first_fetched_at";

ALTER TABLE "listings"
    ADD COLUMN "category" TEXT,
    ADD COLUMN "brand" TEXT,
    ADD COLUMN "location_texts" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

UPDATE "listings"
SET "location_texts" = ARRAY["location_text"]
WHERE "location_text" IS NOT NULL
  AND btrim("location_text") <> '';

ALTER TABLE "listings"
    DROP COLUMN "location_text";

CREATE INDEX "listings_category_idx" ON "listings"("category");
CREATE INDEX "listings_brand_idx" ON "listings"("brand");
