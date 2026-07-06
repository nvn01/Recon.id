# Reddit Data Collection Notes

Scope: this folder is only for the Reddit collector for RECON. Keep it focused on public seller/listing posts for computer, PC, tech, and gaming peripheral products.

Current proof script:

```powershell
python "scraper\reddit\reddit_latest.py" --limit 5
```

Important context:

- Target source is `r/jualbeliindonesia`.
- Current target flair is `WTS: Computers & Peripherals`.
- Direct Reddit JSON endpoints returned `403` during probing. The working path is Reddit search RSS/Atom with `sort=new`.
- The RSS body exposes the post description, not just the title.
- Keep a polite `User-Agent`, retry on `429`, and avoid aggressive polling.
- Do not add database/export behavior here unless the user asks for it. This is still a starter collector.
- Future orchestration should call this script/module separately from Instagram and Facebook.
