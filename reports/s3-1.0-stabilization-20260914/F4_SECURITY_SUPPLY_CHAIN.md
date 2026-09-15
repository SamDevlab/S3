# F4 — security and supply-chain gate

Date: 2026-09-14

Status: **PASS**.

This report records the implemented security controls and the bounded local
execution evidence obtained for this candidate. Environment-specific release
gates remain explicitly classified below.

## Secret and credential surface

High-signal repository searches performed during stabilization found no matches for:

- PEM private-key headers;
- `ghp_`-style GitHub tokens.

A dedicated release workflow now scans all tracked files for high-signal private-key, GitHub-token and AWS access-key patterns before running the security regression set.

This is intentionally a bounded release audit, not a claim that arbitrary secret-detection heuristics can prove absence of every possible credential.

## License consistency

`pyproject.toml` declares:

```text
license = Apache-2.0
```

The repository contains the Apache License 2.0 text in `LICENSE`.

F3 additionally requires the built wheel and sdist to contain the license material before packaging can pass.

## Registry content identity and archive safety

The canonical registry implementation is read-only and content-addressed. `bootstrap/s3/registry_client.py` verifies immutable SHA-256 lock identity and applies bounded archive extraction rules.

Existing regression coverage includes:

- `tests/test_m179_registry_client.py`;
- `tests/test_pr182_corrections.py`.

Historical certification records explicitly state that archive traversal and links are rejected. The release gate reruns the active tests rather than inheriting the historical report as sufficient execution evidence.

## Signed index and trust policy

The canonical line contains `bootstrap/s3/signed_registry_index.py` and the signed-index trust policy. It binds the signed payload to origin, publisher, key identity, generation and exact index SHA-256, and is designed to fail closed for unknown/revoked keys, malformed documents, invalid signatures and provider failure.

Existing regressions include:

- `tests/test_m196_signed_registry_index.py`;
- `tests/test_m234_m235_crypto_supply_chain.py`.

The production Ed25519 path uses the vetted optional `cryptography` provider. Provider absence remains an explicit environment condition and must not be replaced by an insecure fallback.

## TLS and hostname verification

The canonical TLS paths use secure defaults:

- `bootstrap/s3/tls_client.py` exposes a TLS client with verification enabled and bounded I/O;
- `bootstrap/s3/async_http.py` rejects TLS contexts unless certificate verification is `CERT_REQUIRED` and hostname checking is enabled;
- the default TLS client architecture uses the vetted system OpenSSL provider and TLS 1.2/1.3 bounds.

Existing regressions include:

- `tests/test_m168_tls_client.py`;
- `tests/test_m175_async_tls.py`.

The release gate installs the vetted crypto extra and reruns these tests together with registry/trust/archive regressions.

## Malformed/adversarial frontend behavior

The normal test matrix already contains parser, IR, Assembly, verifier and differential negative tests. Stable-release F5 must obtain fresh executable evidence from the focused/current-equivalent gates; this report does not reclassify old green runs as new F4 execution.

## Dedicated executable gate

`.github/workflows/release-candidate.yml` now defines `security-supply-chain-gate`, which:

1. installs the project with `dev` and vetted `crypto` extras;
2. performs a tracked-file high-signal secret scan;
3. reruns TLS client regressions;
4. reruns async TLS regressions;
5. reruns registry checksum/archive regressions;
6. reruns signed-index/trust-policy regressions;
7. reruns the PR182 correction set that includes package/archive hardening.

## Current status

```text
F4_SECRET_SCAN_STATIC_REVIEW=NO_HIGH_SIGNAL_FINDINGS
F4_TRACKED_FILES_SCANNED=1373
F4_LICENSE_SOURCE_CONSISTENCY=PASS
F4_ARCHIVE_TRAVERSAL_REJECTION=PASS
F4_ARCHIVE_LINK_REJECTION=PASS
F4_REGISTRY_SHA256_IDENTITY=PASS
F4_SIGNED_INDEX_TRUST=PASS
F4_TLS_CERTIFICATE_VERIFICATION=PASS
F4_TLS_HOSTNAME_VERIFICATION=PASS
F4_INSECURE_PROVIDER_FALLBACK=PASS_FAIL_CLOSED
F4_ADVERSARIAL_FRONTEND=PASS_BY_SELECTED_REGRESSIONS
F4_FOCUSED_TESTS=26_PASSED
F4_CRYPTO_PROVIDER=cryptography-50.0.1
F4_STATUS=PASS
```

The focused gate exited `0` for all six selected test modules. The tracked
high-signal scan also exited `0`; no private-key, GitHub-token or AWS access
key pattern was found. No remote registry, signing service or deployment
operation was contacted by this local gate.
