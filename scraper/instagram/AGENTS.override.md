# Instagram Data Collection Notes

Scope: this folder is only for Instagram consignment/store collection for RECON. Keep it focused on public sale posts for computer, PC, tech, and gaming peripheral products.

Current proof script:

```powershell
python "scraper\instagram\instagram_samples.py"
```

Important context:

- Seed accounts explored: `chemicy.consignment`, `thelazytitip`, `sensegame.id`, `cappee.gaming`, `gamecentral.id`, `consigngaming`, and `ggsconsign`.
- Anonymous Instagram profile HTML did not expose reliable recent post URLs/captions during probing.
- Instagram `web_profile_info` returned `429 Too Many Requests` during probing.
- Individual post pages can be reachable, but anonymous static HTML often does not expose clean captions.
- The current script is a seeded sample probe, not a solved latest-post scraper.
- Future improvements must distinguish real sale posts from pinned posts, memes, engagement content, and non-sale posts.
- Do not hardcode login credentials or collect private user data. If browser/session scraping becomes necessary, keep it explicit and local.

## Phase 2 Instagram Diagnostic Recap

The active seed list is `chemicy.consignment`, `thelazytitip`, `sensegame.id`, `cappee.gaming`, `gamecentral.id`, `consigngaming`, and `ggsconsign`. There is no `chemicygaming` Instagram source in the current connector list.

During the July 2026 Instagram pass, anonymous Chrome diagnostics could fetch profile timeline JSON through Instagram's web app path, but direct non-browser requests had previously hit `429`. Treat browser-observed `web_profile_info` responses as a diagnostic source, not a production guarantee, and do not commit browser cookies, CSRF tokens, or captured session headers into scraper code.

Profile timelines can include pinned or stale grid entries ahead of newer posts. Always sort fetched posts by `taken_at_timestamp` before deciding "latest", and run content-vs-listing classification before normalization. Example: `thelazytitip` latest fetched post `DadRWvpiC3W` was a content reel and should be skipped; the newest storable listing in that diagnostic window was `Dac6_Sdkl0K`.

The local diagnostic output was written under `.codex-runtime/instagram-latest-normalized-local.json`. It matched the Prisma-facing listing shape with `platform`, `sourceUrl`, `externalId`, `title`, `description`, `category`, `brand`, `price`, `locationTexts`, `conditionText`, `sellerName`, `status`, `postedAt`, `firstFetchedAt`, `lastFetchedAt`, and nested `images`. Runtime diagnostics stay local-only and must not be treated as committed fixtures unless they are sanitized and intentionally promoted later.

AI parsing should only enrich listing fields after deterministic pre-classification. The existing NVIDIA parser can be reused later, but a missing key, network block, or model failure must degrade to rule/local parsing rather than blocking the connector.

## Availability Rules

Availability reconciliation should be deterministic and account-specific. Do not use AI to decide sold status when the account has a clear template.

Known sold markers:

- `thelazytitip`: captions beginning with or clearly containing `SOLD` such as `SOLD 💸💸💸` mark the listing as `SOLD`.
- `consigngaming`: captions beginning with or clearly containing `🚫SOLDOUT🚫` mark the listing as `SOLD`.
- `gamecentral.id`: captions beginning with or clearly containing `SOLD OUT`, including formats like `❌SOLD OUT IN 1 MINUTE❌`, mark the listing as `SOLD`.
- `chemicy.consignment`: sold listings may be removed rather than relabeled. If a previously stored post disappears or fetches unavailable, do not immediately mark it sold; keep current status and log the degraded/missing check until a later policy is chosen.
- For accounts without a known sold label, only mark `SOLD` on clear sold text. Otherwise keep parser status as `AVAILABLE` or `UNKNOWN`.

For status refresh, fetch a small recent window such as the last 10 product posts per account and update only the `status` field when deterministic markers match.
