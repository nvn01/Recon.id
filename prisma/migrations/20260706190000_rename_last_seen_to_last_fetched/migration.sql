-- Rename system refresh terminology from "seen" to "fetched".
-- This preserves existing timestamp values while making the column describe
-- scraper activity instead of user presence.

ALTER TABLE "listings"
    RENAME COLUMN "last_seen_at" TO "last_fetched_at";

ALTER INDEX IF EXISTS "listings_last_seen_at_idx"
    RENAME TO "listings_last_fetched_at_idx";
