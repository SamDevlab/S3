# S3 1.1.0 — Reliability & Maintenance

S3 1.1.0 is the release candidate for the reliability and maintenance track
following the stable v1.0.0 toolchain line. Publication remains a separate
explicit decision.

## Technical scope

- **R0:** frozen deterministic reliability contracts.
- **R1:** killable isolated execution with a hard watchdog.
- **R2:** deterministic valid and malformed source generation.
- **R3:** hosted/native differential campaigns and replay evidence.
- **R4:** deterministic minimization, exact failure-signature preservation,
  deduplication, and canonical triage reports.
- **R5:** bounded clean maintenance closure.

Evidence retained by the track includes the hardened R3 campaign at
`128/128 PASS` with a 16-case Linux native shard, and the R5 campaign at
`256/256 PASS` with a 32-case Linux native shard. These are separate campaign
results and are not presented as a fresh v1.0.0 T4.

## Boundaries

This release candidate does not expand language syntax or compiler semantics,
add a backend, or widen platform-support claims. The Python implementation
remains the reference compiler, and full self-hosting remains deferred. PyPI
publication is a separate operation. GitHub Actions runner provisioning debt,
if still unresolved, remains tracked under issue #284 and is not hidden by
weakening workflows or correctness gates.

The existing v1.0.0 tag and release remain immutable. The candidate package
version is `1.1.0`; language syntax, IR, Assembly, diagnostic, and reliability
protocol versions retain their established contracts.
