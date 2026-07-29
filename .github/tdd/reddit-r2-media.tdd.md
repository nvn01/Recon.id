# Reddit R2 Media TDD Evidence

## Source

Journeys were derived from the reported production failures and screenshots on
2026-07-29. No external plan file was used.

## User journeys

- As a RECON visitor, I receive the original Reddit image instead of a resized
  RSS thumbnail so cards and detail previews stay sharp.
- As a RECON visitor, I see each real Reddit gallery asset exactly once and in
  source order.
- As an operator, I add Reddit to the existing Instagram and Facebook Group R2
  worker while Facebook Marketplace remains origin-only.
- As an operator, I can inspect and repair historical Reddit image rows without
  writing until I explicitly pass `--apply`.

## RED checkpoint

Original RED commit: `504b5d7`; rebased commit: `1058e1e`.

Commands:

```text
python -m unittest scraper.tests.test_reddit_fetch scraper.tests.test_instagram_media_cache scraper.tests.test_instagram_media_worker scraper.tests.test_reddit_image_backfill
npm test -- src/server/listings/listing-dto.test.ts src/server/listings/facets.test.ts
```

Observed RED evidence:

- RSS and gallery metadata returned multiple resized variants for one asset
  instead of one `i.redd.it` original.
- `MediaR2Cache` and `scraper.reddit.backfill_images` did not exist.
- `PendingImage` had no platform and the worker SQL selected Instagram only.
- The DTO ignored a safe `production/reddit/...` cached URL.
- Facet SQL selected cached covers for Instagram only.

## GREEN checkpoint

Original GREEN commit: `704f4c9`; rebased commit: `6a7452d`.

Focused commands:

```text
python -m unittest scraper.tests.test_reddit_fetch scraper.tests.test_instagram_media_cache scraper.tests.test_instagram_media_worker scraper.tests.test_reddit_image_backfill
npm test -- src/server/listings/listing-dto.test.ts src/server/listings/facets.test.ts
```

Focused result: 20 Python tests passed and 11 TypeScript tests passed.

Final commands and results:

```text
python -m unittest discover -s scraper/tests -p "test_*.py"
151 tests passed

python -m compileall -q scraper
PASS

python -m ruff check scraper
All checks passed

npm run test:coverage
81 tests passed
Statements 91.5%, branches 87.94%, functions 94.73%, lines 93.83%

npx tsc --noEmit --incremental false
PASS

npm run check
PASS

npm run build
PASS, 17 routes generated

docker compose ... config --quiet
Local, staging, and production manifests passed with validation-only image tags
```

The clean build initially exposed a stale ignored Prisma client containing the
removed `FACEBOOK_GROUP` enum. `npm run db:generate` regenerated it from the
current three-platform schema; no generated files were committed.

## Test specification

| # | Guarantee | Evidence | Type | Result |
|---|---|---|---|---|
| 1 | Resized Reddit preview variants become one query-free original asset | `test_rss_images_use_original_reddit_assets_and_remove_thumbnail_duplicates` | Unit | PASS |
| 2 | Gallery metadata preserves item order and emits one original per item | `test_gallery_metadata_returns_one_original_image_per_item_in_gallery_order` | Unit | PASS |
| 3 | Reddit R2 objects use `production/reddit/...` and Reddit metadata | `test_reddit_upload_uses_a_separate_content_addressed_prefix` | Unit | PASS |
| 4 | Reddit and Instagram have separate strict source-host allowlists | `test_source_validation_allowlists_reddit_media_without_weakening_instagram` | Security unit | PASS |
| 5 | The durable worker selects Instagram, Reddit, and Facebook Groups but not Marketplace | `test_database_query_selects_all_r2_platforms_but_not_marketplace` | Integration-style unit | PASS |
| 6 | Reddit DTOs prefer only a platform-matching R2 URL | `uses the dedicated Reddit R2 image when it is present and safe` | API unit | PASS |
| 7 | A cross-platform R2 prefix is rejected and falls back to origin | `rejects a cached Reddit image stored under another platform prefix` | API security unit | PASS |
| 8 | Historical preview rows are canonicalized without losing gallery order | `test_desired_urls_upgrade_existing_previews_and_preserve_gallery_order` | Unit | PASS |
| 9 | Missing historical rows can use post RSS and the command is dry-run-first | `test_missing_existing_images_can_be_recovered_from_post_rss` plus CLI default | Unit/CLI | PASS |

## Bounded production evidence

Read-only PostgreSQL projection:

```text
listings=363
rowsBefore=492
rowsAfterCanonical=414
listingsChanged=349
duplicatesRemoved=78
missingListings=13
originalRedditUrlsAfter=412
```

A bounded original-image download through the new validation boundary returned
JPEG, 287,122 bytes, with a valid JPEG signature and SHA-256 hash. No R2 upload,
database write, deployment, or production backfill was performed.

## Known gaps and release gate

- The production runtime still returns `403` for Reddit detail JSON. Scheduled
  correctness therefore uses RSS originals and distinct asset paths; detail JSON
  remains optional.
- Individual post RSS recovery is intentionally limited to rows with no images,
  waits 15 seconds between requests by default, and stops further missing-image
  requests after a final `429`.
- The current production image already supports Instagram and Facebook Group
  caching. Reddit remains pending an explicitly approved staging/promotion and
  reviewed dry-run backfill.
