# Phase 4 Backend API TDD Evidence

## Source

The journeys and acceptance criteria came from `.plan/first-pass.html`, the
Phase 4 feature model approved in this task, and the live normalized staging
database. No separate implementation plan was executed.

## User Journeys

- As a visitor, I can read a bounded listing feed without authentication.
- As a visitor, I can filter the feed by platform and listing status.
- As a visitor, I see available listings before unknown and sold listings,
  without duplicates while loading later pages.
- As the future UI, I receive the normalized DB-shaped listing fields and safe
  ordered image URLs without internal Prisma fields.

## RED And GREEN

- RED: `npm test` executed four new suites and failed because `cursor`,
  `feed-input`, `feed`, and `listing-dto` did not exist. Checkpoint commit:
  `6eccd88 test: define listing feed API contract`.
- GREEN: `npm test` passed 27 tests after the implementation. Checkpoint
  commit: `db837ca feat: add read-only listing feed API`.
- SECURITY RED: the router test proved that an unexpected database error kept
  its internal connection message. Checkpoint commit:
  `febed50 test: prevent listing API error disclosure`.
- SECURITY GREEN: unexpected failures now return a generic
  `INTERNAL_SERVER_ERROR` while server logs keep only the error class.
  Checkpoint commit: `e70bd2c fix: hide listing API internal errors`.
- Coverage: `npm run test:coverage` passed after the security fix with 100%
  statements, 92.59% branches, 100% functions, and 100% lines for the Phase 4
  target.

## Test Specification

| Guarantee                                                                                       | Evidence                               | Type        | Result |
| ----------------------------------------------------------------------------------------------- | -------------------------------------- | ----------- | ------ |
| Defaults, enum allowlists, unique filters, cursor length, and `1..50` page cap are validated    | `feed-input.test.ts`                   | Unit        | PASS   |
| Cursor versions and values round-trip and malformed cursors fail safely                         | `cursor.test.ts`                       | Unit        | PASS   |
| DTO preserves normalized fields, lowercases enums, orders images, and removes unsafe image URLs | `listing-dto.test.ts`                  | Unit        | PASS   |
| Ranked IDs remain ordered, pagination uses `limit + 1`, and filters/cursors are SQL parameters  | `feed.test.ts`                         | Service     | PASS   |
| The tRPC router exposes default reads and translates invalid cursors to `BAD_REQUEST`           | `listings.test.ts`                     | API         | PASS   |
| Unexpected database failures cannot expose internal connection or Prisma messages               | `listings.test.ts`                     | Security    | PASS   |
| Every live staging page is duplicate-free and follows status/effective-time/ID order            | bounded read-only staging Vitest smoke | Integration | PASS   |
| Live Instagram sold filtering returns only Instagram sold rows                                  | bounded read-only staging Vitest smoke | Integration | PASS   |

## Verification Commands

```text
npm test
npm run test:coverage
npm run typecheck
npx vitest run .codex-runtime/staging-feed.integration.test.ts --config vitest.config.ts
```

The staging integration smoke passed 2/2 tests against the current database.
It performed reads only and did not deploy or modify staging state.

## Known Gaps

- The current staging PostgreSQL `recon` role is a superuser with write and
  truncate privileges. Split web reader, scraper writer, and migration owner
  credentials before public launch.
- Public edge rate limiting is not configured in this repository because the
  private Traefik/Compose runtime is outside the tracked project files.
- No UI E2E test exists yet because Phase 5 UI is intentionally not built.
