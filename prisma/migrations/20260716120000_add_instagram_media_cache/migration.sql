ALTER TABLE "listing_images"
ADD COLUMN "cached_url" TEXT,
ADD COLUMN "storage_key" TEXT,
ADD COLUMN "content_hash" TEXT,
ADD COLUMN "content_type" TEXT,
ADD COLUMN "byte_size" INTEGER,
ADD COLUMN "cached_at" TIMESTAMP(3);

ALTER TABLE "listing_images"
ADD CONSTRAINT "listing_images_cached_metadata_consistent" CHECK (
  ("cached_url" IS NULL
    AND "storage_key" IS NULL
    AND "content_hash" IS NULL
    AND "content_type" IS NULL
    AND "byte_size" IS NULL
    AND "cached_at" IS NULL)
  OR
  ("cached_url" IS NOT NULL
    AND "storage_key" IS NOT NULL
    AND "content_hash" IS NOT NULL
    AND "content_type" IS NOT NULL
    AND "byte_size" IS NOT NULL
    AND "byte_size" > 0
    AND "cached_at" IS NOT NULL)
);
