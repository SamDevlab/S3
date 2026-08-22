# M1.96 Test Evidence

`tests/test_m196_signed_registry_index.py` covers valid canonical trust,
generation monotonicity, key revocation, origin tampering, and provider
failure. The fixture verifier is test-only; no production cryptographic
algorithm is implemented here.
