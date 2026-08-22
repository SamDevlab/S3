# M2.32 Linux x86-64 Conformance V2

`M2_32_LINUX_X86_64=PARTIAL`

The native conformance contract now requires exact hosted/native stdout and
exit-code equality and refuses to promote structural artifacts to runtime
evidence. Focused conformance and prior Linux x86-64 integration tests pass.
No reproducible semantic mismatch is known. A fresh Linux native matrix was
not executed on this Windows host and remains an environment deferment.

- `HOSTED_NATIVE_DIFFERENTIAL=PASS`
- `O0=DEFERRED_BY_ENVIRONMENT`
- `O1=DEFERRED_BY_ENVIRONMENT`
- `SYSV_ABI=DEFERRED_BY_ENVIRONMENT`
- `STRESS_CORPUS=PARTIAL`
