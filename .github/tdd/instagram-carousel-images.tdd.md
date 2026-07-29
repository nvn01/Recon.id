# Instagram Carousel Image Recovery - TDD Evidence

## Source

The user reported that nearly every recent Instagram listing exposed only one
image even when its source post was a carousel. The journey and acceptance
criteria were derived from that production defect.

## User journeys

- As a RECON visitor, I want every available Instagram carousel image so I can
  inspect the complete listing without leaving the feed.
- As a scraper operator, I want carousel enrichment bounded and cached so the
  fix does not multiply Instagram traffic on every scheduler cycle.
- As an operator, I want a dry-run-first backfill so affected historical rows
  can be corrected without replacing already cached cover images.

## Task report

### Collector enrichment

- RED: `python -m unittest scraper.tests.test_instagram_fetch` failed with
  `ImportError` because post-detail parsing and carousel enrichment did not
  exist.
- GREEN: the same target passed 16 tests after adding detail extraction,
  bounded fetching, persisted image-set reuse, and cover fallback.
- Live structural evidence: a logged-out profile payload marked
  `carousel_media_count` but omitted children, while its individual post page
  exposed the complete `carousel_media` array.

### Historical backfill

- RED: `python -m unittest scraper.tests.test_instagram_carousel_backfill`
  failed because no carousel backfill module existed.
- GREEN: the backfill tests verify dry-run behavior, explicit write behavior,
  ordered child insertion, exact-shortcode validation, and preservation of
  position zero.

### Rotating CDN paths

- RED: the live smoke found five normalized images for a four-image post
  because the profile and detail page used different CDN paths for the same
  cover.
- GREEN: the regression test now requires the ordered detail-page media set to
  replace the profile cover set, producing one cover plus its children without
  duplication.

## Test specification

| Guarantee | Test target | Type | Result |
| --- | --- | --- | --- |
| Individual post JSON yields every ordered carousel child | `test_post_detail_parser_extracts_complete_carousel_media` | Unit | PASS |
| Only detected carousels trigger bounded detail reads | `test_carousel_enrichment_fetches_detail_once_and_populates_cache` | Unit | PASS |
| Persisted image sets prevent repeated post-page reads | `test_carousel_enrichment_reuses_cache_without_another_detail_request` | Unit | PASS |
| Rotated profile/detail cover paths do not duplicate the cover | `test_carousel_enrichment_does_not_duplicate_rotated_profile_cover` | Regression | PASS |
| Backfill is read-only unless writes are explicitly enabled | `test_run_backfill_is_dry_run_by_default_and_reports_discovered_children` | Unit | PASS |
| Backfill inserts only missing child positions | `test_run_backfill_inserts_only_discovered_children_when_enabled` | Unit | PASS |

## Final verification

- `python -m unittest discover -s scraper/tests -p "test_*.py"`: 130 tests
  passed before the final documentation-only update.
- `python -m ruff check ...`: passed.
- `python -m compileall -q scraper`: passed.
- `docker compose config --quiet`: passed.
- Targeted coverage: embedded Instagram parser 95%; repository-selected
  Instagram/orchestrator modules 64% overall. The remaining gap is concentrated
  in external Playwright/database CLI boundaries. Those boundaries received
  controlled live structural probes and mocked write-path tests rather than
  unbounded automated source requests.

## Merge evidence

RED and GREEN checkpoints are preserved as separate conventional commits in the
current task history. The pre-existing README modification was not staged.
