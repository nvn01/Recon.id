# Recon Agent Instructions

## Project Purpose

Recon is an early-stage repository for building the easiest way to monitor wishlist computers, computer parts, and peripherals across multiple preloved marketplaces and social platforms.

The product goal is simple: users should not need to repeatedly check every marketplace by hand. Recon should discover relevant new listings quickly, normalize them into a consistent structure, and make them easy to inspect, compare, and revisit.

## Current Status

Recon v1 entered production on 2026-07-16. The public discovery UI, read-only
API, PostgreSQL schema, multi-source collector, centralized NVIDIA AI manager,
independent Instagram R2 media worker, and direct production ingestion path are
live. Treat the current repository as a working production system, not an
exploratory scaffold.

The main operational focus now is:

- Make scraping repeatable, source-aware, and resilient.
- Normalize listings into a consistent data structure before writing them to the database.
- Extract useful database fields from messy post descriptions, including category, brand, price, condition, locations, status, and seller context.
- Avoid rate limits, temporary blocks, duplicate spam, and brittle scraping behavior.
- Keep the system inspectable so future agents can understand what happened during each scrape run.
- Preserve the split production topology and deploy only fixed semantic-version images.
- Monitor connector health, AI queue throughput, production disk usage, and database growth.

Phase 5 operational hardening is implemented. Every connector has a sanitized
parser fixture, duplicate-run locks and connector cooldowns have regression
coverage, and `scraper.operational_report` produces separate daily data-quality
and manual-review JSON artifacts under the persisted scraper log volume.

The public UI and backend contracts are implemented. Keep scraper operations,
database writes, and public UI concerns separated unless a requested change
explicitly crosses those boundaries.

## Product Freshness Goal

The long-term product goal is near minute-level freshness so users do not miss wishlist items.

Do not blindly run every connector every minute in production. Prove source safety first. Start with conservative staging checks, connector-level cooldowns, retry limits, backoff, and clear health metrics. Tighten cadence only when the source can tolerate it without lockouts, noisy failures, or duplicate pileups.

## Planning Context

Before making major changes, inspect the existing planning artifacts:

- `.plan/first-pass.html`
- Any nearby planning notes or scraper files related to the requested task.

Preserve the current architecture direction unless the user explicitly changes it:

1. Scraper and backend setup.
2. Database schema and ingestion contracts.
3. Scraper core and source connectors.
4. Backend API.
5. Operational hardening before public UI work.

## Major Feature Proposal Workflow

When Novandra opens a new branch/worktree or asks what a new major feature would look like, do not start building immediately.

First answer with a complete feature model/spec that explains:

- What the user experience should be.
- What data model or storage changes are needed.
- What API/backend behavior is needed.
- What frontend behavior is needed, if any.
- How the feature works without violating current project constraints, such as no user accounts or no authentication.
- Important tradeoffs, failure modes, abuse risks, privacy risks, and edge cases.
- How the feature should be tested and verified.
- Whether it belongs in the current plan or should update `.plan/first-pass.html`.

Example trigger:

> what would it look like if user interested in one post then want to save or like some the product in the web app without need to doing some login or authentication since our app is not have users profile feature yet.

For this kind of request, propose the whole model first. Wait for explicit approval before implementing. Approval may be phrased casually, such as "Oke i like that, build it!", "Love it, build it!", "build it", or a similar clear instruction.

If Novandra asks follow-up questions, keep refining the model/spec. Do not treat interest in the idea as permission to build.

## Private Local Skills

The `.agents/` directory is intentionally private and ignored by git. It may contain personal, sensitive, or non-public workflow knowledge.

When `.agents/` is available locally:

- Read `.agents/RECRUITED_SKILLS.md` before choosing workflow skills.
- Use only the relevant skill files for the task.
- Do not copy private skill contents into public repository files.
- Do not remove `.agents/` from `.gitignore`.
- Do not assume GitHub or another remote environment has access to `.agents/`.

When `.agents/` is not available, continue with the public repository context and explain any limitation if it affects the work.

## Skill And Agent Usage

Use specialized skills and subagents when they materially improve the work, especially for:

- Scraper design and connector investigation.
- Backend and API design.
- PostgreSQL, Prisma, and migration planning.
- TDD, verification, linting, formatting, and coverage checks.
- Security review, especially around scraping, user data, environment variables, and deployment.
- Homelab CI/CD while the project is still hosted locally.
- Product, legal, compliance, operations, business, marketing, and brand review when those perspectives are relevant.

Knowledge-work skills act like internal departments. If a non-technical department has a recommendation, warning, progress update, or decision request, leave a clear ticket-style note for Novandra instead of making the business decision silently.

For investigation-heavy work, prefer parallel research or subagents when available. Synthesize their findings into concrete decisions, risks, and next steps.

## Working Style

Be direct, critical, and truthful. If a decision, algorithm, tool, or architecture choice is weak, say so and propose a better option.

Do not flatter the plan. Recon needs practical scrutiny, especially around scraping reliability, source limits, legal exposure, operational cost, and data quality.

When implementation begins:

- Prefer test-driven changes for new behavior and bug fixes.
- Keep changes scoped to the requested area.
- Validate inputs at boundaries.
- Avoid hardcoded secrets.
- Run the relevant tests, type checks, lint, formatting, and security checks when available.
- Review the final diff for risky patterns before handing off.

## Scraping Rules

The scraper must be designed as a reliable ingestion system, not a quick one-off script.

Required expectations:

- Use public data only unless the user explicitly approves another authenticated workflow.
- Respect source-specific limits, errors, and blocking signals.
- Implement per-source backoff, cooldowns, retry limits, and failure logging.
- Make each connector idempotent so repeated runs do not create duplicate listings.
- Store source URL, external listing identity when available, scrape timestamp, raw text, and parsed database fields.
- Preserve raw descriptions when extracting category, brand, condition, location, or price from unstructured text.
- Mark inferred fields as inferred. Do not present low-confidence extraction as fact.
- Prefer structured parsing when a source provides structured data.
- Keep connector-specific logic isolated behind a shared normalized listing contract.

VPN or proxy-capable egress may be useful later, but do not use network switching to hide broken scraper behavior. Fix cadence, parsing, backoff, and connector health first.

## Data Contract Direction

Normalized listings should be able to represent at least:

- Source platform and source URL.
- External listing ID or stable derived fingerprint.
- Title.
- Description or raw post text.
- Price and currency.
- Product category.
- Brand.
- Condition.
- One or more public listing locations.
- Seller or account identity when available.
- Original image URLs and cached thumbnail metadata.
- Listing status, such as active, sold, removed, unknown, or duplicate.
- First fetched, last fetched, and scraper-side run metadata.
- Parser provenance in scraper-side logs or notes until the database plan explicitly adds provenance columns.

Design the schema so future agents can inspect why a field has a value.

## Inspectability

Every runtime feature should be inspectable by another agent or future session.

For scraper and backend work, include or preserve:

- Scrape-run logs.
- Connector health state.
- Source-specific error categories.
- Dedupe decisions.
- Ingestion counts.
- Raw-to-normalized mapping evidence.
- Clear environment variable names.
- Minimal runbooks or comments where operational behavior is not obvious.

## Section Overrides

Some folders, services, features, or platform connectors may have their own `AGENTS.override.md`.

Use those files for local context such as:

- Platform-specific scraping notes.
- Footnotes and issue history.
- Known brittle selectors or parsing assumptions.
- Connector health findings.
- Operational cautions for future agents.

When working inside a folder with an override file, read it together with this root file. The more specific override controls local details, but it should not contradict the root project direction without explaining why.

After building a major feature, create or update the right local agent context file when the implementation leaves durable assumptions, feature-specific behavior, or operational risks that future agents need to understand.

Use these naming rules:

- `AGENTS.override.md` for broad folder-level context that applies to everything in that directory.
- `AGENTS.<area>.md` for a specific major feature or subsystem inside a busy directory, such as `AGENTS.api.md`, `AGENTS.save-feature.md`, `AGENTS.parser.md`, or `AGENTS.thumbnail-cache.md`.

Do not create context files for trivial edits. Create them when they explain decisions that would otherwise be rediscovered later, such as API contracts, data parsing assumptions, anonymous-user behavior, storage rules, rate-limit behavior, or known failure modes.

## Deployment Direction

Use the homelab CI/CD path for now. Keep the architecture portable so Recon can move to a VPS or another hosting platform after the app and scraper are stable.

Prefer Dockerized services for the web app, scraper, and PostgreSQL. Keep staging and production configuration separate, and never commit real secrets.

## Live Production Topology

Production is intentionally split because Oracle Cloud egress is unsuitable for
Instagram and Facebook scraping. Do not collapse these services back into one
host without an explicit architecture decision.

| Role | Host | Tailscale IP | Runtime directory | Services |
| --- | --- | --- | --- | --- |
| Production scraper | `ubserver1` on PVE1 | `100.100.20.1` | `/docker/recon-scraper` | `collector`, `ai-manager`, `media-worker` |
| Production web and data | `ubserver3` on Oracle Cloud ARM64 | `100.100.20.2` | `/docker/recon` | `postgres`, one-shot `migrate`, `web`, `cloudflared` |
| Staging | `debian` on PVE2 | `100.100.20.3` | `/docker/recon` | Staging web, PostgreSQL, collector, and AI manager; intentionally stopped after the production launch |

Public production URL: `https://recon.app-pixel.com`.

The Cloudflare tunnel is named `recon-production-ubserver3`. Its published
route is `recon.app-pixel.com -> http://web:3000`. The web container has no
public host port; Cloudflare Tunnel is the public ingress. Production
PostgreSQL is bound on the Oracle host only at `100.100.20.2:5432` for
Tailscale access from the home scraper. Never publish PostgreSQL on
`0.0.0.0:5432` or point production services at staging PostgreSQL.

Production database credentials are separated by role:

- Migration/owner credentials apply Prisma migrations and own the schema.
- The web app receives a SELECT-only role.
- The AI manager and media worker receive a scraper role with
  SELECT/INSERT/UPDATE/DELETE.
- The collector receives read-only database access for operational reports and
  does not receive the NVIDIA key or write credentials.

The collector queues raw candidates in the shared persisted scraper state
volume. The AI manager is the only production process that enriches queued
candidates with NVIDIA and writes validated listings to PostgreSQL. That write
is the end of the AI critical path; it must never wait for image downloads or
R2. A separate media worker polls PostgreSQL for uncached Instagram images,
uploads them to R2, and updates only their cache metadata. All three processes
run the same fixed scraper image with separate commands and scoped env files.

The supported AI-manager design is a fixed one-minute train, not an immediate
two-item loop. Each departure leases up to 20 ready candidates across Reddit,
Instagram, and Facebook, sends that entire train to NVIDIA in one request, and
bulk-upserts the validated result. Candidates collected while that request is
running wait for the next train. Fresh candidates board before delayed retries.
Never restore per-platform AI workers or multiple concurrent NVIDIA parsers.

Candidate fingerprints represent semantic AI work. Instagram `postedAt` and
CDN image-path variations must not requeue an otherwise unchanged post. A
refresh may update the payload of a candidate that is still waiting so the
eventual PostgreSQL/R2 path receives current media URLs. A genuinely changed
caption or `_sourceFacts` value creates one new version and supersedes the older
pending version of that source post.

## Instagram Media Cache

Instagram images are cached in Cloudflare R2 because signed Instagram CDN URLs
can expire or fail for public users. This is intentionally Instagram-only:
Facebook and Reddit continue to use their original image URLs.

- Bucket: `recon-media-production`
- Public custom domain: `https://media.app-pixel.com`
- Object layout: `production/instagram/<sha256-prefix>/<sha256>.<extension>`
- Upload owner: the dedicated media worker on ubserver1, after the AI manager
  has committed the listing to PostgreSQL
- Worker command: `python -m scraper.media.worker`
- Poll cadence: 60 seconds; a full batch continues immediately so a backlog can
  drain without waiting another minute between batches
- Backfill command: `python -m scraper.media.backfill_instagram`

The media worker validates HTTPS source hosts against Instagram/Facebook CDN
suffixes, rejects private-address resolution, limits redirects and downloads,
checks MIME type and image signatures, then uploads immutable content-addressed
objects. PostgreSQL is the durable media queue: an Instagram `listing_images`
row with `cached_url IS NULL` remains pending. An individual cache failure is
non-fatal and unrelated to AI queue completion; PostgreSQL retains the original
source URL and the UI falls back to it. The public API never fetches remote
media and exposes the cached URL through its existing `sourceUrl` DTO field only
when the listing platform is Instagram.

R2 write credentials and `R2_OBJECT_PREFIX=production` belong only in
`ubserver1:/docker/recon-scraper/.env.media-worker`. Do not give them to the AI
manager, collector, Oracle web container, or browser. Keep the R2 development
URL disabled; production delivery uses the custom domain so Cloudflare caching
is active.

## Production Runtime Files And Secrets

Runtime Compose and environment files live on the servers and are not the
tracked root Compose files in this repository.

On `ubserver3:/docker/recon`:

```text
compose.yml
.env.production
.env.tunnel
initdb/01-roles.sh
```

On `ubserver1:/docker/recon-scraper`:

```text
compose.yml
.env.deploy
.env.collector
.env.ai-manager
.env.media-worker
```

`WEB_IMAGE_TAG` is stored in the Oracle `.env.production` file.
`SCRAPER_IMAGE_TAG` is stored in the ubserver1 `.env.deploy` file. The NVIDIA
API key is stored only in `.env.ai-manager`; the database and R2 credentials
used by media caching are stored in `.env.media-worker`. The Cloudflare tunnel
token is stored only in `.env.tunnel` on ubserver3. Secret-bearing files were
created root-owned with mode `600`; preserve that ownership and mode. Never
print, copy into logs, or commit their values. The staging NVIDIA key was
retained so staging can be restarted for future release validation.

## Production Deployment And Update Runbook

The release path is:

```text
push/merge main
  -> GitHub Actions verifies and publishes :stagging
  -> verify staging and image manifests
  -> manually promote the same manifests to X.Y.Z
  -> deploy that fixed version to ubserver3 and ubserver1
  -> verify web, database, tunnel, collector, AI manager, and media worker
```

For a normal update:

1. Let `.github/workflows/staging.yml` finish successfully after the merge to
   `main`.
2. Validate the change on Debian staging. Staging is currently stopped; start
   only the services needed for the validation and stop them again afterward.
3. Confirm `novn01/recon.id:stagging` contains `linux/amd64` and `linux/arm64`,
   and `novn01/recon-scraper:stagging` contains `linux/amd64`.
4. Manually dispatch `.github/workflows/promote-production.yml` with the next
   semantic version. This copies the exact staging manifests; it must not
   rebuild production.
5. On ubserver3, change only `WEB_IMAGE_TAG` to the promoted version, then pull
   and apply the Compose stack. Allow the one-shot migration service to finish
   before considering the web deployment healthy.
6. On ubserver1, change only `SCRAPER_IMAGE_TAG`, then pull and apply all three
   scraper worker services.
7. Run the verification checks below. Do not call the deployment complete only
   because containers started.

Useful production checks:

```bash
# Oracle web, database, migrations, and tunnel
ssh root@100.100.20.2
cd /docker/recon
docker compose --env-file .env.production ps -a
docker compose --env-file .env.production logs --tail 100 migrate web cloudflared postgres

# Home collector, AI manager, and Instagram media worker
ssh root@100.100.20.1
cd /docker/recon-scraper
docker compose --env-file .env.deploy ps
docker compose --env-file .env.deploy logs --tail 120 collector ai-manager media-worker
docker inspect -f '{{.Name}} restarts={{.RestartCount}} status={{.State.Status}}' \
  recon-scraper-production-collector-1 \
  recon-scraper-production-ai-manager-1 \
  recon-scraper-production-media-worker-1
```

Production verification requires all of the following:

- `https://recon.app-pixel.com` reaches HTTP 200 after its expected redirect to
  `/collection/all`, with valid TLS.
- PostgreSQL and web are healthy, `migrate` exits `0`, and cloudflared remains
  connected.
- Collector, AI manager, and media worker are running with restart count `0`.
- Recent collector logs show normal `success`, `no_new_data`, or intentional
  cooldown outcomes instead of a persistent `401`, `403`, or `429` flood.
- AI manager logs continue to show successful parsing and storage writes.
- AI manager train logs show `intervalSeconds: 60`, at most one NVIDIA request
  per departure, and `boarded` matching the number processed by that request.
- Media worker logs show bounded Instagram-only cache batches; its failures do
  not requeue AI candidates or block listing inserts.
- Production listing counts continue to grow when new candidates are found.

The retired two-item loop allowed volatile Instagram versions and retries to
grow the queue to roughly 130-150 candidates. Do not restore that behavior.
With the train manager, new posts should normally leave within the next
one-minute departure and backlogs drain in trains of up to 20. Treat a steadily
growing queue, repeated provider errors, or a stalled `done` count as an
operational issue; do not assume a running container is healthy.

Rollback means restoring both `WEB_IMAGE_TAG` and `SCRAPER_IMAGE_TAG` to the
previous known-good fixed version and reapplying Compose. Image rollback does
not automatically roll back database migrations. Review migration
compatibility before reverting the web or scraper across a schema change.

## Staging State After Production Launch

The Debian staging stack at `100.100.20.3:/docker/recon` was manually stopped
after production verification on 2026-07-16. Its containers, named volumes,
database, logs, and scraper state were preserved. Do not interpret stopped
containers as a staging failure, and do not delete its volumes when restarting
or cleaning up. Start staging only for an explicit validation or burn-in task,
then stop its web, PostgreSQL, collector, and AI manager when the check is done.

## Production Operational Cautions

- ubserver1 disk usage reached approximately 85% after pulling the browser-heavy
  scraper image, with about 21 GB free at launch. Check disk space before
  pulling several additional scraper versions; do not prune images or volumes
  without confirming rollback and data requirements.
- ubserver3 had a pending kernel upgrade after Docker installation and was not
  rebooted during launch. Verify the current kernel and service state before a
  planned reboot.
- Cloudflare Tunnel is the intended web ingress. Do not add public `3000`,
  `5432`, or database security-list rules as a shortcut.
- Keep production on fixed semantic-version application tags. Do not deploy
  `latest` or the moving `stagging` tag directly to production.

## CI/CD Image Publishing

GitHub Actions publishes separate web and scraper Docker images to Docker Hub. The scraper service has its own Dockerfile and is still not included in the root web image because `scraper/` is excluded from the root Docker context.

Required GitHub repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Current Docker Hub image names:

```text
novn01/recon.id
novn01/recon-scraper
```

Staging workflow:

- File: `.github/workflows/staging.yml`
- Trigger: push to `main` or manual workflow dispatch.
- Checks: `npm ci`, Prisma validate, Next lint/typecheck/build, Python scraper unit tests, and Ruff.
- Publishes `novn01/recon.id:stagging` as a multi-platform manifest for
  `linux/amd64` and `linux/arm64`.
- Publishes `novn01/recon-scraper:stagging` for `linux/amd64`, matching the
  ubserver1 production scraper host.

Production workflow:

- File: `.github/workflows/promote-production.yml`
- Trigger: manual workflow dispatch only.
- Input: Docker tag version, for example `1.0.0`.
- Behavior: uses `docker buildx imagetools create` to copy the complete
  `stagging` manifests to `<version>`. This preserves both web platforms and
  the scraper platform. Do not replace it with a runner-local pull/tag/push,
  which would promote only the runner architecture, and do not rebuild
  production separately from staging.

First production application version: `1.0.0`.

Production rollback is a manual Docker tag choice: redeploy the previous known-good fixed version tags.

## Documentation And Handoff

Capture durable project knowledge in the right place:

- Architecture, schema, API, scraper, or deployment decisions belong in project docs or nearby override files.
- Temporary debugging notes should stay local unless they are useful to future contributors.
- Private skill knowledge stays private.
- If there is no obvious documentation location, ask before creating a new top-level file.

When leaving a handoff, include:

- What changed.
- What was verified.
- What remains risky or unknown.
- Which files or commands matter next.
