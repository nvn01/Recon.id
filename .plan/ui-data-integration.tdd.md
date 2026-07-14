# UI data integration TDD evidence

Date: 2026-07-14

## User journeys

1. Open a collection or platform route and receive the first 12 real listings from the read-only cursor feed.
2. Apply platform, availability, price, condition, location, or search filters and keep that state in the URL and API query key.
3. Choose **Muat temuan berikutnya** to request only the next cursor page and append it without refetching the full catalog.
4. Open a listing, inspect its available image/details, and continue to the HTTPS source URL.
5. Receive explicit loading, retry, empty, end-of-feed, missing-image, and missing-field states.

## RED

- Added failing contract tests for URL-to-API mapping, real collection/category mapping, 12-row queries, public DTO allowlisting, facets, and placeholder-price handling.
- Confirmed the intended baseline: 7 new contract files failed while the existing 27 backend tests continued to pass.
- Commits: `dd6b4a8`, `528138a`, and `0a250d3`.

## GREEN

- Replaced dummy listing imports with typed public API data.
- Added parameterized server-side filters and search without changing cursor ordering.
- Added a bounded read-only facets query.
- Added public DTO presentation guards without mutating stored records.
- Wired manual cursor pagination, server prefetch/hydration, retry/empty/loading states, and direct HTTPS image fallbacks.

## Verification

- `npm test`
- `npm run test:coverage`
- `npm run check`
- `npm run build`
- `npx prisma validate`
- staging and production `docker compose ... config --quiet`
- `git diff --check`
- Chrome desktop and 390 x 844 mobile interaction checks

Docker Desktop was unavailable for the final local browser session, so the browser deliberately exercised the generic database-error state. Filter/search URL behavior, responsive layout, error privacy, and request shape were still verified. The new SQL shapes were checked read-only against the staging PostgreSQL container. No scraper command, container restart, image deploy, write query, or data migration was performed.
