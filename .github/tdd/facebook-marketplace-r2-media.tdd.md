# Facebook Marketplace R2 Media TDD Evidence

## Source and journey

No plan file was supplied. The journey was derived from the production incident:
as a RECON visitor, I want Marketplace cards to use durable R2 images so that
temporary Facebook CDN links do not turn recent cards into blank placeholders.

## RED evidence

- `python -m unittest scraper.tests.test_instagram_media_cache scraper.tests.test_instagram_media_worker`
  failed because `facebook` was unsupported and absent from the worker query.
- `npx vitest run src/server/listings/listing-dto.test.ts`
  failed because Marketplace cached URLs fell back to the Facebook source URL.
- `npx vitest run src/server/listings/facets.test.ts`
  failed because a cached `production/facebook/` category cover was rejected.

## GREEN evidence

| Guarantee | Test or command | Result |
|---|---|---|
| Marketplace CDN hosts are allowlisted without allowing arbitrary hosts | `scraper.tests.test_instagram_media_cache` | PASS |
| Marketplace objects use the isolated `production/facebook/` prefix | `scraper.tests.test_instagram_media_cache` | PASS |
| The worker selects only Marketplace images first fetched within 24 hours | `scraper.tests.test_instagram_media_worker` | PASS |
| Feed DTO accepts only a platform-matching Marketplace R2 URL | `src/server/listings/listing-dto.test.ts` | PASS |
| Category facets accept a platform-matching Marketplace R2 cover | `src/server/listings/facets.test.ts` | PASS |
| Python lint, web tests, TypeScript, lint, and production build remain valid | `python -m ruff check scraper`; `npm test`; `npm run check`; `npm run build` | PASS |

## Coverage and known gaps

`npm run test:coverage` passed with 89.5% statements, 86.7% branches, 94.87%
functions, and 91.61% lines. Historical Marketplace rows older than 24 hours are
intentionally not retried because their signed source URLs may already be
expired. They keep the existing source-URL fallback; fresh and future rows are
the bounded recovery path.

The complete ignored/local scraper test suite has one unrelated pre-existing
failure in `test_storage_layer.py` for the removed
`upsert_ai_rejections_with_connection` helper. Both media-focused scraper test
modules pass.
