# Facebook brand-negation TDD evidence

## User journey

As a RECON user, I want Facebook listings to ignore explicitly negated competitor brands so that the stored brand reflects positive product evidence.

## Evidence

| Guarantee | Test | Result |
| --- | --- | --- |
| The live AMD RX 6800 XT title containing `not intel` resolves to AMD | `FacebookDiscoveryTests.test_brand_extraction_ignores_negated_competitor_mentions` | PASS |
| Indonesian `bukan`/`tanpa` and `non-` negations are ignored | `FacebookDiscoveryTests.test_brand_extraction_ignores_negated_competitor_mentions` | PASS |
| A positive Intel product mention still resolves to Intel | `FacebookDiscoveryTests.test_brand_extraction_keeps_positive_intel_mentions` | PASS |

RED was reproduced before the implementation: the live title returned `Intel` instead of `AMD`.

GREEN verification:

```text
python -m py_compile scraper/facebook/facebook_marketplace.py scraper/tests/test_facebook_discovery.py
python -m ruff check scraper/facebook/facebook_marketplace.py scraper/tests/test_facebook_discovery.py
python -m unittest discover scraper.tests
```

All 61 tests passed. The focused Facebook test file measured 96% coverage. The large Facebook connector module measured 24%; broad live-browser and CLI paths remain an existing coverage gap outside this parser fix.
