# M2.34 TLS and Ed25519 Provider Closure

`M2_34_CRYPTO_PROVIDER=DEFERRED_BY_ENVIRONMENT`

The host reports `OpenSSL 3.0.13 30 Jan 2024` for TLS. No `cryptography`
Ed25519 provider is installed, so vetted Ed25519 runtime verification is
deferred. No custom cryptography was added. Provider discovery is deterministic
and the fail-closed vetted-provider gate is covered by focused tests.

- `TLS_PROVIDER=OpenSSL 3.0.13 30 Jan 2024`
- `TLS_CLIENT=PASS_FOR_EXISTING_FIXTURE_CONTRACT`
- `TLS_SERVER=PASS_FOR_EXISTING_FIXTURE_CONTRACT`
- `CERT_VALIDATION=PASS_FOR_EXISTING_FIXTURE_CONTRACT`
- `HOSTNAME_VALIDATION=PASS_FOR_EXISTING_FIXTURE_CONTRACT`
- `ED25519_PROVIDER=unavailable`
- `ED25519_VALIDATION=DEFERRED_BY_ENVIRONMENT`
