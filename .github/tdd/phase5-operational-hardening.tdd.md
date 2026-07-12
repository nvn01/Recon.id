# Phase 5 Operational Hardening TDD Evidence

## Source plan

Acceptance criteria came from `.plan/first-pass.html`, Phase 5.

## User journeys

- As an operator, I want captured parser fixtures for each connector so parser changes cannot silently corrupt normalized listings.
- As an operator, I want one daily quality snapshot so missing and uncertain fields are visible without inspecting PostgreSQL manually.
- As a reviewer, I want a focused queue for condition, location, and sold-state ambiguity without copying full seller descriptions into reports.
- As an operator, I want reporting to reuse scheduler state, locks, cooldowns, and secret-safe subprocess boundaries.

## RED and GREEN evidence

| Guarantee | Test target | RED evidence | GREEN evidence |
|---|---|---|---|
| Every connector fixture preserves DB-shaped parsing | `scraper.tests.test_parser_fixtures` | Instagram selected `SOLD OUT` as title; Reddit classified an RTX laptop as GPU | All three connector fixtures pass |
| Quality and manual-review reports remain separate and description-safe | `scraper.tests.test_operational_report` | `scraper.operational_report` did not exist | Report analysis and dated artifact tests pass |
| Relative reports persist in the mounted scraper log directory | `test_relative_report_directory_resolves_inside_persisted_scraper_logs` | `resolve_output_dir` import failed | Relative path resolves below `scraper/.logs` |
| Daily report is scheduler-managed and read-only | `scraper.tests.test_scheduler` | No operational scheduler job existed | 86,400-second job uses the report module, omits `--write-db`, and keeps DB URL in environment only |

## Validation

- `python -m unittest discover scraper.tests` — latest full suite: 83 tests passed.
- `python -m unittest scraper.tests.test_operational_report scraper.tests.test_scheduler` — 16 tests passed after the final RED/GREEN cycle.
- `python -m ruff check scraper` — passed.
- `python -m compileall -q scraper` — passed.
- `npm run check` — ESLint and TypeScript passed.
- `npm run test:coverage` — 27 backend tests passed at 100/92.59/100/100 coverage.
- `npx prisma validate` — schema valid.
- `npm run build` — production build generated a fresh `.next/BUILD_ID`.
- Read-only staging execution analyzed 222 rows and produced both reports; 141 rows entered manual review and brand, category, condition, and `postedAt` were below the 80% coverage target.

## Known boundary

The tracked code schedules the report whenever the persisted scraper scheduler runs. The staging host currently has no tracked host-level timer, and deployment/push remains a separate explicitly approved action.
