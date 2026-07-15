# Queued Scraper Pipeline TDD Evidence

## User journeys

- As an operator, I want Reddit, Instagram, and Facebook collection to progress
  independently from NVIDIA and PostgreSQL availability.
- As an operator, I want one AI manager to mix platforms into efficient batches
  without repeatedly parsing unchanged source evidence.
- As an operator, I want failed AI or storage batches retained for bounded retry
  instead of silently losing raw candidates.
- As an operator, I want a single Instagram access block to stop the faster
  account rotation until the platform cooldown expires.

## RED and GREEN evidence

| Guarantee | Test target | RED evidence | GREEN evidence |
|---|---|---|---|
| Stable evidence deduplicates fetch timestamps and signed image URLs | `scraper.tests.test_candidate_pipeline` | `scraper.candidate_pool` did not exist | New, unchanged, and changed versions are accounted for and persisted |
| Private Facebook facts reach AI but never PostgreSQL | `scraper.tests.test_candidate_pipeline`, `scraper.tests.test_scheduler` | The first queue draft lost `_sourceFacts` after listing validation | Source facts affect fingerprints, survive the queue envelope, and are stripped before storage |
| Mixed-platform batches wait for size or deadline | `scraper.tests.test_candidate_pipeline` | `scraper.ai_manager` did not exist | Reddit and Instagram lease together; lone items flush after the deadline |
| Failed AI batches never write and return to pending | `scraper.tests.test_candidate_pipeline` | No centralized retry boundary existed | Whole-batch retry preserves candidates with a delayed availability time |
| Scheduled collectors omit AI and database writes | `scraper.tests.test_scheduler` | Jobs carried `--ai-parse` and the image default carried `--write-db` | Raw candidates enter SQLite and Compose runs a separate manager service |
| Faster production cadence stays staggered | `scraper.tests.test_scheduler` | Reddit used 300/75 seconds, Instagram 600/85, Facebook targets 600/60 | Reddit uses 240/60, Instagram 315/45, and Facebook targets 180/60 |
| Instagram blocks stop every account until cooldown expiry | `scraper.tests.test_runtime_guardrails` | Cooldown state was account-scoped and root cooldown was cleared at every run | The first access/login block opens a platform-wide cooldown |

## Checkpoints

- RED checkpoint: `b4e154b test(scraper): define queued pipeline guarantees`.
- Initial RED run: 36 tests, five failures and one import error.
- Focused GREEN run: 45 tests passed.

## Validation

- `python -m unittest discover scraper.tests` — 102 tests passed.
- `python -m ruff check scraper` — passed.
- `python -m compileall -q scraper` — passed.
- Focused coverage for `candidate_pool` and `ai_manager` — 81% total
  (`candidate_pool` 93%, `ai_manager` 64%).
- `npx prisma validate` — schema valid.
- `npm run check` — ESLint and TypeScript passed.
- `npm run build` — production build passed.
- `docker compose --profile scraper-scheduler config --quiet` — passed.
