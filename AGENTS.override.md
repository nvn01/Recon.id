# Recon Phase 1 Local Context

Read this file together with the root `AGENTS.md` when working from the repository root. This override records the Phase 1 database/web baseline and the operational notes left after the first local verification pass.

## Current Baseline

- Phase 1 database scope is intentionally small: PostgreSQL tables `listings` and `listing_images` only.
- Prisma is the source of truth for the schema in `prisma/schema.prisma`.
- The initial migration is `prisma/migrations/20260706000000_init_recon_phase1/migration.sql`.
- `source_url` is unique on listings and is the current idempotency anchor.
- `listing_images` are owned by listings and cascade-delete with the parent listing.
- Scraper config, source targets, scrape-run logs, connector health, and parser sample evidence are intentionally outside PostgreSQL for v1.
- The root Next app is not the product UI yet. It is a Phase 1 startup surface with a public read-only tRPC health route.

## What Changed In Phase 1

- Removed the T3 starter `Post` model, router, and UI component before creating the real Recon migration.
- Added Recon listing and listing image models with platform/status enums and the expected indexes.
- Added `scripts/db-smoke.mjs` to verify insert, image relation, readback, unique `source_url`, and cleanup behavior.
- Added `db:generate`, `db:migrate:dev`, and `db:smoke` package scripts.
- Added basic security headers in `next.config.js`; CSP is report-only for now.
- Updated the startup page and metadata so the app no longer looks like an untouched T3 scaffold.
- Explicitly ignored `.codex-runtime/` in Git and Docker context after local dev-server logs were created.

## Issues Faced

- Local Docker image build produced a usable `recons-web:latest` image but `docker compose build web` exited nonzero when Docker reported the image tag already existed. Containerized checks still passed using the produced image. If this repeats, inspect the existing image/tag before changing Dockerfile behavior.
- `npm audit` reports the known `next -> postcss@8.4.31` advisory. Do not run `npm audit fix --force`; it proposes an unacceptable downgrade path. Track this separately from Phase 1 closure.
- The dev server writes logs under `.codex-runtime/`. Keep that directory local-only.
- Facebook Marketplace probing uses a local Playwright/session proof path in `scraper/facebook/`. It is not connected to Phase 1 ingestion and must not be promoted without explicit legal/platform/account-risk review.

## Verification Log

Commands that passed during Phase 1 closeout:

```text
npx prisma validate
npx prisma format
npx prisma migrate deploy
npx prisma migrate status
npm run db:smoke
npm run check
npm run build
docker run --rm --network recons_default -e DATABASE_URL=... -e NODE_ENV=test recons-web:latest sh -c "npx prisma migrate deploy && npm run db:smoke"
docker run --rm --network recons_default -e DATABASE_URL=... -e NODE_ENV=test recons-web:latest npm run check
```

Local app was also started with `npm run dev` and returned HTTP 200 at `http://localhost:3000`.

## Next-Agent Cautions

- Do not add broad scraper ops tables to PostgreSQL in Phase 2 unless the plan is explicitly changed.
- Keep raw parse samples, scraper run logs, and connector health files in scraper-side storage first.
- Add listing read APIs only after normalized rows exist; when doing so, add input validation, pagination caps, DTO mapping, and rate-limit considerations.
- Treat CSP enforcement as a Phase 4/public-launch hardening item. The current policy is report-only because strict Next.js CSP enforcement needs nonce/hash work.
- Before any public connector launch, evaluate platform terms, takedown handling, data retention, cached media, and Indonesian privacy obligations.
