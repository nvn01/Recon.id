# Discovery-First Scraper Rebase

## Contract

Fast discovery must finish before optional detail, gallery, or AI enrichment:

- Instagram reads the public profile document's embedded timeline with logged-out Chrome.
- Facebook reads the initial Marketplace search document's embedded Relay feed.
- Reddit remains RSS-first.
- `sourceUrl` and platform IDs remain the dedupe anchors; normalized output still passes through `listing_contract.py` before opt-in database writes.

No scheduled discovery path uses login, authentication, persistent browser profiles, per-item detail requests, scrolling, CAPTCHA handling, account rotation, or VPN/proxy rotation.

## TDD Evidence

Source intent came from `.plan/first-pass.html`, `.plan/phase3-production-scraper-hardening-prd.md`, and the approved live Chrome inspection.

User journeys:

1. As the RECON owner, I want every Instagram account checked inside ten minutes without requesting all seven at once.
2. As the RECON owner, I want Instagram and Facebook to use their initial public documents so limits are spent on discovery rather than scrolling or internal API replay.
3. As the RECON owner, I want structured source status, price, identity, and images preserved in the existing DB-shaped contract.

| Guarantee | Test/evidence | Result |
|---|---|---|
| Instagram Relay posts dedupe and sort by timestamp or numeric `pk` | `scraper.tests.test_instagram_fetch` | PASS |
| Instagram legacy edges and carousel images remain supported | `scraper.tests.test_instagram_fetch` | PASS |
| Facebook Relay records preserve exact price, status, seller, location, and image | `scraper.tests.test_facebook_discovery` | PASS |
| Facebook scheduled discovery defaults to a fresh logged-out context | `scraper.tests.test_facebook_discovery` | PASS |
| Seven Instagram jobs fit in one 600-second ring at 85-second offsets | `scraper.tests.test_scheduler` | PASS |
| Full scraper regression suite | `python -m unittest discover scraper.tests` | 42 PASS |
| New pure embedded parsers | `python -m coverage ...` | 91% branch coverage |
| Static checks | `python -m ruff check scraper` and `python -m py_compile ...` | PASS |
| Instagram live no-state proof | Chrome channel, one account, limit 1 | 12 posts returned; 1 normalized |
| Facebook live no-state proof | Chrome channel, `gpu-rtx`, limit 1 | 24 embedded records; 1 normalized |

RED checkpoints were confirmed before implementation: missing embedded modules, missing anonymous-session decision, old one-hour Instagram cadence, and old Chromium configuration each failed for the intended reason.

Known gap: the Chrome-channel Docker image still needs the normal GitHub Actions build and staging burn-in before this branch can be called production-ready. Do not restore API-first Instagram fetching if staging fails; inspect the Chrome package/runtime first.
