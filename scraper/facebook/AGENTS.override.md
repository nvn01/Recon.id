# Facebook Marketplace Data Collection Notes

Scope: this folder is only for Facebook Marketplace collection for RECON. Keep it focused on public Marketplace listings for computer, PC, tech, and gaming peripheral products.

Current connector script:

```powershell
python "scraper\facebook\facebook_marketplace.py" --once --query vga --limit 15 --format json --no-state
python "scraper\facebook\facebook_marketplace.py" --once --query vga --limit 15 --details --format json
python "scraper\facebook\facebook_marketplace.py" --watch --interval 60 --query vga --limit 15 --details
python "scraper\facebook\facebook_marketplace.py" --access-mode http-probe --query vga --no-state
python "scraper\facebook\facebook_marketplace.py" --list-targets
python "scraper\facebook\facebook_marketplace.py" --once --target-group hot --limit 15 --format json --no-state
python "scraper\facebook\facebook_marketplace.py" --calibrate-targets --target gpu-rtx --target laptop-gaming --format json --no-state
```

First-time local session setup:

```powershell
python "scraper\facebook\facebook_marketplace.py" --login
```

Important context:

- Plain HTTP requests to Facebook Marketplace returned blocked/error responses during probing.
- Browser/session-based collection works through Playwright with a persistent local profile.
- The local profile lives at `.facebook-profile/` inside this folder and must stay ignored by git.
- Search cards expose item id, URL, title, price, location, thumbnail image URL, and image alt text.
- Detail pages expose deeper data such as posted timing, condition, description, approximate location, and seller label.
- The script now emits the shared normalized listing shape: `platform`, `sourceUrl`, `externalId`, `title`, `description`, `category`, `brand`, `price`, `locationTexts`, `conditionText`, `sellerName`, `status`, `postedAt`, `firstFetchedAt`, `lastFetchedAt`, and nested `images`.
- Runtime state is local-only: `scraper/.state/facebook_marketplace.json`, `scraper/.state/facebook_marketplace.lock`, and `scraper/.logs/facebook_marketplace.jsonl`.
- Reviewed Facebook Marketplace URL/query targets live in `source_targets.json`. Keep this as scraper-side config, not PostgreSQL.
- Use named targets or target groups for production-like runs. `--query` remains useful for quick probes, but it does not carry the reviewed query-specific blocklist and cadence hints.
- Target groups are intentionally split by cadence: `hot` can be checked around minute-level diagnostics, `parts` and `peripherals` should be slower, and `discovery` is broad radar only.
- `--calibrate-targets` prints per-target candidate/matched/selected/skipped/blocked counts and sample titles without updating seen IDs. Use it before promoting a broad query into the minute-level group.
- Watch mode supports minute-level diagnostics with `--watch --interval 60`; this is not proof that Facebook tolerates production one-minute polling.
- When `--details` is enabled with state, detail pages are fetched only for new listings by default. Use `--detail-scope all` only for controlled debugging.
- Search result scrolling is bounded by `--max-scrolls` and `--candidate-limit`. Do not raise these aggressively to compensate for weak filters.
- `--access-mode http-probe` is a reachability diagnostic for anonymous direct HTTP. It does not bypass login gates or replace the browser connector.
- Price is still a nullable integer IDR field. `Gratis`, ask/DM, and ambiguous shorthand such as `Rp675` or `Rp800` should remain `null` unless AI parsing can confidently resolve the intended rupiah value.
- NVIDIA AI parsing can be enabled with `--ai-parse`; it must remain batched and only merge database-backed fields.
- Broad Electronics search is noisy. Focused queries such as `vga`, plus RECON keyword filtering, produce better samples.
- `vga` can also match unrelated products such as Yamaha Vega parts, so keep the relevance filter in place and tune keywords carefully.
- Do not add broad `switch` as a standalone keyword. It matched motorcycle brake-switch listings; Nintendo Switch listings should match through `nintendo` or a later phrase-specific rule.
- Do not message sellers, submit forms, or perform any account-side action from the scraper.
- Do not build login-wall bypass, CAPTCHA solving, account rotation, or IP-block evasion into this connector. Prefer cooldowns, degraded state, and explicit approval before changing access strategy.
