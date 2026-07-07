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
