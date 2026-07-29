# Scraper Service Instructions

This directory owns RECON's Python scraper runtime. Treat the current deployed
connectors and normalized database writes as the source of truth; do not restore
old probe scripts or historical access experiments.

## Current Runtime Shape

- The supported production runtime is three workers built from the exact same
  immutable scraper image:
  - collector: `python -m scraper.scheduler --queue-candidates`
  - AI manager: `python -m scraper.ai_manager --write-db`
  - media worker: `python -m scraper.media.worker`
- The currently pinned production image still caches Instagram only. The tracked
  next release adds Reddit to that worker; do not call Reddit R2 live before an
  explicitly approved promotion and reviewed backfill.
- The collector and AI manager must share the same persisted `.state` and
  `.logs` volumes. The media worker uses PostgreSQL as its durable queue and
  writes its log to the persisted scraper log volume. Never run the former
  combined `scraper.scheduler --write-db` scheduler beside these workers.
- `scraper.scheduler` remains the image entrypoint. Its default one-shot command
  queues candidates for diagnostics; it is not the continuous deployment shape.
- Scheduled collectors perform raw fetch and contract validation only. They
  never call NVIDIA or PostgreSQL.
- `scraper.candidate_pool` keeps stable semantic-evidence versions in ignored
  `.state/candidate_pool.sqlite3`. Fetch timestamps, Instagram `postedAt`, and
  signed/CDN image-path variations do not create duplicate AI work. A refresh
  may update the payload of a candidate that is still waiting so its eventual
  database/media write receives current source data.
- Preserve the candidate-pool state volume across deploys and rollbacks. Do not
  delete, replace, or initialize its SQLite file while either worker is live.
- Queue envelopes may carry the existing bounded `_sourceFacts` dictionary for
  AI review. It must affect the evidence fingerprint, remain out of scheduler
  logs, and be stripped by contract validation before PostgreSQL writes.
- `scraper.ai_manager` departs on a fixed 60-second schedule, leases up to three
  ready candidates across all platforms, sends the whole train to NVIDIA in one
  request, validates the returned multi-item JSON, and bulk-upserts the train to
  PostgreSQL. Failed AI or storage trains return to the pool with a bounded
  retry delay. Candidates arriving while a request is running wait for the next
  departure; never restore per-platform or concurrent NVIDIA parsers.
- `scraper.media.worker` is independent of AI completion. It polls PostgreSQL
  for uncached Instagram and Reddit image rows only after listings have been committed,
  downloads and uploads them to Cloudflare R2, then updates cache metadata. An
  image failure must never requeue AI work or delay a listing insert.
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

## Final Production Baseline (`1.1.2`)

This is the final live baseline established on 2026-07-16. Future changes must
preserve this split unless the user explicitly approves a new architecture.

- Home production scraper: `ubserver1` (`100.100.20.1`), directory
  `/docker/recon-scraper`, services `collector`, `ai-manager`, and
  `media-worker`, image `novn01/recon-scraper:1.1.2`.
- Oracle production web/data: `ubserver3` (`100.100.20.2`), directory
  `/docker/recon`, services `postgres`, one-shot `migrate`, `web`, and
  `cloudflared`, image `novn01/recon.id:1.1.2`.
- Public app: `https://recon.app-pixel.com` through Cloudflare Tunnel. The web
  container has no public host port.
- Production PostgreSQL is reachable by the home scraper only through
  Tailscale at `100.100.20.2:5432`; never publish it on `0.0.0.0` or point
  production at staging PostgreSQL.
- Debian staging is `100.100.20.3` under `/docker/recon`. It is intentionally
  stopped after release validation; its volumes and NVIDIA key are preserved
  for the next controlled staging test.
- Production was accepted with all three scraper workers running the same image
  ID, zero restarts, a healthy public app and R2 object, and a drained candidate
  pool (`pending=0`, `leased=0`). A running container alone is not proof of
  scraper health.

The v1-to-v2 evidence-fingerprint rollout created a one-time queue of old
semantic duplicates. Production cleanup marked only exact semantic duplicates
of already-completed versions as done; leased work completed normally and one
genuinely changed candidate boarded the next train. Do not repeat that cleanup
blindly. Any future growing queue must be diagnosed as live work, retries, or a
deduplication defect before records are changed.

## Supported Discovery Paths

### Reddit

- Use the public RSS feed for scheduled discovery.
- The four configured flairs start 60 seconds apart and each repeat every 240
  seconds, producing one scheduled RSS request per minute.
- This `60s` stagger / `240s` per-flair cadence is the approved production
  baseline. Staging sustained approximately 98% successful real network
  attempts at this rate; do not increase it merely because protected cooldown
  slots produce no request.
- Keep `image_mode = "rss"`; do not add per-post JSON or gallery requests to the
  scheduled path.
- RSS media URLs are canonicalized from resized `preview.redd.it` variants to
  the matching full-resolution `i.redd.it` asset. Deduplicate by that canonical
  asset identity so the feed thumbnail and first gallery frame do not become
  two slides.
- Preserve every distinct RSS gallery asset in source order. The optional
  detail JSON path may enrich controlled diagnostics, but production correctness
  cannot depend on it because the runtime currently receives `403`.
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
- Treat a final browser path under `/accounts/login/` as a login-wall signal
  even if the page title still resembles the requested profile.
- The `45s` stagger / `315s` repeat preserved data completeness during staging,
  but it also produced recurring login-wall pressure and one-hour cooldowns.
  Do not make it faster. If that pressure persists in production, the first
  fallback is a `60s` stagger / `420s` per-account repeat, not a bypass or a
  second browser identity.
- Instagram `postedAt` and signed/CDN image variations are intentionally
  excluded from the semantic evidence fingerprint. Caption or `_sourceFacts`
  changes create a new candidate version and supersede an older pending version
  for the same source post.
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
- Scheduled Facebook jobs only queue raw candidates. The centralized AI manager
  includes them in the same mixed-platform trains as Reddit and Instagram.
  Collector fields such as card price, location, and sold flags are source
  evidence only; local code must not translate them into database semantic
  values.
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

## Queue And AI Manager Guardrails

- A train departs every 60 seconds and carries at most three ready candidates.
  It makes exactly one NVIDIA request for the whole mixed-platform train and one
  bulk PostgreSQL write for the validated result. The proven production request
  budget is 8,192 output tokens with a 90-second timeout. Do not increase train
  capacity without controlled staging evidence; larger live batches previously
  produced truncated or invalid JSON.
- Fresh ready candidates board before delayed retries. A genuinely newer
  semantic version supersedes an older pending version of the same source post.
  Do not serialize into one AI request per listing and do not create one manager
  per platform.
- The durable pool, bounded retries, and platform cooldowns are the data-loss
  boundary. A staging burn-in drained the pool to zero without observed missing
  listings; provider or connector retries must continue to return work to the
  pool rather than discard it.
- NVIDIA capacity, timeout, or invalid-output failures must not permit raw
  candidates to bypass the mandatory AI parser or reach PostgreSQL.
- A provider-wide parser cooldown should pause new leasing globally. Repeated
  lease/retry churn while the circuit is open is an operational defect, even if
  the durable queue eventually recovers; fix it before increasing throughput.
- A temporary backlog is acceptable. A continuously growing pending/leased
  count, expired leases that never recover, or retries that exhaust without a
  terminal record is not.
- This queue is scraper-local operational state. It does not add a PostgreSQL
  schema migration or make the public web application responsible for scraping.

## Instagram And Reddit R2 Media Path

- R2 caching covers Instagram and Reddit. Facebook keeps its original image
  URLs in the tracked next release.
- Bucket: `recon-media-production`; public custom domain:
  `https://media.app-pixel.com`; object prefix: `production`.
- AI parse and PostgreSQL upsert finish first. The independent media worker then
  finds Instagram or Reddit `listing_images` rows whose `cached_url` is null, downloads
  the source, uploads immutable content-addressed objects, and updates only the
  cache metadata.
- Store Instagram and Reddit objects under separate
  `production/<platform>/...` prefixes and require the public API prefix to
  match the listing platform.
- Before first Reddit media-worker promotion, run
  `python -m scraper.reddit.backfill_images --fetch-missing` without `--apply`,
  inspect the summary, then run the same command with `--apply`. This upgrades
  historical previews, removes duplicate frames, and uses paced per-post RSS
  only for listings that have no image row. A final Reddit `429` stops further
  missing-image requests for that run.
- PostgreSQL is the durable media queue. On a cache failure, keep the original
  source URL so the UI can fall back to it; never move the listing back into the
  AI candidate pool.
- R2 credentials live only in
  `ubserver1:/docker/recon-scraper/.env.media-worker`. The collector and AI
  manager must not receive them. The NVIDIA key lives only in `.env.ai-manager`.
- The production media worker polls every 60 seconds and processes up to 25
  images per batch. A full batch may continue immediately to drain a backlog.

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

Staging is the authoritative environment for browser/network and release-image
behavior. It is normally stopped. Inspect the existing runtime before starting
only the services required for a bounded validation:

```bash
ssh root@100.100.20.3
cd /docker/recon
docker compose --env-file .env.staging -f compose.yml ps -a
docker pull novn01/recon-scraper:stagging
```

Current deployment facts:

- Debian staging host: `100.100.20.3`
- Project directory: `/docker/recon`
- Scraper image: `novn01/recon-scraper:stagging`
- Runtime env: `/docker/recon/.env.staging`
- Continuous containers: `recon-scraper-collector` and
  `recon-scraper-ai-manager`
- The tracked staging Compose stack does not currently define those scraper
  workers; the live validation containers are managed separately from it. Do
  not assume nonexistent Compose service names work. Preserve and inspect their
  existing env, network, command, and volume configuration before recreating
  them from the new `:stagging` image.
- Both containers must resolve to the exact same image ID, use
  `restart: unless-stopped`, and retain zero unexpected restarts.
- Chrome/Xvfb startup must remain behind `tini`; do not duplicate Compose `init`
  or browser flags in the service command.

After deployment, inspect only a bounded snapshot:

```bash
docker inspect recon-scraper-collector recon-scraper-ai-manager --format '{{.Name}} image={{.Image}} restarts={{.RestartCount}} status={{.State.Status}}'
docker logs --tail=100 recon-scraper-collector
docker logs --tail=100 recon-scraper-ai-manager
docker compose --env-file .env.staging -f compose.yml exec -T postgres psql -U recon -d recon_staging -c "select platform, status, count(*) from listings group by platform, status order by platform, status;"
```

For an AI-manager change, observe at least two departures from the promoted
image: the first must wait a full minute, subsequent departures must remain
60 seconds apart, each train must board at most three candidates, and each train
must produce one NVIDIA request and one bulk database write. Stop the staging
containers and PostgreSQL after validation, leaving volumes intact.

The verified two-worker staging burn-in ran for more than ten hours with zero
container restarts, drained the candidate pool, and showed no missing data.
Reddit remained healthy. Instagram remained complete because login walls opened
cooldowns, but those cooldowns are access pressure and must not be described as
clean fetch success. Do not attach an open-ended log monitor or restore
superseded access experiments.

## Production Promotion Gate

- Production must pin a fixed `SCRAPER_IMAGE_TAG`; never promote `stagging` or
  `latest` as the only production identity. Promote the exact image digest that
  passed staging instead of rebuilding it.
- Production on ubserver1 must define all three long-running services from the
  same fixed scraper image: collector, AI manager, and media worker. Use the
  documented commands, scoped env files, persisted state/log volumes,
  `restart: unless-stopped`, and the production `DATABASE_URL` where required.
- The tracked root `docker-compose.production.yml` is not the live split-host
  production scraper definition. The authoritative runtime Compose file is
  `ubserver1:/docker/recon-scraper/compose.yml`; do not deploy the tracked
  one-shot `scraper` profile and call the continuous runtime live.
- Stop and remove any old direct-write scheduler before starting the three
  workers. Never allow the old and new runtimes to scrape the same sources
  concurrently.
- Preserve the candidate pool during normal promotion and rollback. Start all
  three workers together; the manager may safely drain a legitimate backlog
  after restart and the media worker drains independently from PostgreSQL.
- Before accepting production, verify all three worker image IDs and commands,
  zero unexpected restarts, 60-second train departures, one NVIDIA request per
  train, bounded logs without a persistent `401`/`403`/`429` or login-wall
  flood, a pool that drains rather than grows indefinitely, fresh PostgreSQL
  rows from every enabled platform, and successful Instagram and Reddit R2 URLs
  after the Reddit media release is promoted.
- If any gate fails, restore the previous fixed image tag and keep the queue
  volume intact. Production promotion remains a manual, explicitly approved
  action.

## Change Checklist

Before committing scraper changes:

1. Trace imports, CLI entrypoints, Compose references, workflow references, and
   tests before removing a file.
2. Keep connector discovery cheap; AI semantic parsing is required and batched.
3. Preserve the shared normalized contract and idempotent write behavior.
4. Run the full scraper unit suite and Ruff.
5. For browser/network changes, build through GitHub Actions and validate the
   resulting image once on Debian staging.
6. For scheduler or manager changes, verify lease recovery, bounded retries,
   queue drain, and that the old combined runtime is not running.
7. Validate the environment-specific Compose file, not only the local
   development Compose file.
8. Update this file when the supported runtime workflow changes; do not append a
   historical diary.
