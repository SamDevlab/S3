# F4 — security and supply-chain gate

Date: 2026-09-14

Status: **STRUCTURAL AUDIT COMPLETE / EXECUTION EVIDENCE PENDING**.

This report records what is already implemented in the canonical line and what still requires an executable test environment before stable-release closure.

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
F4_LICENSE_SOURCE_CONSISTENCY=PASS_STATIC
F4_ARCHIVE_TRAVERSAL_REJECTION=IMPLEMENTED_TEST_EXECUTION_PENDING
F4_ARCHIVE_LINK_REJECTION=IMPLEMENTED_TEST_EXECUTION_PENDING
F4_REGISTRY_SHA256_IDENTITY=IMPLEMENTED_TEST_EXECUTION_PENDING
F4_SIGNED_INDEX_TRUST=IMPLEMENTED_TEST_EXECUTION_PENDING
F4_TLS_CERTIFICATE_VERIFICATION=IMPLEMENTED_TEST_EXECUTION_PENDING
F4_TLS_HOSTNAME_VERIFICATION=IMPLEMENTED_TEST_EXECUTION_PENDING
F4_INSECURE_PROVIDER_FALLBACK=NOT_ALLOWED_BY_CONTRACT_TEST_EXECUTION_PENDING
F4_ADVERSARIAL_FRONTEND=F5_EXECUTION_PENDING
F4_STATUS=OPEN_PENDING_EXECUTABLE_RUNNER
```

No security gate is considered green merely because the code or an older report exists.
