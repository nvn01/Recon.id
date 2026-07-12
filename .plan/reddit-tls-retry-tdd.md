# Reddit verified-TLS retry TDD evidence

## User journey

As a RECON operator, I want the Reddit RSS connector to recover from an intermittent staging TLS path failure without ever accepting an invalid certificate.

## Diagnosis

- The real all-connector Debian run ended Reddit with `CERTIFICATE_VERIFY_FAILED` after roughly 60 seconds.
- A bounded TLS-only probe from both the Debian host and the deployed scraper image subsequently verified Reddit's real `*.reddit.com` certificate issued by DigiCert over TLS 1.3.
- The host and container both had populated system CA stores and no proxy environment.
- A single exact RSS request from the deployed image then returned three current normalized listings.
- This isolates the failure to an intermittent transport/TLS path sequence, not a missing CA bundle, permanent Reddit block, or parser failure.

## Guarantees

| Guarantee | Test/evidence | Result |
| --- | --- | --- |
| A transient certificate-verification failure receives a bounded verified retry | `test_fetch_text_retries_tls_verification_error_without_disabling_verification` | PASS |
| A timeout followed by certificate failure gets one extra recovery attempt | `test_fetch_text_gets_one_extra_verified_attempt_after_timeout_then_tls_failure` | PASS |
| A persistently invalid/self-signed certificate is never accepted | `test_fetch_text_never_accepts_a_persistently_invalid_certificate` | PASS |
| Normal RSS parsing still works in the deployed Debian image | Patched no-state three-listing probe | PASS |

## Verification

```text
python -m py_compile scraper/reddit/reddit.py scraper/tests/test_reddit_fetch.py
python -m ruff check scraper/reddit/reddit.py scraper/tests/test_reddit_fetch.py
python -m unittest discover scraper.tests
```

All 65 tests passed. The focused Reddit test file measured 97% coverage. The monolithic Reddit connector module measured 16%; unexecuted CLI, parser, state, and network branches remain an existing coverage gap outside this transport fix.

The patch does not create an unverified SSL context, disable hostname checks, install a custom CA, rotate proxies, or retry HTTP 429 beyond the existing configured limit.
