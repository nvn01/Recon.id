# Scraper Service Context

This folder is the Python scraper service boundary for RECON.

Keep scraper-specific source URLs, cadence, user-agent, retry, and platform configuration here instead of in the root T3 web app env files.

The existing platform folders are proof collectors until the normalized listing contract and ingestion path are implemented.

## Phase 2 Reddit Recap For Other Connectors

Reddit is the current reference connector shape:

1. Collect source data with the safest available public endpoint.
2. Normalize into the Prisma listing contract, not a source-specific shape.
3. Keep raw seller text in `description`; only extract fields that exist in the database.
4. Use batched AI parsing only as an enrichment layer for messy text, with rule parsing as fallback.
5. Emit nested `images` as `sourceUrl`, `position`, and `altText`; fetch all gallery images when the source exposes them, but degrade to available thumbnails when blocked.
6. Keep platform rate limits, cooldowns, locks, and fetch notes in the platform folder.

Instagram and Facebook should reuse the same parser contract and AI enrichment pattern instead of inventing separate output schemas.

## Phase 2 Instagram Recap For Facebook

Instagram confirmed the shared connector shape still holds, but it also exposed source-specific traps that Facebook should account for:

1. The source list must be explicit and reviewed. The current Instagram sources are `chemicy.consignment`, `thelazytitip`, `sensegame.id`, `cappee.gaming`, `gamecentral.id`, `consigngaming`, and `ggsconsign`; remove stale source names instead of silently ignoring them.
2. Fetching and parsing are separate decisions. Instagram profile data could be inspected through anonymous Chrome diagnostics, while direct anonymous requests may return `429`; future Facebook work should first prove the safest fetch source before adding parser/storage behavior.
3. Never trust returned order blindly. Instagram profiles can surface pinned or stale posts before newer posts, so connectors should sort by source timestamp and then classify content vs product posts.
4. Keep raw source text in `description`, then map only database-backed fields into the normalized listing shape. Do not emit parser-only evidence, confidence, OCR notes, or model-specific fields into normal listing JSON until the schema explicitly changes.
5. Availability reconciliation should use deterministic source-specific markers when available. For Instagram examples, `thelazytitip` uses `SOLD`, `consigngaming` uses `SOLDOUT`, and `gamecentral.id` uses `SOLD OUT`; AI is not needed for these status updates.
6. For removed or unavailable posts, do not guess sold status. Log the degraded fetch or missing-post check in scraper-side state, then keep the current listing status until a source-specific rule is approved.
7. Runtime diagnostics such as `.codex-runtime/instagram-latest-normalized-local.json` are local evidence only. Do not commit browser cookies, CSRF tokens, captured headers, or unsanitized source snapshots.

Facebook should inherit the same public-source posture: prove access first, keep run health and cooldowns scraper-side, normalize into `listings`/`listing_images`, and degrade gracefully when the source blocks, gates, removes, or reorders content.

## Phase 2 Facebook Recap For Future Scraper Work

Facebook Marketplace is now a hardened diagnostic connector, but it remains outside database ingestion until the ingestion path is explicitly approved.

Current useful commands:

```powershell
python "scraper\facebook\facebook_marketplace.py" --list-targets
python "scraper\facebook\facebook_marketplace.py" --once --target gpu-rtx --limit 5 --headless --format json --no-state
python "scraper\facebook\facebook_marketplace.py" --once --target gpu-rtx --limit 5 --details --ai-parse --format json --no-state
python "scraper\facebook\facebook_marketplace.py" --watch --interval 60 --target-group hot --headless --details --ai-parse
python "scraper\facebook\facebook_marketplace.py" --calibrate-targets --target gpu-rtx --target laptop-gaming --format json --no-state
python "scraper\facebook\facebook_marketplace.py" --access-mode http-probe --target gpu-rtx --no-state
```

Important Facebook-specific facts:

1. Plain HTTP/requests access is not reliable. The direct probe returned HTTP 400/no item cards; keep it as a diagnostic only, not the collection strategy.
2. The practical path is Playwright with a persistent local profile. It can run headless after session setup; first-time setup may need `--login` with a visible browser. Do not commit `.facebook-profile*`.
3. Reviewed Marketplace targets live in `scraper/facebook/source_targets.json`. This is scraper-side config, not PostgreSQL. Do not reintroduce `source_targets`, `scrape_runs`, or connector health tables into the Phase 1 database.
4. Use target groups instead of broad Electronics search. `hot` is minute-level diagnostic coverage; `parts` and `peripherals` should run slower; `discovery` is broad radar only and should not be promoted without calibration evidence.
5. `--calibrate-targets` is the safe way to judge a query before adding it to a faster cadence. It reports candidate, matched, skipped, blocked, and sample title counts without updating seen IDs.
6. The connector emits the shared listing shape only: `platform`, `sourceUrl`, `externalId`, `title`, `description`, `category`, `brand`, `price`, `locationTexts`, `conditionText`, `sellerName`, `status`, `postedAt`, `firstFetchedAt`, `lastFetchedAt`, and nested `images`.
7. NVIDIA AI parsing is optional with `--ai-parse`; it must stay batched and limited to database-backed fields. Rule parsing remains the fallback. Use `--ai-prefer` carefully because model output can be worse than browser/rule fields.
8. Detail pages are expensive and more likely to expose gating. With state enabled, `--details` fetches details only for new listings by default; use `--detail-scope all` only for controlled debugging.
9. Runtime state and logs are local-only: `scraper/.state/facebook_marketplace.json`, `scraper/.state/facebook_marketplace.lock`, and `scraper/.logs/facebook_marketplace.jsonl`.
10. Parser fixes already handled: broad `switch` was removed, CLI `--limit` now overrides target defaults, low-value titles such as `·` fall back to image alt text, card-location blobs containing prices are dropped, `Bekasi` no longer becomes condition text, and ROG/Zephyrus/Victus/Nitro style laptop titles classify as `Laptop`.
11. Do not add login-wall bypass, CAPTCHA solving, account rotation, proxy escalation, seller messaging, form submission, or account-side actions. Prefer cooldowns, degraded state, and explicit approval before changing access strategy.

Latest verification before this note: Python compile passed, JSON target config validated, `ruff` passed for scraper files, `npm run check` passed, headless Facebook fetch returned live listing JSON, and `npm audit --omit=dev` still only showed the known existing `next -> postcss` advisory.
