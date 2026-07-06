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
