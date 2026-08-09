# Instagram title guard TDD evidence

## Source and journey

No plan file was provided. The journey was derived from production evidence:
as a RECON visitor, I should see a meaningful Instagram product title rather
than the post shortcode, and incomplete AI output must remain retryable instead
of reaching PostgreSQL.

## Task report

| Guarantee | Test or command | Type | Result | Evidence |
|---|---|---|---|---|
| The prompt forbids Instagram shortcode titles | `test_prompt_forbids_instagram_shortcode_titles` | Unit | PASS | Failed before the prompt rule; passed after it was added |
| Accepted Instagram output whose title equals `externalId` is rejected | `test_instagram_ai_result_rejects_shortcode_title` | Unit | PASS | Failed because batch validation accepted it; passed after semantic validation |
| A blank AI title cannot fall back to the raw shortcode | `test_instagram_merge_rejects_blank_title_instead_of_using_shortcode` | Unit | PASS | Failed because merge preserved the raw title; passed after the merge guard |
| Invalid Instagram titles participate in the existing invalid-output circuit | `test_invalid_instagram_title_counts_as_invalid_model_output` | Unit | PASS | Failed as `other`; passed as `invalid_output` |
| Existing scraper behavior remains intact | `python -m unittest discover scraper.tests` | Regression | PASS | 159 tests passed |
| Python lint remains clean | `python -m ruff check scraper` | Static | PASS | All checks passed |

## RED and GREEN checkpoints

- RED: `b2227c5 test(scraper): reproduce Instagram shortcode titles`
- RED classification: `44263aa test(scraper): classify invalid Instagram titles`
- GREEN: `2a06c04 fix(scraper): reject Instagram shortcode titles`

## Coverage and known gaps

`python -m coverage run --source=scraper -m unittest discover scraper.tests`
followed by a report for `scraper/reddit/nvidia_parser.py` measured 67% module
coverage. The four changed behaviors above are directly covered, but the large
pre-existing provider client module remains below the preferred 80% target.

A read-only production query found 19 existing Instagram rows whose title
equals `external_id`. This code prevents future writes after deployment; it
does not mutate or requeue those historical rows. Repairing them requires a
separately approved production operation after the fixed image is validated.
