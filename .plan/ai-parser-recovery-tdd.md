# AI Parser Recovery TDD Evidence

## Source

Journeys and acceptance criteria were derived from the 2026-07-15 staging
audit of the AI-only scraper. No external implementation plan was supplied.

## User journeys

- As the scraper operator, I want NVIDIA capacity and invalid-output failures
  to stop duplicate requests so the shared endpoint can recover.
- As the scraper operator, I want semantic parsing to remain AI-only and fail
  closed so incomplete locally guessed listings never reach PostgreSQL.
- As the scraper operator, I want Instagram login redirects and configured
  post limits handled per account so one blocked profile does not increase
  access pressure for the remaining profiles.

## Task evidence

| Guarantee | Test or command | Type | Result | Evidence |
|---|---|---|---|---|
| Non-JSON and capacity failures do not immediately retry without guidance | `python -m unittest scraper.tests.test_nvidia_parser scraper.tests.test_instagram_fetch scraper.tests.test_runtime_guardrails` | Unit | RED then PASS | RED: 2 failures and 5 errors; GREEN: 43 tests passed |
| Only explicit guided-JSON incompatibility gets one unguided retry | `test_guided_json_rejection_retries_once_without_guidance` | Unit | PASS | Two calls; first payload contains `nvext`, second does not |
| Capacity failure and two invalid outputs open a shared five-minute circuit | `test_capacity_failure_opens_shared_circuit_before_next_request`, `test_two_invalid_outputs_open_shared_circuit` | Unit | PASS | A subsequent client using the same state file makes no request |
| Instagram collection obeys the requested limit | `test_account_collection_obeys_requested_limit` | Unit | PASS | Five discovered posts with limit 2 produce two candidates |
| Instagram login redirects create account-scoped cooldown without a fake HTTP status | `test_login_redirect_is_marked_as_cooldown_eligible`, `test_instagram_login_redirect_uses_account_cooldown_without_fake_http_status` | Unit/integration | PASS | Second account run returns `cooldown_skip` without invoking the collector |
| Full scraper suite remains green | `python -m unittest discover scraper.tests` | Unit/integration | PASS | 89 tests passed |
| Python style and syntax remain valid | `python -m ruff check scraper`; `python -m py_compile ...` | Static | PASS | No findings |
| Root application gates remain green | `npm run check`; `npx prisma validate`; `npm run build` | Static/build | PASS | ESLint, TypeScript, Prisma, and Next production build passed |
| Recovery works in the Debian container runtime | isolated bind-mounted staging probe | Staging integration | PASS | Circuit made 1 then 0 requests; login redirect was cooldown eligible; one live NVIDIA item returned valid title, category, and price |

## Coverage and gaps

`python -m coverage run --source=scraper -m unittest discover scraper.tests`
passed all 89 tests. The three broad touched modules report 61% aggregate line
coverage because existing browser, network, and orchestration branches remain
outside unit coverage. The new circuit, fallback, limit, and redirect paths are
directly exercised. No tests were skipped. Live Instagram navigation was not
repeated because the change handles an already-observed redirect and additional
anonymous requests would increase platform-access pressure.

## Commit evidence

- RED checkpoint: `2271236 test(scraper): reproduce AI overload failures`
- GREEN checkpoint: `f8855eb fix(scraper): back off unstable AI parsing`

## NVIDIA function lifecycle follow-up

The 2026-07-15 staging audit later captured two additional NVIDIA Cloud
Functions availability responses: HTTP 400 with `DEGRADED function cannot be
invoked`, followed by a function-ID-specific HTTP 404. NVIDIA's lifecycle
documentation states that a `DEGRADED` function has no active instances and
cannot receive invocations. The implementation therefore treats only those
specific provider-function response shapes as shared circuit triggers; generic
client-side HTTP 400 errors remain uncircuited.

Documentation:

- <https://docs.nvidia.com/nvcf/function-lifecycle>
- <https://docs.nvidia.com/nvcf/dev/generic-http-function-invocation>

| Guarantee | Test or command | Result | Evidence |
|---|---|---|---|
| A `DEGRADED function cannot be invoked` response opens the shared five-minute circuit after one request | `test_degraded_function_failure_opens_shared_circuit_before_next_request` | RED then PASS | RED: second client reached `_request`; GREEN: second client was blocked before `_request` |
| The observed function-ID `not found` response opens the same circuit | `test_function_not_found_failure_opens_shared_circuit_before_next_request` | RED then PASS | Same cross-client state-file guarantee as the degraded response |
| Unrelated HTTP 400 responses do not get mislabeled as provider outages | `test_generic_bad_request_does_not_open_provider_unavailable_circuit` | PASS | Second client made its normal request and returned a valid result |
| Full scraper suite remains green | `python -m unittest discover scraper.tests` | PASS | 92 tests passed |
| Python style and syntax remain valid | `python -m ruff check scraper`; `python -m py_compile ...` | PASS | No findings |
| Both production error shapes work inside the Debian scraper image | isolated bind-mounted staging probe | PASS | Each case made one initial request, opened `provider_unavailable`, and blocked the second request with zero API calls |

Focused coverage for the broad `nvidia_parser.py` module is 64%; all newly
added classifier branches and circuit behavior are directly exercised. The
remaining uncovered lines are existing HTTP, prompt, merge, normalization, and
environment-loading paths outside this follow-up.

- RED checkpoint: `f2adebe test(scraper): reproduce NVIDIA function outage flood`
- GREEN checkpoint: `72e9971 fix(scraper): back off unavailable NVIDIA functions`
