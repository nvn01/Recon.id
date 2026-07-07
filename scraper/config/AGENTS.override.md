# Scraper Config Context

This folder contains committed scraper configuration that is safe to share. It should describe public source names, source URLs, account usernames, target-file references, conservative limits, timeout values, retry settings, jitter, cooldowns, and other non-secret runtime defaults.

## Current File

- `sources.toml` is loaded by `scraper/shared/config.py` and consumed by `scraper/main.py`.
- `[run]` holds orchestrator defaults such as `limit`, `timeout_seconds`, retry backoff, jitter, lock stale seconds, and AI batch/rate-limit defaults.
- `[reddit.wts_computers]`, `[instagram.accounts]`, and `[facebook.marketplace]` hold connector-specific safe defaults.

## What Belongs Here

1. Public source identifiers: subreddit names, flair names, Instagram account usernames, and paths to reviewed source-target JSON files.
2. Conservative fetch controls: `limit`, `timeout_seconds`, `retries`, `retry_base_seconds`, `retry_max_seconds`, `retry_wait_seconds`, `retry_jitter_seconds`, `delay_seconds`, and `cooldown_seconds`.
3. Safe connector defaults such as Reddit `image_mode = "rss"` and Facebook `headless = true`.
4. References to scraper-side config files such as `../facebook/source_targets.json`.

## What Must Not Go Here

1. Browser cookies, CSRF tokens, captured request headers, access tokens, API keys, passwords, proxy credentials, or VPN credentials.
2. Raw source snapshots, parser evidence payloads, runtime logs, connector health state, seen-ID state, or lock files.
3. PostgreSQL schema decisions. Prisma remains the schema source of truth.
4. Database URLs or deployment-only secrets. Use ignored env files or secret managers.

## Egress Configuration Boundary

Proxy/VPN is intentionally controlled by environment variables, not TOML:

```text
SCRAPER_EGRESS_MODE=direct|proxy|vpn
SCRAPER_ALLOW_PROXY=true
SCRAPER_PROXY_URL=http://...
SCRAPER_ALLOW_VPN=true
```

Default mode is `direct`. Do not add proxy URLs to `sources.toml`; proxy URLs can contain credentials and must stay outside committed config.

## Footnotes For Future Agents

- When increasing cadence or lowering cooldowns, verify with live connector health first. The long-term product wants freshness, but Phase 2 still favors source safety over speed.
- Keep Facebook target changes in `scraper/facebook/source_targets.json` first, then reference target IDs or groups here after calibration.
- If a source starts returning 403/429, do not solve it by editing proxy/VPN defaults here. Inspect connector behavior, lower cadence, use cooldowns, or mark degraded.
