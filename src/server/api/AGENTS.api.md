# Listing API Context

Read this file with the root `AGENTS.md` when changing the Next.js/tRPC API.

## Current Contract

- `listings.feed`, `listings.facets`, and `listings.version` are public, read-only procedures used by
  the RECON discovery UI.
- Feed input accepts bounded unique platform, status, category, location, and
  condition arrays; an 80-character search query; integer minimum/maximum
  prices; a default limit of 24 capped at 50; and an opaque cursor capped at
  512 characters. The UI deliberately requests 12 rows per page.
- The response preserves the full normalized listing description and images,
  maps enum values to lowercase, adds the fixed `IDR` currency label and one
  `listedAt` date, and does not expose Prisma timestamps or scraper-only IDs.
- `listings.facets` returns bounded category, location, and condition summaries.
  Category summaries include count, public-safe minimum price, and an optional
  HTTPS cover image. Facets are navigation aids, not mutable catalog metadata.
- `listings.version` returns an opaque revision plus the current listing count.
  The UI uses the count delta to label unseen inserts, polls separately, and must
  not refetch visible feed data until the user activates the new-items control.
- Do not add total counts to the cursor feed. They add a second changing query
  and are not needed for infinite scrolling.

## Ordering And Pagination

The canonical order is fixed:

```text
available + unknown (same rank) -> sold
COALESCE(posted_at, first_fetched_at) DESC
id DESC
```

Never sort the public feed by `lastFetchedAt`; scraper refreshes would move old
listings back to the top. The cursor contains version 2, status rank, effective
timestamp, and ID. Version 1 cursors from the old three-rank ordering are
rejected. Changing this order is a breaking API change and requires new
cursor-version handling plus pagination regression tests.

`feed.ts` uses one parameterized Prisma SQL query for ranked IDs because the
status CASE expression and nullable timestamp fallback are not representable as
a normal Prisma cursor. It then uses one explicit Prisma `select` for records
and ordered images. Prisma may issue a separate batched relation query for the
images; that is still bounded and is not N+1. Keep this ranked-ID plus batched
readback shape, and never introduce `$queryRawUnsafe`.

All search and filter predicates must be applied in the ranked-ID query before
the page boundary. Search uses escaped parameterized `ILIKE` predicates; never
interpolate a raw search pattern or apply client-only filtering to one page.

## Security Boundary

- Listing and image URLs returned by the DTO must use HTTPS and contain no URL
  credentials. Unsafe image URLs are omitted; an unsafe primary listing URL
  fails closed.
- The API still returns URLs only and never performs network fetches. Instagram
  media is downloaded by the production AI manager on `ubserver1`, stored in
  Cloudflare R2, and recorded alongside the original source URL. For Instagram
  only, the DTO prefers a safe HTTPS `cachedUrl` and falls back to the original
  `sourceUrl`; Facebook and Reddit always use their original image URLs.
- Public prices below IDR 10,000 and known dummy sequences such as `12345` and
  `123456` are returned as unknown because historical values in those groups
  include seller placeholders. Contact-like, URL-like, multiline, and
  oversized location strings are omitted. Stored rows are not rewritten by
  this presentation rule.
- Unexpected feed failures must return the generic error message "Unable to
  load listing feed." Server diagnostics may record the error class but must
  not log or return database messages, URLs, SQL, or credentials.
- Unexpected facet failures must return the generic error message "Unable to
  load listing filters." with the same diagnostic restrictions.
- Unexpected listing-version failures must return "Unable to check for new
  listings" and must not expose timestamps or database details.
- `/api/*` responses receive strict JSON-oriented CSP and
  `Cache-Control: no-store`; the application-wide CSP remains report-only until
  UI nonce/hash work is implemented.
- Keep CORS same-origin. Public edge rate limiting belongs in Traefik or another
  shared gateway, not an in-memory Next.js counter.
- Staging currently uses a shared PostgreSQL superuser. Before public launch,
  give the web container a SELECT-only `DATABASE_URL` and keep scraper/migration
  credentials separate. Do not create or rotate those remote credentials
  without Novandra's explicit approval.
- Staging and production are separate self-contained Compose stacks. Each web
  container must resolve the `postgres` service on its own internal network;
  never add a staging database hostname or cross-environment fallback.

## Deferred Surface

Do not add connector health, scrape runs, listing writes, takedown/hide,
authentication, arbitrary sorting, or non-Instagram media caching until a
product or UI requirement calls for it.

## Verification

Run from the repository root:

```powershell
npm test
npm run test:coverage
npm run check
npm run build
```

The listing tests must cover input caps, cursor validation, ranked ordering,
search/filter parameterization, stable page boundaries, DTO allowlisting,
unsafe URL handling, public placeholder suppression, facets, and URL-to-query
mapping. Use a bounded read-only staging smoke for real PostgreSQL query
behavior after feed-query changes.
