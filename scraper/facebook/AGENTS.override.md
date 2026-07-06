# Facebook Marketplace Data Collection Notes

Scope: this folder is only for Facebook Marketplace collection for RECON. Keep it focused on public Marketplace listings for computer, PC, tech, and gaming peripheral products.

Current proof script:

```powershell
python "scraper\facebook\facebook_marketplace.py" --query vga --limit 5
python "scraper\facebook\facebook_marketplace.py" --query vga --limit 5 --details
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
- Broad Electronics search is noisy. Focused queries such as `vga`, plus RECON keyword filtering, produce better samples.
- `vga` can also match unrelated products such as Yamaha Vega parts, so keep the relevance filter in place and tune keywords carefully.
- Do not message sellers, submit forms, or perform any account-side action from the scraper.
