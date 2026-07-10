# RECON Phase 3 scraper handoff for GPT 5.6

Created: 2026-07-09 Asia/Jakarta.

This note is intentionally detailed. It exists so the next model can restart Phase 3 scraper hardening without rediscovering the staging state, the safety rules, and the bugs already found.

## Read these first

Before editing or running more staging tests, read these files in this order:

1. @AGENTS.md
2. @.plan/first-pass.html
3. @.plan/phase3-production-scraper-hardening-prd.md
4. @scraper/AGENTS.override.md
5. @scraper/reddit/AGENTS.override.md
6. @scraper/instagram/AGENTS.override.md
7. @scraper/facebook/AGENTS.override.md
8. @scraper/shared/AGENTS.override.md
9. @scraper/config/AGENTS.override.md
10. @scraper/storage/AGENTS.override.md if touching DB writes

The root rule is simple: Phase 3 is not done until Reddit, Instagram, and Facebook each pass the staging readiness criteria with source-specific cadence, persisted cooldown state, concise logs, idempotent DB writes, and a burn-in report.

## Non-negotiable safety rules

- Do not disable TLS verification.
- Do not commit browser cookies, CSRF tokens, captured headers, account credentials, browser profiles, or raw private session data.
- Do not add CAPTCHA solving, account rotation, seller messaging, hidden login-wall bypass, or proxy/VPN rotation.
- Direct egress remains the default. Proxy/VPN is opt-in only through existing explicit environment flags.
- Do not use `--ignore-cooldown` for burn-in. It is only for controlled diagnostics.
- Do not hammer blocked sources. Cooldown/degraded state is a valid safety outcome, but it is not the same as production readiness.
- Keep scraper run logs, connector state, cooldowns, and failure reasons in scraper-side files/volumes, not PostgreSQL.
- Keep v1 PostgreSQL scope to `listings` and `listing_images`.

## Current repo and branch state

Current branch:

```text
main
```

Latest pushed commits at the time of this handoff:

```text
4b1532d fix: cooldown instagram auth blocks
2214d0b fix: isolate scheduled facebook targets
4a63f6b fix: improve phase 3 scraper yield
90cd4c2 fix: avoid double counting burn-in logs
208f902 ci: install scraper dependencies for tests
```

Known local untracked files before this note was created:

```text
.plan/phase3-production-scraper-hardening-prd.md
skills-lock.json
```

Do not accidentally commit unrelated untracked files unless the user asks.

## Staging topology

Staging host:

```text
root@100.100.20.3
```

Staging compose directory:

```text
/docker/recon
```

Compose command base:

```bash
docker compose --env-file .env.staging -f compose.yml
```

Important services and volumes:

```text
postgres service: postgres
database: recon_staging
database user: recon
scraper image: novn01/recon-scraper:stagging
web image: novn01/recon.id:stagging
logs volume: recon-staging_scraper-staging-logs
state volume: recon-staging_scraper-staging-state
```

The tag is currently spelled `stagging` in the workflow/image naming. Do not rename it during scraper debugging unless the user explicitly approves a CI/CD naming cleanup.

The last pulled scraper image during this pass was:

```text
novn01/recon-scraper:stagging
image id: sha256:ed56ee33a3530e2d47e59cc2e9b84bd69e02a1f1b44afb7299a5147da470568b
created: 2026-07-08T17:49:29Z
source commit: 4b1532d
GitHub Actions run: https://github.com/nvn01/Recon.id/actions/runs/28963617682
conclusion: success
```

No production host was touched in this pass.

## Stop any leftover burn-in before continuing

The user asked to stop. Verify no burn-in container is running before doing anything else:

```bash
ssh root@100.100.20.3 'docker rm -f recon-scheduler-burnin >/dev/null 2>&1 || true; docker ps --filter name=recon-scheduler-burnin --format "{{.Names}} {{.Status}}"'
```

Expected output is empty.

## Database basics

Staging test DB clearing command:

```bash
ssh root@100.100.20.3 'cd /docker/recon && docker compose --env-file .env.staging -f compose.yml exec -T postgres psql -U recon -d recon_staging -c "truncate table listing_images, listings cascade; select count(1) as listings from listings; select count(1) as listing_images from listing_images;"'
```

Status/count query:

```bash
ssh root@100.100.20.3 'cd /docker/recon && docker compose --env-file .env.staging -f compose.yml exec -T postgres psql -U recon -d recon_staging -c "select platform, status, count(1) from listings group by platform, status order by platform, status; select count(1) as listing_images from listing_images;"'
```

Storage behavior to preserve:

- `listings.source_url` is the idempotency anchor.
- Repeated scrapes should update existing listings, not duplicate rows.
- `listing_images` are reconciled per listing.
- Runtime logs and connector health are not stored in DB.

## Scraper state and log cleanup

Use this to clear only scraper logs/state for staging tests. Do not delete browser profile/cookies/profile directories.

```bash
ssh root@100.100.20.3 'docker run --rm -v recon-staging_scraper-staging-logs:/logs -v recon-staging_scraper-staging-state:/state alpine:3.20 sh -lc "rm -f /logs/*.jsonl /state/scheduler.json /state/instagram_accounts.json /state/reddit_wts_computers.json /state/reddit_wts_computers.lock /state/facebook_marketplace.json /state/facebook_marketplace.lock /state/scraper_orchestrator.lock; ls -la /logs; ls -la /state"'
```

If you want to preserve Instagram cooldown safety state after proving a block, do not delete `/state/instagram_accounts.json`.

Note: Alpine BusyBox `find` does not support `-printf`. Use `ls`, `find -print`, `cat`, and `tail`.

## GitHub Actions and image flow

The normal flow is:

```text
local edit -> tests -> git commit -> git push -> GitHub Actions -> Docker Hub staging image -> staging pull -> staging test
```

Useful local checks before commit:

```powershell
python -m unittest discover scraper.tests
python -m ruff check scraper
python -m py_compile scraper\main.py
```

Poll Actions from PowerShell without `gh`:

```powershell
$sha = (git rev-parse HEAD).Trim()
$headers = @{ 'User-Agent' = 'codex-recon-staging-check'; 'Accept' = 'application/vnd.github+json' }
$runs = Invoke-RestMethod -Headers $headers -Uri 'https://api.github.com/repos/nvn01/Recon.id/actions/runs?branch=main&per_page=10'
$runs.workflow_runs | Where-Object { $_.head_sha -eq $sha } | Select-Object -First 1 id,status,conclusion,html_url
```

Pull the built staging scraper image:

```bash
ssh root@100.100.20.3 'cd /docker/recon && docker compose --env-file .env.staging -f compose.yml pull scraper && docker image inspect novn01/recon-scraper:stagging --format "image={{.Id}} created={{.Created}}"'
```

The pull can take around 3 minutes because the scraper image includes Playwright/browser dependencies.

## How to run scraper tests on staging

One-shot all-connector scheduler smoke:

```bash
ssh root@100.100.20.3 'cd /docker/recon && docker compose --env-file .env.staging -f compose.yml --profile scraper run --rm scraper python -m scraper.scheduler --once --write-db'
```

Manual orchestrator smoke:

```bash
ssh root@100.100.20.3 'cd /docker/recon && docker compose --env-file .env.staging -f compose.yml --profile scraper run --rm scraper python -m scraper.main --all --write-db --headless --facebook-browser chromium'
```

Detached burn-in:

```bash
ssh root@100.100.20.3 'cd /docker/recon && docker rm -f recon-scheduler-burnin >/dev/null 2>&1 || true && docker compose --env-file .env.staging -f compose.yml --profile scraper run -d --name recon-scheduler-burnin scraper python -m scraper.scheduler --write-db'
```

Poll burn-in:

```bash
ssh root@100.100.20.3 'docker ps --filter name=recon-scheduler-burnin --format "{{.Names}} {{.Status}}" && docker logs --tail 120 recon-scheduler-burnin 2>&1'
```

Stop burn-in:

```bash
ssh root@100.100.20.3 'docker stop recon-scheduler-burnin >/dev/null 2>&1 || true; docker rm recon-scheduler-burnin >/dev/null 2>&1 || true'
```

Generate burn-in report:

```bash
ssh root@100.100.20.3 'docker run --rm -v recon-staging_scraper-staging-logs:/logs novn01/recon-scraper:stagging python -m scraper.burn_in_report --logs-dir /logs --since-hours 2'
```

Important footnote: the remote Debian host did not have a host-level `python` command during this pass. Use Python inside the scraper container, not on the host.

## Current scheduler config

The production-shaped scheduler lives in @scraper/scheduler.py and defaults are in @scraper/config/sources.toml.

Current important defaults:

```text
scheduler.loop_sleep_seconds = 60
reddit cadence = 60s, limit = 15, jitter = 10s
instagram cadence = 3600s per account, stagger = 600s, limit = 2, fetch_mode = auto
facebook split_targets = true, target_groups = ["hot"], one target staggered every 60s, each target repeats around 600s, limit = 3
```

This means the scheduler can wake every minute, but not every source is fetched every minute. That is intentional.

Do not change Instagram to every minute while it is returning `401`/`429`. The safe current behavior is slow per-account checks plus persisted account cooldown.

## What was fixed in this pass

### Higher-yield scheduler defaults

Commit:

```text
4a63f6b fix: improve phase 3 scraper yield
```

High-level changes:

- Reddit now has a wider staging window: 60-second cadence, `limit = 15`, RSS image mode.
- Facebook now rotates reviewed hot targets instead of only fetching one `gpu-rtx` target.
- Instagram uses `fetch_mode = auto`, direct public request first, then temporary non-persistent browser fallback on blocking statuses.
- Burn-in report has yield-focused summaries.
- Tests were updated.

GitHub Actions for this commit passed:

```text
https://github.com/nvn01/Recon.id/actions/runs/28961638324
```

### Facebook target isolation bug

Commit:

```text
2214d0b fix: isolate scheduled facebook targets
```

Staging smoke found this real bug:

```text
facebook:gpu-rtx success exit=0 listings=25 requested=25 inserted=25
```

That was wrong. The split `facebook:gpu-rtx` job inherited the configured `target_groups = ["hot"]`, so a single target job fetched the whole hot group.

Fix:

- @scraper/main.py now treats explicit CLI Facebook targets/groups as an override instead of merging them with config groups.
- @scraper/tests/test_runtime_guardrails.py has regression coverage.

Corrected smoke after the fix:

```text
reddit success listings=15 inserted=15
instagram:chemicy.consignment success listings=2 inserted=2
facebook:gpu-rtx success listings=3 inserted=3
```

GitHub Actions for this commit passed:

```text
https://github.com/nvn01/Recon.id/actions/runs/28962778404
```

### Instagram 401 cooldown bug

Commit:

```text
4b1532d fix: cooldown instagram auth blocks
```

Staging burn-in found this real bug:

```text
instagram:chemicy.consignment degraded
state last_error: Instagram browser HTTP 401
cooldown_until: null
```

That was unsafe because a browser/auth block stayed retryable. The code only cooled down Instagram accounts on `403` and `429`.

Fix:

- @scraper/main.py now treats Instagram `401`, `403`, and `429` as cooldown-worthy block statuses.
- @scraper/tests/test_runtime_guardrails.py now covers account-scoped cooldown for both `429` and browser/auth `401`.

Focused staging check after the fix showed blocked Instagram accounts now get `cooldown_until` values for one hour.

GitHub Actions for this commit passed:

```text
https://github.com/nvn01/Recon.id/actions/runs/28963617682
```

## Latest staging evidence

### Good smoke after Facebook target isolation

Command:

```bash
docker compose --env-file .env.staging -f compose.yml --profile scraper run --rm scraper python -m scraper.scheduler --once --write-db
```

Output:

```text
2026-07-08T17:40:36Z reddit success listings=15 requested=15 inserted=15
2026-07-08T17:40:43Z instagram:chemicy.consignment success listings=2 requested=2 inserted=2
2026-07-08T17:40:52Z facebook:gpu-rtx success listings=3 requested=3 inserted=3
```

This proved the image could fetch all three once, but it was not enough for Phase 3 readiness.

### Focused Instagram safety check after 4b1532d

After clean state, two Instagram-only runs showed accounts entering cooldown for `401` and `429`.

State examples:

```text
chemicy.consignment: later hit Instagram browser HTTP 401 and got cooldown_until
sensegame.id: Instagram browser HTTP 401 with cooldown_until
cappee.gaming: Instagram browser HTTP 401 with cooldown_until
gamecentral.id: Instagram browser HTTP 401 with cooldown_until
consigngaming: Instagram browser HTTP 401 with cooldown_until
ggsconsign: Instagram browser HTTP 429 with cooldown_until
thelazytitip: Instagram browser HTTP 429 with cooldown_until
```

This is safe behavior, not readiness. Instagram is still blocked/unreliable from staging.

### Latest burn-in attempt after 4b1532d

The burn-in was intentionally stopped after the user asked to stop.

Early burn-in output:

```text
2026-07-08T17:56:42Z reddit degraded exit=1 listings=0
2026-07-08T17:56:49Z instagram:chemicy.consignment degraded exit=1 listings=0
2026-07-08T17:56:58Z facebook:gpu-rtx success listings=3 inserted=3
2026-07-08T17:57:50Z facebook:gpu-gtx success listings=3 inserted=3
2026-07-08T17:57:52Z reddit no_new_data exit=0 listings=0
2026-07-08T17:58:49Z facebook:gpu-rx success listings=3 inserted=3
2026-07-08T17:58:56Z reddit no_new_data exit=0 listings=0
```

Database count at that point:

```text
facebook available: 9
listing_images: 9
```

Reddit state:

```text
last_error: CERTIFICATE_VERIFY_FAILED self-signed certificate
cooldown_until: 2026-07-08T18:01:42Z
```

Instagram state:

```text
chemicy.consignment: Instagram browser HTTP 401, cooldown_until around 2026-07-08T18:56:49Z
other accounts: mostly 401/429 cooldowns from focused check
```

Facebook state:

```text
gpu-rtx, gpu-gtx, gpu-rx each inserted 3 rows successfully during this short window.
```

## Current unresolved issues

### 1. Reddit cooldown is logged correctly but summarized incorrectly

Evidence:

@scraper/reddit/reddit.py logs this correctly:

```text
reddit_wts_computers.jsonl:
status = cooldown_skip
cooldown_remaining_seconds = 230
```

But @scraper/main.py reports the connector as:

```text
status = no_new_data
exitCode = 0
validated = 0
```

Then @scraper/scheduler.py records:

```text
reddit no_new_data
stderr_tail: Reddit connector is cooling down for 230s.
```

This is a reporting bug. It hides the difference between "source reachable but no new listing" and "source is intentionally cooling down."

Likely area:

```text
@scraper/main.py run_reddit()
```

Current shape:

```python
code, listings = reddit.guarded_run_once(reddit_args)
valid, invalid = validate_listings(listings)
ok = code == 0 and not invalid
"status": connector_result_status(ok, len(valid))
```

Problem: `guarded_run_once()` only returns `(code, listings)`, so `run_reddit()` loses the connector-local reason for `code == 0` with zero listings.

Recommended fix direction:

- Do not infer cooldown from "zero listings" alone because that can be a real `no_new_data`.
- Make Reddit return explicit run metadata/status, or expose a small status result object from `guarded_run_once()`.
- Preserve backward compatibility if other code imports it.
- Add tests around `cooldown_skip` so `scraper.main` and `scheduler` summarize it correctly.

Do this before another long burn-in.

### 2. Reddit staging TLS/certificate failures are still intermittent

Known failures:

```text
_ssl.c:993 The handshake operation timed out
CERTIFICATE_VERIFY_FAILED self-signed certificate
```

The connector now cools down after TLS verification failure. That is safe, but it is not readiness.

Do not disable TLS verification.

Next model should diagnose the staging network path:

- Verify DNS from inside scraper container.
- Compare cert chain inside scraper container and host.
- Check whether intermittent interception is happening only from Docker network.
- Keep curl probes very limited; repeated probes already produced noisy `403`/`429`.
- If egress changes are needed, use explicit `SCRAPER_EGRESS_MODE` rules and user approval.

### 3. Instagram still is not production-ready

Observed from staging:

- Direct public `web_profile_info` can return `429`.
- Browser fallback can return `401` or `429`.
- A single smoke can succeed, then later runs block.
- Cooldown is now safer and account-scoped, but the source still does not reliably produce data.

Do not make Instagram every-minute. Current safe posture is slow per-account cadence and cooldowns.

Possible next directions:

- Improve diagnostics around which step failed: direct vs browser fallback, status, retry-after if present, account, and cooldown.
- Consider disabling scheduled Instagram writes while leaving diagnostic cooldown checks, if user accepts that Phase 3 remains blocked.
- If a stronger model can design a better public, non-persistent, non-cookie strategy, prove it with one account first and do not commit browser/session material.
- If no compliant reliable access path exists, state that clearly instead of faking readiness.

### 4. Facebook is closest, but still needs classifier and burn-in review

Good:

- Browser-backed Playwright fetch works on staging.
- Split targets now respect individual target IDs.
- `gpu-rtx`, `gpu-gtx`, and `gpu-rx` each wrote 3 rows during the short burn-in.
- Writes were idempotent in earlier scheduler loops.

Still needs:

- Spot-check latest Facebook rows so complete laptops are not categorized as GPU.
- Keep target coverage from reviewed @scraper/facebook/source_targets.json.
- Do not broaden to uncalibrated Marketplace searches just to increase row counts.

### 5. No clean one-hour burn-in report yet

There is no passing 1-hour all-connector burn-in report. The latest attempt was stopped after it exposed:

- Reddit TLS degradation and reporting bug.
- Instagram `401` cooldown.
- Facebook success.

Do not mark Phase 3 done until a burn-in report shows all connector readiness criteria pass or the user explicitly changes the definition.

## Suggested next sequence

1. Verify no staging burn-in is running.
2. Read the required docs listed at the top of this file.
3. Fix the Reddit `cooldown_skip` summary bug.
4. Add/adjust tests for Reddit cooldown status flowing through:
   - Reddit connector result
   - `scraper.main`
   - `scraper.scheduler`
   - `scraper.burn_in_report` if needed
5. Run local checks:

```powershell
python -m unittest discover scraper.tests
python -m ruff check scraper
python -m py_compile scraper\main.py scraper\scheduler.py scraper\reddit\reddit.py
```

6. Commit and push only the scoped fix.
7. Wait for GitHub Actions success for the exact SHA.
8. Pull `novn01/recon-scraper:stagging` on staging.
9. Clear staging listings/logs/state only as needed.
10. Run a one-shot scheduler smoke.
11. If one-shot passes, run a 60-minute burn-in.
12. Generate burn-in report and inspect DB counts.

## Success criteria for the next burn-in

Minimum acceptable burn-in evidence:

- Scheduler is running production-shaped source-specific jobs, not an ad-hoc tight `--all` loop.
- Reddit latest state is `success`, `no_new_data`, or explicit `cooldown_skip`; no hidden cooldown as `no_new_data`.
- Instagram does not hammer blocked accounts. If it remains `401`/`429`, it must be explicit `cooldown_skip`/`degraded` with account cooldown state. That still blocks Phase 3 completion unless the user accepts deferring Instagram.
- Facebook target jobs succeed and do not insert broad target-group rows from a single target job.
- Database writes are idempotent: repeated runs update/skip existing rows instead of duplicate spam.
- Logs are concise on stdout and detailed in JSONL files.
- Burn-in report includes connector status counts, storage counts, yield, and latest failures.

## Files likely to matter next

Core scheduler/orchestrator:

```text
@scraper/main.py
@scraper/scheduler.py
@scraper/burn_in_report.py
@scraper/config/sources.toml
```

Runtime and validation:

```text
@scraper/shared/runtime.py
@scraper/shared/listing_contract.py
@scraper/storage/postgres.py
@scraper/storage/run_log.py
```

Connectors:

```text
@scraper/reddit/reddit.py
@scraper/instagram/instagram.py
@scraper/facebook/facebook_marketplace.py
@scraper/facebook/source_targets.json
```

Tests:

```text
@scraper/tests/test_runtime_guardrails.py
@scraper/tests/test_scheduler.py
@scraper/tests/test_reddit_fetch.py
@scraper/tests/test_instagram_fetch.py
@scraper/tests/test_facebook_classification.py
@scraper/tests/test_burn_in_report.py
```

CI/CD:

```text
@.github/workflows/staging.yml
@Dockerfile
@scraper/Dockerfile
@docker-compose.production.yml
```

## Useful log inspection commands

Logs:

```bash
ssh root@100.100.20.3 'docker run --rm -v recon-staging_scraper-staging-logs:/logs alpine:3.20 sh -lc "ls -la /logs; tail -n 40 /logs/scheduler_runs.jsonl 2>/dev/null || true; tail -n 40 /logs/scraper_runs.jsonl 2>/dev/null || true"'
```

State:

```bash
ssh root@100.100.20.3 'docker run --rm -v recon-staging_scraper-staging-state:/state alpine:3.20 sh -lc "ls -la /state; for f in /state/*.json; do echo FILE=$f; cat $f; echo; done"'
```

Connector-specific logs:

```bash
ssh root@100.100.20.3 'docker run --rm -v recon-staging_scraper-staging-logs:/logs alpine:3.20 sh -lc "cat /logs/reddit_wts_computers.jsonl 2>/dev/null || true; cat /logs/instagram_accounts.jsonl 2>/dev/null || true; cat /logs/facebook_marketplace.jsonl 2>/dev/null || true"'
```

## Final warning

The scraper is now much safer than before, but it is not genuinely Phase 3 complete. The honest current state is:

```text
Reddit: functional path proven, but staging TLS is unstable and cooldown status reporting needs a fix.
Instagram: account cooldown safety improved, but reliable staging data collection is still blocked by 401/429.
Facebook: browser-backed fetch and split target rotation work, but classifier/output quality still needs burn-in review.
Database writes: idempotent path works for staging tests.
Scheduler: production-shaped and useful, but do not trust reports until the Reddit cooldown status bug is fixed.
```

Treat the next session as a hardening/debugging session, not a completion session.
