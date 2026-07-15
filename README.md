# Recon

Recon is an early-stage scraper-first listing intelligence project for monitoring Indonesian second-hand computer, tech, gaming gear, and peripheral listings.

## Current Phase

Phase 3 is focused on production scraper hardening:

- Prisma schema for `listings` and `listing_images`.
- Scraper can upsert validated normalized listings with `python -m scraper.main --reddit --write-db`.
- `scraper.scheduler` collects source-specific raw candidates on persisted cadences.
- `scraper.ai_manager` mixes queued platforms into small NVIDIA batches before database writes.
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

The production-shaped collector and AI manager share a durable scraper-state
volume and start together under a separate profile:

```powershell
docker compose --profile scraper-scheduler up -d scraper-scheduler scraper-ai-manager
docker compose --profile scraper-scheduler logs --tail=100 scraper-scheduler scraper-ai-manager
python -m scraper.burn_in_report --since-hours 6
```

The collector never calls AI or PostgreSQL. It deduplicates stable raw evidence
in `.state/candidate_pool.sqlite3`; the manager is the only scheduled path that
calls NVIDIA and then writes validated listings. Direct `scraper.main --write-db`
remains available for controlled one-shot diagnostics.
