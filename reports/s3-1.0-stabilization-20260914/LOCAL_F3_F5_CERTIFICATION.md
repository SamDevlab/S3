# Local F3-F5 certification

Date: 2026-09-14

This is the bounded local execution record for the 1.0 release candidate.
It does not authorize candidate freeze, final lineage T4, publication,
tagging or release.

```text
F3=PASS
F4=PASS
F5_HOST_INDEPENDENT=PASS
F5_LINUX_X86_64_NATIVE=DEFERRED_ENVIRONMENT_UNAVAILABLE
F5_NORMAL_MATRIX=DEFERRED_CI_RUNNER_UNAVAILABLE
COMPILEALL=PASS
DIFF_CHECK=PASS
```

## F3 package evidence

Python `3.13.15` built the candidate twice with
`SOURCE_DATE_EPOCH=1700000000`. The final wheel and sdist pairs were both
byte-identical:

```text
WHEEL=s3_bootstrap-1.0.0-py3-none-any.whl
WHEEL_BYTES=437037
WHEEL_SHA256=3b8490c30a09eaa594920462f8c9c9e7267bc270e92ca79e635f593d2ee83d76
SDIST=s3_bootstrap-1.0.0.tar.gz
SDIST_BYTES=695713
SDIST_SHA256=f295a899d147f7170f4143fb5fa30b9c42b70db10a2d45d60f3a85a34c9f7ae8
WHEEL_BYTE_IDENTITY=PASS
SDIST_BYTE_IDENTITY=PASS
```

Both distributions had the expected metadata (`s3-bootstrap`, `1.0.0`),
the Apache-2.0 license, and safe inventories. A clean Python environment
installed the wheel and all CLI/example smokes exited zero.

## F4 security evidence

The tracked-file scan examined 1,373 files and found no high-signal private
key, GitHub token or AWS access-key pattern. The six selected TLS, registry,
archive, signed-index, crypto-provider and PR182 correction modules passed:
`26 passed`, exit `0`. The vetted `cryptography 50.0.1` provider was
available; no insecure fallback was used.

## F5 focused evidence

The required five modules passed: `57 passed`, exit `0`. The host is Windows
11 AMD64 and has no `gcc`, `clang` or `ld`, so Linux x86-64 native evidence
remains explicitly deferred. The broad normal matrix also remains deferred
because the configured GitHub Actions runner did not allocate.

```text
FINAL_T4=NOT_RUN
FINAL_T4_AUTHORIZED=NO
TAG=NO
RELEASE=NO
PYPI=NO
```
