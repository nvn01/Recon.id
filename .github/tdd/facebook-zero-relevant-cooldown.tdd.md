# Facebook Zero-Relevant Cooldown TDD Evidence

## Incident

The continuous staging scheduler parsed 24 cards from the Facebook cell-phone-accessories category, filtered all of them as unrelated/noisy, then raised `ConnectorBlockedError`. That global cooldown prevented the following video-games and computers jobs from fetching.

## Guarantees

| Guarantee | Test | Result |
|---|---|---|
| A parsed candidate page with zero relevant cards is healthy `no_new_data` | `test_candidate_page_with_zero_relevant_cards_is_valid_no_new_data` | PASS |
| A page with zero Marketplace candidates still fails closed | `test_page_without_any_marketplace_candidates_remains_blocked` | PASS |
| Successful empty access clears an older cooldown and error | `test_zero_relevant_result_clears_prior_cooldown_as_successful_access` | PASS |
| Facebook cooldown skips remain visible through the orchestrator | `test_facebook_cooldown_status_survives_orchestrator_summary` | PASS |
| Staging Dell Latitude and Acer Aspire rows stay Laptop despite CPU/GPU terms | `test_staging_laptop_families_beat_component_terms` | PASS |
| A complete staging PC beats component-level RAM/CPU terms | `test_staging_complete_pc_beats_ram_and_cpu_terms` | PASS |

## RED evidence

- `collect_target_cards` did not exist, so the candidate/no-candidate distinction could not be represented.
- `run_facebook` discarded connector-local cooldown status and reported empty cooldown runs as ordinary `no_new_data`.

## GREEN evidence

- `python -m unittest discover scraper.tests` — 83 tests passed.
- `python -m ruff check scraper` — passed.
- `python -m compileall -q scraper` — passed.
- Isolated Debian staging phone-accessories probe: 24 cards parsed, 19 irrelevant and 5 blocked, exit 0 with `no_new_data`; temporary state recorded `cooldown_until: null`.
- An immediately following Debian staging computers probe using the same temporary state parsed 24 cards and normalized/validated 3 listings, exit 0 with `success`.

The exact local patch files were checksum-verified after copying to `/tmp` and bind-mounted read-only over `novn01/recon-scraper:stagging`. The probes used isolated temporary state/log directories and omitted `--write-db`. The continuous scraper container and its persistent volumes were not restarted or modified; the temporary patch directory was removed afterward.
