# Phase 3 Production Scraper Hardening PRD

## Problem Statement

Phase 3 is intended to prove that RECON's source connectors can run like a production scraper, not just pass one-off local checks. The current staging evidence is mixed:

- Reddit can fetch, normalize, validate, and write listings through the shared contract, but staging has shown intermittent TLS/certificate failures.
- Facebook can fetch through the browser-backed path and write listings, but classification can mislabel gaming laptops as GPU listings when RTX terms appear in the title.
- Instagram direct public `web_profile_info` access from staging returns HTTP 429 for every configured account, so Instagram is not production-ready.
- The current ad-hoc loop can run the connectors, but production needs source-specific cadence, cooldown behavior, concise logs, and a repeatable staging verification protocol.

From the user's perspective, Phase 3 should not be marked done until the scraper can run on staging for a meaningful window without duplicate spam, silent failures, repeated source lockout, or broken database writes.

## Solution

Build a production-grade Phase 3 connector hardening pass that proves each connector through the same end-to-end path:

1. Fetch from the safest approved access path for the source.
2. Normalize into the shared listing contract.
3. Validate before storage.
4. Upsert idempotently into PostgreSQL.
5. Persist concise scraper-side logs and state.
6. Apply source-specific cadence, cooldown, and egress rules.
7. Pass a staging burn-in run with clear success thresholds.

"Can fetch every time" should mean every scheduled cycle ends in one of these explicit states:

- `success`: fetched and wrote or refreshed listings.
- `no_new_data`: source reachable, no new listing needed.
- `cooldown_skip`: connector intentionally skipped because the previous block/rate-limit signal is still cooling down.
- `degraded`: connector could not fetch, but the reason is logged, storage is not corrupted, and the scheduler does not hammer the source.

It should not mean disabling TLS verification, ignoring platform blocks, or retrying aggressively until a source locks the VM out.

## User Stories

1. As the RECON owner, I want all Phase 3 connectors tested on staging, so that I know the Docker image, VM network path, mounted state, and database writes work together.
2. As the RECON owner, I want Reddit to run every 5 minutes safely, so that new WTS listings are captured quickly.
3. As the RECON owner, I want Reddit TLS failures to be diagnosed without weakening TLS, so that staging network problems do not become data-integrity problems.
4. As the RECON owner, I want Reddit to fetch more than one listing per cycle, so that multiple posts between intervals are not missed.
5. As the RECON owner, I want Instagram to use a reliable approved access path, so that all configured accounts can produce listing candidates instead of HTTP 429 only.
6. As the RECON owner, I want Instagram account checks paced per account, so that one blocked account does not force repeated aggressive retries for every account.
7. As the RECON owner, I want Instagram non-product posts skipped, so that reels, memes, or engagement posts do not pollute the listing table.
8. As the RECON owner, I want Instagram sold markers handled deterministically, so that obvious sold status does not require AI guessing.
9. As the RECON owner, I want Facebook to keep using the browser-backed path when direct HTTP is unreliable, so that Marketplace remains fetchable on staging.
10. As the RECON owner, I want Facebook product classification fixed, so that gaming laptops are not stored as GPU listings just because the title contains RTX.
11. As the RECON owner, I want Facebook target cadence separated from Reddit and Instagram, so that one source's limits do not dictate the whole scraper.
12. As the RECON owner, I want one production-like scheduler model, so that staging behavior matches the eventual production worker shape.
13. As the RECON owner, I want concise container logs, so that long listing JSON does not bury errors during burn-in.
14. As the RECON owner, I want detailed JSONL evidence in scraper-side logs, so that future debugging still has enough data.
15. As the RECON owner, I want run summaries visible from staging commands, so that I can quickly see success/failure counts after lunch-length tests.
16. As the RECON owner, I want cooldown state persisted in volumes, so that container restarts do not forget rate-limit history.
17. As the RECON owner, I want duplicate-run locking preserved, so that overlapping scheduler cycles do not write duplicate or conflicting data.
18. As the RECON owner, I want database writes to remain idempotent, so that repeated runs refresh listings instead of creating duplicate rows.
19. As the RECON owner, I want failure reasons stored outside PostgreSQL, so that operational noise does not bloat the minimal v1 schema.
20. As the RECON owner, I want a clear Phase 3 done checklist, so that the plan can honestly move to Phase 4 backend API work.

## Implementation Decisions

- Keep the shared scraper contract as the single integration boundary for Phase 3.
- Keep scraper run logs, connector state, cooldowns, and failure reasons in scraper-side files/volumes, not PostgreSQL.
- Replace the ad-hoc production test loop with a production-shaped scheduler strategy. The scheduler may be host cron/systemd or a dedicated Compose scheduler service, but it must not rely on crash/restart loops.
- Split cadence by connector instead of running all sources every 5 minutes:
  - Reddit: 5 minutes after burn-in proves it is stable.
  - Facebook: 10-15 minutes while browser-backed fetching is still beta.
  - Instagram: slow diagnostic cadence until the 429 issue is fixed, then tighten gradually.
- Increase Reddit production fetch limit from 1 to at least 3.
- Do not disable TLS verification for Reddit. Certificate failures must trigger diagnostics, degraded state, or explicit egress changes.
- Add summary-only container output for scheduled runs. Full listing payloads remain available through JSON output when explicitly requested.
- Instagram direct public requests are not currently production-ready from staging. The next implementation must prove one of:
  - browser-backed public fetch path with no committed cookies or captured session headers,
  - explicit proxy/VPN egress using existing opt-in egress flags,
  - or a slower per-account direct strategy that no longer returns all-account 429.
- Instagram cooldown should become account-aware. One account's block should not force the connector to repeatedly probe all accounts every 5 minutes.
- Facebook category rules should prioritize laptop/desktop terms over GPU terms when a listing is clearly a complete machine.
- Facebook remains beta until the browser session path, target matrix, and classifier can pass staging burn-in without manual intervention.
- Production readiness requires a staging burn-in report, not a single successful run.

## Testing Decisions

The highest-value test seam is the staging orchestrator path: scheduler -> connector -> shared validation -> database upsert -> scraper-side logs/state. This is the seam that actually proves production behavior.

Lower-level tests still matter, but they support the staging seam:

- Unit tests for retry/cooldown decisions and parser classification.
- Fixture-backed connector parser tests for Reddit, Instagram, and Facebook.
- Storage smoke tests for idempotent upsert and image reconciliation.
- Staging burn-in checks that count connector success, failures, cooldown skips, inserted rows, updated rows, and duplicate behavior.

Good tests should assert externally visible behavior:

- a source failure is logged and does not corrupt storage,
- a repeated listing updates instead of duplicating,
- a sold marker changes status deterministically,
- a gaming laptop is categorized as a laptop, not a GPU,
- a rate-limited Instagram account enters cooldown instead of being hammered.

## Out of Scope

- Public listing UI.
- Alerts, watchlists, and saved searches.
- User accounts or personalization.
- New PostgreSQL tables for scrape runs or connector health.
- CAPTCHA solving, account rotation, hidden bypasses, or disabling TLS verification.
- Full-size image archival.
- Production promotion before staging burn-in passes.

## Further Notes

Current staging result from the production-like all-connector loop:

- Reddit succeeded and stored 3 listings.
- Facebook succeeded and stored 1 listing.
- Instagram failed with HTTP 429 for all 7 configured accounts.

The immediate blocker for Phase 3 completion is Instagram access reliability. The immediate quality bug is Facebook classification. The immediate operations gap is replacing ad-hoc loops with a real scheduler and concise run summaries.

## Proposed Issue Breakdown

1. **Add production-shaped connector scheduler**
   - Blocked by: none
   - User stories covered: 1, 12, 15, 16, 17, 20
   - Build a staging-safe scheduler that can run source-specific commands at different intervals and preserve logs/state across restarts.

2. **Add summary logging mode for scheduled scraper runs**
   - Blocked by: none
   - User stories covered: 13, 14, 15
   - Scheduled runs should print compact summaries to container stdout while keeping detailed JSONL evidence in scraper-side logs.

3. **Harden Reddit staging burn-in**
   - Blocked by: 1, 2
   - User stories covered: 2, 3, 4, 18, 19
   - Run Reddit at 5-minute cadence with limit 3+, verify no duplicate spam, and capture TLS failures as explicit degraded events without disabling verification.

4. **Fix Facebook complete-machine classification**
   - Blocked by: none
   - User stories covered: 9, 10, 11
   - Prioritize laptop/desktop/all-in-one language over GPU terms when the listing is a complete machine.

5. **Harden Facebook browser-backed staging cadence**
   - Blocked by: 1, 2, 4
   - User stories covered: 9, 11, 18, 20
   - Prove Facebook can run at a slower staging cadence through the persistent browser path and write idempotent rows.

6. **Implement Instagram access recovery path**
   - Blocked by: 1, 2
   - User stories covered: 5, 6, 7, 8, 16, 19
   - Replace the current all-account direct 429 failure with a proven staging access strategy: browser-backed public fetch, explicit proxy/VPN egress, or slower per-account direct probing.

7. **Add account-aware Instagram cooldown and diagnostics**
   - Blocked by: 6
   - User stories covered: 5, 6, 16, 19
   - Store per-account cooldown/failure state and avoid hammering every account after one account or egress path is blocked.

8. **Run Phase 3 all-connector burn-in and update plan**
   - Blocked by: 3, 5, 7
   - User stories covered: 1, 15, 20
   - Run a production-like staging burn-in, record counts and failures, and only then mark Phase 3 as done in the project plan.
