# Listing API Context

Read this file with the root `AGENTS.md` when changing the Next.js/tRPC API.

## Current Contract

- `listings.feed` is the only listing procedure. It is public, read-only, and
  intended for the future RECON feed UI.
- Input accepts optional unique `platforms` and `statuses` arrays, a default
  limit of 24 capped at 50, and an opaque cursor capped at 512 characters.
- The response preserves the full normalized listing description and images,
  maps enum values to lowercase, adds the fixed `IDR` currency label, and does
  not expose Prisma timestamps such as `createdAt` or `updatedAt`.
- Do not add total counts to the cursor feed. They add a second changing query
  and are not needed for infinite scrolling.

## Ordering And Pagination

The canonical order is fixed:

```text
available -> unknown -> sold
COALESCE(posted_at, first_fetched_at) DESC
id DESC
```

Never sort the public feed by `lastFetchedAt`; scraper refreshes would move old
listings back to the top. The cursor contains a version, status rank, effective
timestamp, and ID. Changing this order is a breaking API change and requires
new cursor-version handling plus pagination regression tests.

`feed.ts` uses one parameterized Prisma SQL query for ranked IDs because the
status CASE expression and nullable timestamp fallback are not representable as
a normal Prisma cursor. It then uses one explicit Prisma `select` for records
and ordered images. Prisma may issue a separate batched relation query for the
images; that is still bounded and is not N+1. Keep this ranked-ID plus batched
readback shape, and never introduce `$queryRawUnsafe`.

## Security Boundary

- Listing and image URLs returned by the DTO must use HTTPS and contain no URL
  credentials. Unsafe image URLs are omitted; an unsafe primary listing URL
  fails closed.
- The API returns URLs only. It does not proxy, fetch, download, or cache remote
  images.
- Unexpected feed failures must return the generic error message "Unable to
  load listing feed." Server diagnostics may record the error class but must
  not log or return database messages, URLs, SQL, or credentials.
- `/api/*` responses receive strict JSON-oriented CSP and
  `Cache-Control: no-store`; the application-wide CSP remains report-only until
  UI nonce/hash work is implemented.
- Keep CORS same-origin. Public edge rate limiting belongs in Traefik or another
  shared gateway, not an in-memory Next.js counter.
- Staging currently uses a shared PostgreSQL superuser. Before public launch,
  give the web container a SELECT-only `DATABASE_URL` and keep scraper/migration
  credentials separate. Do not create or rotate those remote credentials
  without Novandra's explicit approval.

## Deferred Surface

Do not add connector health, scrape runs, listing writes, takedown/hide,
authentication, search, arbitrary sorting, or thumbnail caching until a product
or UI requirement calls for it.

## Verification

Run from the repository root:

```powershell
npm test
npm run test:coverage
npm run check
npm run build
```

The feed tests must cover input caps, cursor validation, ranked ordering,
filter parameterization, stable page boundaries, DTO allowlisting, and unsafe
URL handling. Use a bounded read-only staging smoke for real PostgreSQL query
behavior after feed-query changes.
