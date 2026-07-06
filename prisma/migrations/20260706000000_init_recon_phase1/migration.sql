-- Initial RECON Phase 1 storage: core listings plus listing images only.

CREATE TYPE "listing_platform" AS ENUM ('reddit', 'instagram', 'facebook');
CREATE TYPE "listing_status" AS ENUM ('available', 'sold', 'unknown');

CREATE TABLE "listings" (
    "id" TEXT NOT NULL,
    "platform" "listing_platform" NOT NULL,
    "source_url" TEXT NOT NULL,
    "external_id" TEXT,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "price" INTEGER,
    "location_text" TEXT,
    "condition_text" TEXT,
    "seller_name" TEXT,
    "status" "listing_status" NOT NULL DEFAULT 'unknown',
    "posted_at" TIMESTAMP(3),
    "first_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "listings_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "listing_images" (
    "id" TEXT NOT NULL,
    "listing_id" TEXT NOT NULL,
    "source_url" TEXT NOT NULL,
    "position" INTEGER NOT NULL,
    "alt_text" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "listing_images_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "listings_source_url_key" ON "listings"("source_url");
CREATE INDEX "listings_platform_idx" ON "listings"("platform");
CREATE INDEX "listings_status_idx" ON "listings"("status");
CREATE INDEX "listings_last_seen_at_idx" ON "listings"("last_seen_at");
CREATE INDEX "listings_price_idx" ON "listings"("price");

CREATE UNIQUE INDEX "listing_images_listing_id_position_key" ON "listing_images"("listing_id", "position");
CREATE INDEX "listing_images_listing_id_idx" ON "listing_images"("listing_id");

ALTER TABLE "listing_images"
    ADD CONSTRAINT "listing_images_listing_id_fkey"
    FOREIGN KEY ("listing_id") REFERENCES "listings"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;
