# Reproducible S3 Test Runner

The `s3 test` command reads a manifest, normalizes and sorts its declared
source paths and test names, then executes each test in hosted, native, or
both modes. A manifest records a fixed seed, timeout, optimization level, and
explicit capabilities.

The machine report uses `s3.test-report.v1`. Results are `PASS`, `SKIP`,
`FAIL`, `TIMEOUT`, `CAPABILITY_DENIED`, `RESOURCE_LIMIT`, or
`INFRASTRUCTURE_FAILURE`. Exit status is 0 only for all-pass or explicit-skip
outcomes; ordinary failures and time/resource failures are nonzero, while
runner infrastructure failures use exit status 2.

Hosted execution is the semantic reference. Linux x86-64 native execution is
a differential gate and must agree on the observable integer result. Duration
is recorded for diagnosis but is excluded from deterministic report identity.
