# M2.05 TLS Provider Certification

BASE_SHA=`26795e747f2355df8c09682ab8ca15881a796f63`

FINAL_SHA=`26795e747f2355df8c09682ab8ca15881a796f63`

FILES_CHANGED=none

PRODUCTION_CHANGE=NO

TEST_CHANGE=NO

TLS_CLIENT=PASS_CONTRACT

TLS_SERVER=PASS_CONTRACT

CERT_VALIDATION=PASS_CONTRACT

HOSTNAME_VALIDATION=PASS_CONTRACT

CANCELLATION=PASS_CONTRACT

PROVIDER=DEFERRED_BY_ENVIRONMENT

The focused client, server, cancellation, certificate, and hostname tests
passed. The required vetted `cryptography` provider is not installed on this
host, so provider-backed handshake certification is explicitly deferred and
not promoted to PASS.

T1=PASS_FOCUSED_CONTRACTS

T2=PASS_FOCUSED_TLS_SUBSYSTEM

T3=NOT_RUN

T4=NOT_RUN

BENCHMARKS=NOT_RUN

DEFERMENTS=Vetted TLS provider unavailable.

BLOCKERS=ENVIRONMENT

STATUS=DEFERRED
