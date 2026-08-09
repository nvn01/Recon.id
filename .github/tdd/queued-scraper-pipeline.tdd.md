# Queued Scraper Pipeline TDD Evidence

## User journeys

- As an operator, I want Reddit, Instagram, and Facebook collection to progress
  independently from NVIDIA and PostgreSQL availability.
- As an operator, I want one AI manager to mix platforms into efficient batches
  without repeatedly parsing unchanged source evidence.
- As an operator, I want one train to collect every platform for a full minute,
  make one NVIDIA request, and bulk-write the returned listing array.
- As an operator, I want new posts to board before retries so old provider
  failures cannot hide fresh listings for tens of minutes.
- As an operator, I want failed AI or storage batches retained for bounded retry
  instead of silently losing raw candidates.
- As an operator, I want a single Instagram access block to stop the faster
  account rotation until the platform cooldown expires.

## RED and GREEN evidence

| Guarantee | Test target | RED evidence | GREEN evidence |
|---|---|---|---|
| Stable AI evidence ignores fetch timestamps, unstable Instagram `postedAt`, and CDN path variants | `scraper.tests.test_candidate_pipeline` | The AZ037 incident produced multiple fingerprints for one unchanged post | Volatile refreshes update a waiting payload but enqueue no additional AI work |
| Private Facebook facts reach AI but never PostgreSQL | `scraper.tests.test_candidate_pipeline`, `scraper.tests.test_scheduler` | The first queue draft lost `_sourceFacts` after listing validation | Source facts affect fingerprints, survive the queue envelope, and are stripped before storage |
| A mixed-platform train waits 60 seconds and boards the whole ready window | `scraper.tests.test_candidate_pipeline` | The manager leased fixed two-item batches immediately | Reddit, Instagram, and Facebook are passed to one NVIDIA invocation with `batch_size` equal to the boarded train |
| Fresh work boards before retries and duplicate pending versions are superseded | `scraper.tests.test_candidate_pipeline` | AZ037 had 128 candidates ahead of it while old rows reached 10-15 attempts | A fresh candidate wins a capacity-limited departure and only the newest pending version of a post remains boardable |
| Failed AI batches never write and return to pending | `scraper.tests.test_candidate_pipeline` | No centralized retry boundary existed | Whole-batch retry preserves candidates with a delayed availability time |
| Scheduled collectors omit AI and database writes | `scraper.tests.test_scheduler` | Jobs carried `--ai-parse` and the image default carried `--write-db` | Raw candidates enter SQLite and Compose runs a separate manager service |
| Faster production cadence stays staggered | `scraper.tests.test_scheduler` | Reddit used 300/75 seconds, Instagram 600/85, Facebook targets 600/60 | Reddit uses 240/60, Instagram 315/45, and Facebook targets 180/60 |
| Instagram blocks stop every account until cooldown expiry | `scraper.tests.test_runtime_guardrails` | Cooldown state was account-scoped and root cooldown was cleared at every run | The first access/login block opens a platform-wide cooldown |

## Checkpoints

- RED checkpoint: `b4e154b test(scraper): define queued pipeline guarantees`.
- Initial RED run: 36 tests, five failures and one import error.
- Focused GREEN run: 45 tests passed.
- One-minute train RED checkpoints: `3ff3268` and `c154273`.
- One-minute train GREEN checkpoint: `d3fde4f`.
- Current RED evidence: missing `wait_for_departure` import, followed by the
  pending-payload test retaining the old Instagram timestamp/media URL.

## Validation

- `python -m unittest discover scraper.tests` — 117 tests passed.
- `python -m ruff check scraper` — passed.
- `python -m compileall -q scraper` — passed.
- In-memory queue-drain simulation — 45 mixed-platform candidates departed as
  trains of `20`, `20`, and `5`; final queue was zero pending and zero leased.
- Focused coverage for `candidate_pool` and `ai_manager` — 81% total
  (`candidate_pool` 93%, `ai_manager` 64%).
- `npx prisma validate` — schema valid.
- `npm run check` — ESLint and TypeScript passed.
- `npm run build` — production build passed.
- `docker compose --profile scraper-scheduler config --quiet` — passed.
