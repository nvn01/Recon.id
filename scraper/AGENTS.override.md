# Scraper Service Instructions

This directory owns RECON's Python scraper runtime. Treat the current deployed
connectors and normalized database writes as the source of truth; do not restore
old probe scripts or historical access experiments.

## Current Runtime Shape

- `scraper.scheduler` is the image entrypoint. Its default one-shot command
  queues candidates; the production-shaped Compose service runs it continuously.
- Scheduled collectors perform raw fetch and contract validation only. They
  never call NVIDIA or PostgreSQL.
- `scraper.candidate_pool` keeps stable-evidence versions in ignored
  `.state/candidate_pool.sqlite3`. Fetch timestamps and signed image query
  parameters do not create duplicate AI work.
- Queue envelopes may carry the existing bounded `_sourceFacts` dictionary for
  AI review. It must affect the evidence fingerprint, remain out of scheduler
  logs, and be stripped by contract validation before PostgreSQL writes.
- `scraper.ai_manager` leases mixed-platform batches, runs the mandatory NVIDIA
  semantic parser, and only then writes validated listings to PostgreSQL. Failed
  AI or storage batches return to the pool with a bounded retry delay.
- `scraper.main` orchestrates individual connectors and is read-only unless
  `--write-db` is supplied. That direct flag still enables AI parsing for
  controlled one-shot diagnostics; it is not the scheduled path.
- Source URLs, account names, cadence, browser selection, and safe defaults live
  in `config/sources.toml`.
- Facebook's reviewed category targets live in
  `facebook/source_targets.json`.
- Connector output must pass `shared/listing_contract.py` before storage.
- PostgreSQL writes in `storage/postgres.py` are idempotent by `sourceUrl` and
  reconcile `listing_images` transactionally.
- Runtime logs and cooldown state stay in ignored `.logs/` and `.state/`
  directories. Do not add scraper operations tables without an explicit schema
  decision.

## Supported Discovery Paths

### Reddit

- Use the public RSS feed for scheduled discovery.
- The four configured flairs start 60 seconds apart and each repeat every 240
  seconds, producing one scheduled RSS request per minute.
- Keep `image_mode = "rss"`; do not add per-post JSON or gallery requests to the
  scheduled path.
- Preserve TLS verification. Transient certificate or transport failures get
  bounded retries/cooldowns, never `verify=false`.
- Discovery only collects source identity, raw seller text, media, and timestamps.
  Scheduled semantic parsing is AI-only and required before database writes.

### Instagram

- Use a fresh logged-out headed Chrome context under Xvfb.
- Navigate to each configured public profile and extract the embedded timeline
  plus supported same-origin timeline responses.
- Scheduled discovery must not use `web_profile_info`, saved cookies, captured
  headers, a persistent browser profile, or login credentials.
- Canonicalize and deduplicate by shortcode, then sort by source timestamp or
  numeric post ID so pinned posts do not control ordering.
- `browser_wait_ms` is a maximum event-pump budget. Poll and return when timeline
  data arrives rather than adding a fixed sleep.
- Keep `--instagram-browser-mode headless` only as a diagnostic A/B control. The
  proven Debian production path is headed Chrome under Xvfb.
- Scheduled Instagram accounts start 45 seconds apart and repeat every 315
  seconds, completing the first seven-account sweep in 4m30s.
- Any access, login-wall, 401, 403, or 429 result opens a platform-wide
  Instagram cooldown before another scheduled account is attempted.
- Scheduled Instagram jobs send raw post candidates to the durable pool.
  AI decides whether each post is a listing and owns title, category, brand,
  price, condition, location, and status. If parsing fails, do not write the
  incomplete candidates.

### Facebook Marketplace

- Use a fresh logged-out headless Chrome context.
- Discover from the embedded Relay payload; DOM cards are fallback only.
- Use the reviewed localized category URLs for:
  - cell phone accessories
  - video games and consoles
  - computers
- Targets use Jakarta, a 500 km radius, and newest-first ordering. Do not replace
  them with broad `query=` searches.
- Apply the gaming, PC, and peripherals relevance filter before storage.
- Treat a parsed Facebook candidate window with zero relevant matches as
  `no_new_data`; only missing Marketplace candidates or a real access/login
  failure may set the connector-wide cooldown.
- Scheduled discovery does not require login, persistent profile state,
  scrolling, detail-page fetches, or seller actions.
- Scheduled Facebook jobs use batched NVIDIA semantic parsing. Collector fields
  such as card price, location, and sold flags are source evidence only; local
  code must not translate them into database semantic values.
- NVIDIA capacity errors immediately open a shared five-minute parser cooldown.
  NVIDIA Cloud Functions `DEGRADED function cannot be invoked` and function-ID
  `not found` invocation responses open the same cooldown because the provider
  function is unavailable even when the HTTP status is `400` or `404`.
  Two consecutive invalid model outputs open the same cooldown. Only an explicit
  guided-JSON request rejection may retry once without `nvext`; other failures
  must not create an immediate duplicate model request.
- The three reviewed hot targets start 60 seconds apart and each repeat every
  180 seconds.
- Persistent profile and login CLI modes are diagnostics only. Never commit
  `.facebook-profile*`.

## Normalized Listing Contract

All connectors emit the shared database-facing fields only:

```text
platform, sourceUrl, externalId, title, description, category, brand,
price, locationTexts, conditionText, sellerName, status, postedAt,
firstFetchedAt, lastFetchedAt, images
```

Keep the seller's raw text in `description`. Images use `sourceUrl`, `position`,
and `altText`. Do not add confidence scores, OCR notes, raw payloads, cookies,
headers, or model-specific evidence to normal listing JSON.

## Safety And Access Rules

- Direct egress is the default and is proven on staging without a Tailscale exit
  node.
- Proxy/VPN use remains explicit and opt-in through the existing runtime guards.
- Do not add proxy rotation, automatic VPN switching, account rotation, CAPTCHA
  solving, login-wall bypasses, or automated seller/account actions.
- On a block or rate limit, reduce cadence, honor cooldowns, record degraded
  state, and fix the source-specific collector.
- Never commit secrets, browser sessions, cookies, CSRF tokens, captured request
  headers, unsanitized payloads, `.logs/`, or `.state/`.

## Local Verification

Run from the repository root:

```powershell
python -m unittest discover scraper.tests
python -m ruff check scraper
python -m scraper.main --reddit --limit 1 --no-state
python -m scraper.main --instagram --instagram-account chemicy.consignment --limit 1 --no-state
python -m scraper.main --facebook --limit 1 --headless --facebook-browser chrome --no-state
```

Phase 5 parser regressions use sanitized fixtures in
`scraper/tests/fixtures/`. The scheduler also runs the read-only operational
report job at most once every 24 hours using persisted scheduler state. Reports
are written to the mounted scraper log volume under `.logs/reports/`:

```powershell
python -m scraper.operational_report --output-dir .logs/reports
```

The data-quality report treats missing nullable enrichment and `UNKNOWN`
status as low-confidence signals because confidence scores intentionally remain
outside PostgreSQL. The separate manual-review report contains public listing
identity and review reasons, but never copies full descriptions or credentials.

Do not use repeated live probes as a test loop. Unit tests and captured parser
fixtures should cover parsing; use one controlled live smoke only when network
behavior must be verified.

## Staging Workflow

Staging is the authoritative environment for browser/network behavior:

```bash
ssh root@100.100.20.3
cd /docker/recon
docker compose --env-file .env.staging -f compose.yml pull scraper
docker compose --env-file .env.staging -f compose.yml --profile scraper run --rm scraper python -m scraper.main --all --write-db
```

Current deployment facts:

- Debian staging host: `100.100.20.3`
- Project directory: `/docker/recon`
- Scraper image: `novn01/recon-scraper:stagging`
- Runtime env: `/docker/recon/.env.staging`
- Default image command: `scraper.scheduler --once --queue-candidates`
- A continuous deployment must run collector and AI-manager services from the
  same scraper image with the same `.state` and `.logs` volumes. The collector
  command is `scraper.scheduler --queue-candidates`; the manager command is
  `scraper.ai_manager --write-db`.
- Chrome/Xvfb startup must remain behind `tini`; do not duplicate Compose `init`
  or browser flags in the service command.

After one controlled run, inspect only a bounded snapshot:

```bash
docker compose --env-file .env.staging -f compose.yml logs --tail=100 scraper
docker compose --env-file .env.staging -f compose.yml exec -T postgres psql -U recon -d recon_staging -c "select platform, status, count(*) from listings group by platform, status order by platform, status;"
```

Do not attach an open-ended log monitor. The latest verified direct-egress run
successfully collected all three platforms; diagnose future failures from the
new run's evidence rather than restoring superseded experiments.

## Change Checklist

Before committing scraper changes:

1. Trace imports, CLI entrypoints, Compose references, workflow references, and
   tests before removing a file.
2. Keep connector discovery cheap; AI semantic parsing is required and batched.
3. Preserve the shared normalized contract and idempotent write behavior.
4. Run the full scraper unit suite and Ruff.
5. For browser/network changes, build through GitHub Actions and validate the
   resulting image once on Debian staging.
6. Update this file when the supported runtime workflow changes; do not append a
   historical diary.
