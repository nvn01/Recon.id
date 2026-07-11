# Instagram Debian Playwright TDD Evidence

## User journey

As the RECON operator, I want public Instagram discovery to run unattended on the Debian scraper image without an Instagram login, so that staging can collect recent posts using the same normal Chrome rendering path that succeeded during logged-out inspection.

## RED evidence

Command:

```text
python -m unittest scraper.tests.test_instagram_fetch scraper.tests.test_runtime_guardrails scraper.tests.test_scheduler
```

Expected failures were confirmed before production edits:

- `capture_timeline_response` did not exist.
- `resolve_instagram_headless` did not exist.
- production Instagram config had no headed browser mode.
- scraper Dockerfile had no Xvfb entrypoint.

Checkpoint: `e7095b4 test(instagram): define Debian browser discovery runtime`

## GREEN evidence

Focused command:

```text
python -m unittest scraper.tests.test_instagram_fetch scraper.tests.test_runtime_guardrails scraper.tests.test_scheduler
```

Result: 37 tests passed.

Full scraper command:

```text
python -m coverage run --branch -m unittest discover scraper.tests
python -m coverage report -m
```

Result: 57 tests passed. Changed test modules reported 97-98% coverage and `scraper/instagram/embedded.py` reported 94%. Repository-wide coverage remains 43% because the pre-existing Facebook, Reddit, and connector integration surfaces are not comprehensively exercised by the current unit suite.

Checkpoint: `fcbc561 fix(instagram): run browser discovery under Xvfb`

## Guarantees

| Guarantee | Evidence | Result |
|---|---|---|
| Debian scraper commands run inside an Xvfb virtual display | `test_scraper_image_runs_commands_inside_virtual_display` | PASS |
| Production Instagram defaults to headed Chrome while retaining a headless A/B override | runtime/config tests | PASS |
| Timeline JSON is accepted by supported response shape rather than rotating document ID | `test_timeline_response_capture_accepts_shape_not_document_id` | PASS |
| Cross-origin and unrelated JSON are rejected | `test_timeline_response_capture_rejects_unrelated_or_cross_origin_json` | PASS |
| Embedded and network posts merge complementary fields without losing caption, timestamp, image, or media metadata | `test_embedded_and_network_posts_merge_complementary_fields_by_shortcode` | PASS |
| Existing account-scoped Instagram cooldown behavior is preserved | `test_instagram_block_cooldown_is_account_scoped` | PASS |

## Additional verification

- Ruff: passed.
- Python bytecode compilation: passed.
- Prisma validation: passed.
- `npm run check`: passed.
- `npm run build`: passed.
- Local, staging, and production Compose rendering: passed with non-secret verification image tags for production interpolation.
- Changed-file credential-pattern scan: no findings.
- Local Dockerfile build check: not executed because the Docker Desktop Linux engine was unavailable; GitHub Actions remains the image-build gate.

## Debian PID 1 hotfix

The first deployed Xvfb image exposed a container-only startup failure: when
`xvfb-run` was PID 1, it remained blocked waiting for Xvfb's readiness signal
and never launched Python. Two staging runs stayed alive with empty logs and an
empty database.

The staging image itself proved the fix with Docker's init shim:

```text
docker run --rm --init novn01/recon-scraper:stagging python -V
Python 3.12.13
```

The permanent image now installs `tini` and starts
`tini -- xvfb-run ...`, preserving the virtual display while ensuring
`xvfb-run` is not PID 1. The Dockerfile regression test requires that exact
entrypoint order. Local, staging, and production Compose files also set
`init: true` as a runtime-level safeguard for older scraper images.
