# M2.31-M2.40 Release Candidate Mega-Review

## Scope

The review covers the release surface, ownership and async contracts, parser
and semantic boundaries, modules, incremental compilation, IR/SSA/optimizer,
native target classification, FFI, runtime/network protocols, TLS and signed
registry boundaries, workspace and developer tooling, reproducibility, test
infrastructure, and benchmark evidence.

## Findings

- Critical: `0`
- High: `0`
- Medium: `0` unresolved release-blocking correctness/security findings
- Low: environment and capability deferments documented in milestone reports

The M2.39 adversarial campaign found one concrete availability defect in lexer
indentation handling for a NUL byte at line start. It was corrected in
`e202bc9`, and the bounded adversarial, parser, LSP, HTTP/2, registry, and
toolchain tests pass afterward.

## Accepted Deferments

- Fresh Linux x86-64 native conformance is validated in the Linux snapshot for
  the focused matrix; broader native production corpus remains bounded.
- AArch64 and macOS ARM64 runtime execution are not available on this host;
  structural evidence is not promoted to runtime PASS.
- Ed25519 vetted provider execution is unavailable because `cryptography` is
  absent; the signed-registry gate fails closed.
- External benchmark P2-P18 workloads are not present in the benchmark
  repository. P1 correctness and M1.99 hosted characterization are recorded
  without a native speedup claim.
- Full-lineage T4 is intentionally not run before M2.40.

## Gate

`UNRESOLVED_CRITICAL=0`

`UNRESOLVED_HIGH=0`

`MEGA_REVIEW=PASS_WITH_DOCUMENTED_DEFERMENTS`
