# Facebook category-feed TDD evidence

## User journey

As a RECON user, I want Facebook discovery to use localized Marketplace category feeds so that collection is simpler and always requests the newest Jakarta-area listings within 500 km.

## Guarantees

| Guarantee | Evidence | Result |
| --- | --- | --- |
| Category-only targets do not require a search query | `test_category_target_builds_localized_newest_first_url_without_search_query` | PASS |
| URLs use `/marketplace/jakarta/<category>/` with newest sorting and 500 km radius | Focused unit test and Debian calibration | PASS |
| The committed target set contains only the three requested categories | `test_committed_targets_are_the_three_requested_jakarta_categories` | PASS |
| Legacy query targets remain supported | Full scraper unit suite | PASS |

RED evidence:

- Category-only target loading failed with `source target #1 is missing query`.
- The committed configuration exposed twenty query targets instead of the three requested category targets.

GREEN verification:

```text
python -m json.tool scraper/facebook/source_targets.json
python -m unittest discover scraper.tests
python -m ruff check scraper/facebook/facebook_marketplace.py scraper/tests/test_facebook_discovery.py
```

All 63 tests passed. A no-state Debian calibration using the patched files fetched embedded Relay data from all three category feeds: 24 phone-accessory candidates, 24 video-game candidates, and 24 computer candidates. The existing RECON relevance filter selected zero phone-accessory cards, eight gaming cards, and ten of twenty-one relevant computer cards.
