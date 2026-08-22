# M2.06 Signed Registry End-to-End

BASE_SHA=`8b56bdf30a5b55dfbd1225ef4adcfac60b84bfe1`

FINAL_SHA=`8b56bdf30a5b55dfbd1225ef4adcfac60b84bfe1`

FILES_CHANGED=none

PRODUCTION_CHANGE=NO

TEST_CHANGE=NO

SIGNED_INDEX=PASS_CONTRACT

ED25519=DEFERRED_BY_ENVIRONMENT

CONTENT_HASH=PASS

TAMPER_REJECTION=PASS_CONTRACT

TRUST_ROOT=PASS_CONTRACT

OFFLINE_CACHE=PASS_CONTRACT

RESOLUTION_REPRODUCIBILITY=PASS_CONTRACT

The focused registry, signed-index, digest, trust-root, tamper, cache, and
resolution tests passed. The production Ed25519 path intentionally requires
the vetted `cryptography` provider, which is unavailable on this host.
Therefore the complete signed registry E2E result remains deferred; policy
and fail-closed contract evidence is not promoted to provider-backed PASS.

T1=PASS_FOCUSED_CONTRACTS

T2=PASS_FOCUSED_REGISTRY_SUBSYSTEM

T3=NOT_RUN

T4=NOT_RUN

BENCHMARKS=NOT_RUN

DEFERMENTS=Ed25519 provider unavailable.

BLOCKERS=ENVIRONMENT

STATUS=DEFERRED
