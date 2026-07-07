# Shared Scraper Context

This folder contains shared helpers used by multiple RECON scraper connectors. Keep it connector-neutral: source-specific selectors, platform status markers, target lists, cookies, session headers, and source-specific parsing assumptions belong in the platform folders, not here.

## Current Shared Modules

- `listing_contract.py` is the Prisma-facing normalized listing gate. Connectors should validate through this shape before database writes.
- `config.py` loads `scraper/config/sources.toml` and provides small typed access helpers for values read by `scraper/main.py`.
- `runtime.py` owns Phase 2 runtime guardrails: duplicate-run file locks, cooldown state helpers, retry/backoff with jitter, `Retry-After` parsing, scraper-side JSONL logging, and explicit egress config parsing.

## Runtime Guardrail Rules

1. File locks are local filesystem locks for scheduled/single-host scraper runs. They are not a distributed lock for multi-host production.
2. Cooldown state is scraper-side state only. Do not add scraper-run, connector-health, cooldown, or lock tables to PostgreSQL for v1.
3. Retry policies must stay bounded. Do not add infinite retries or crash/restart scheduling loops that can hammer source platforms.
4. Jitter exists to desynchronize retries and scheduled loops, not to hide scraper identity or bypass rate limits.
5. `resolve_egress_config()` defaults to direct access. Proxy mode requires `SCRAPER_EGRESS_MODE=proxy`, `SCRAPER_ALLOW_PROXY=true`, and `SCRAPER_PROXY_URL`. VPN mode requires `SCRAPER_EGRESS_MODE=vpn` and `SCRAPER_ALLOW_VPN=true`.
6. Proxy URLs may contain credentials; runtime log output must use `redact_url()` or `EgressConfig.as_log_dict()` instead of printing raw values.
7. VPN mode is only an explicit deployment/network posture. Python does not rotate VPNs, accounts, or proxy endpoints.

## Footnotes For Future Agents

- If a connector needs a new shared helper, first check whether it is genuinely source-neutral. If it mentions Reddit, Instagram, Facebook, Marketplace, selectors, account names, or platform-specific status words, keep it out of this folder.
- If a new runtime behavior affects cadence, cooldown, locking, logging, or egress, add or update tests in `scraper/tests/test_runtime_guardrails.py`.
- `--no-state` intentionally bypasses locks, cooldown files, and logs for diagnostics. Do not use it as the scheduled production path.
- Shared runtime helpers are allowed to fail closed when egress config is unsafe or incomplete. That is preferable to silently using a proxy or VPN path.
