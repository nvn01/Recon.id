# Recon

Recon is an early-stage scraper-first listing intelligence project for monitoring Indonesian second-hand computer, tech, gaming gear, and peripheral listings.

## Current Phase

Phase 2 is focused on scraper ingestion:

- Prisma schema for `listings` and `listing_images`.
- Scraper can upsert validated normalized listings with `python -m scraper.main --reddit --write-db`.
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
python -m unittest discover scraper.tests
npm run check
npm run build
```

Use Docker Compose for local PostgreSQL. Keep real secrets in `.env`, which is ignored by git.

The optional scraper container is profile-gated:

```powershell
docker compose --profile scraper run --rm scraper
```
