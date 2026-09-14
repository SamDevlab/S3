# F2 — stable 1.0 support and claim matrix

Date: 2026-09-14

This matrix separates implementation presence from release certification. Structural evidence is never promoted to runtime support.

| Surface | Stable 1.0 claim | Classification |
|---|---|---|
| Python reference compiler | Default/reference implementation for compilation and hosted execution | `SUPPORTED_DEFAULT` |
| Source syntax | V0.6 default; V0.5 remains explicit legacy mode where still documented | `SUPPORTED` |
| IR / Assembly | IR JSON 0.6.0 and S3 Assembly 0.6.0 | `SUPPORTED_VERSIONED` |
| Hosted emulator | Reference execution path covered by the canonical test lineage | `SUPPORTED` |
| Linux x86-64 native | Native generation/execution only within the certified System V AMD64 / Linux contract | `SUPPORTED_CERTIFIED_SCOPE` |
| Windows hosted compiler | Python-hosted toolchain claim only where normal Python/CLI evidence applies | `SUPPORTED_HOSTED_SCOPE` |
| Windows x86-64 native / PE | Do not advertise beyond the explicitly tested backend/toolchain-probe evidence | `BOUNDED_NO_BROAD_RUNTIME_CLAIM` |
| Linux AArch64 | Structural/backend integration evidence may exist; runtime certification remains environment-dependent/deferred unless fresh release evidence proves otherwise | `STRUCTURAL_RUNTIME_DEFERRED` |
| macOS ARM64 | No broad runtime certification from the current release evidence | `RUNTIME_DEFERRED` |
| WASM32/WASI | Structural artifact contract only where documented; no implicit runtime certification | `STRUCTURAL_ONLY` |
| FFI | Only the bounded, explicitly documented FFI surface | `SUPPORTED_BOUNDED` |
| HTTP/network | Only documented protocol/capability boundaries; no claim beyond current implementation/certification | `SUPPORTED_BOUNDED` |
| TLS | Secure provider boundary only; no insecure fallback | `FAIL_CLOSED_PROVIDER_BOUNDARY` |
| Ed25519 / signed registry | Vetted-provider execution where available; provider-unavailable paths remain explicit deferments | `FAIL_CLOSED_PROVIDER_BOUNDARY` |
| Package registry / supply chain | Deterministic identity/checksum/trust contracts within documented scope | `SUPPORTED_BOUNDED` |
| Benchmark performance | Correctness evidence plus characterization unless a protocol-equivalent native comparison is explicitly certified | `CHARACTERIZATION_ONLY` |
| Full compiler self-hosting | Separate research frontier; Python remains reference/default | `DEFERRED_NON_BLOCKING` |
| M2.41+ / Gen3 trains | Not part of the canonical stable 1.0 release line unless separately promoted | `EXCLUDED_FROM_1_0` |

## Release wording rules

Stable 1.0 documentation must use the following rules:

1. say **implemented** when only implementation evidence exists;
2. say **structurally validated** for non-executed target artifacts;
3. say **runtime certified** only when the target actually executed under the recorded release evidence;
4. preserve provider/environment deferments verbatim rather than converting them into PASS;
5. never describe the self-host research line as the default compiler;
6. never use benchmark characterization as a native speedup claim.

## Reference compiler status

```text
REFERENCE_COMPILER=PYTHON
DEFAULT_COMPILER=PYTHON
FULL_SELFHOST_DEFAULT=NO
FULL_SELFHOST_RELEASE_BLOCKER=NO
```

The stable package name remains `s3-bootstrap`; the `1.0.0` distribution-version change does not alter this architecture.

## F2 status

```text
F2_SUPPORT_CLAIM_MATRIX=PASS
F2_STRUCTURAL_RUNTIME_DISTINCTION=EXPLICIT
F2_PROVIDER_DEFERMENTS_PRESERVED=YES
F2_PERFORMANCE_OVERCLAIM=NO
F2_SELFHOST_OVERCLAIM=NO
F2_EXPERIMENTAL_TRAIN_PROMOTION=NO
```

F2 is complete as a release-claim policy. Fresh F5/F6 certification may narrow or strengthen individual rows, but may not silently broaden them.
