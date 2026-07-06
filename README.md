# Recon

Recon is an early-stage scraper-first listing intelligence project for monitoring Indonesian second-hand computer, tech, gaming gear, and peripheral listings.

## Current Phase

Phase 1 is focused on the database foundation:

- Prisma schema for `listings` and `listing_images`.
- No user accounts, saved preferences, checkout, chat, alerts, or public listing UI yet.
- Scraper run logs, connector health, cadence, and source configuration stay in the scraper service for now.

## Stack

- Next.js
- Prisma
- PostgreSQL
- tRPC
- Tailwind CSS
- Python scraper service

## Development

```powershell
npm install
npm run db:generate
npm run db:smoke
npm run check
npm run build
```

Use Docker Compose for local PostgreSQL. Keep real secrets in `.env`, which is ignored by git.
