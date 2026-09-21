# Self-host scientific-kernel capability reuse audit

Date: 2026-09-20
Production base: `db0f6b1533938c925daa603209d76d94bbe72485`
Campaign: `SCIENTIFIC_KERNEL_0_1`

This audit is the pre-implementation decision record required before adding
any new scientific value representation or math primitive. It is based on the
production source at the base above and the focused evidence recorded by PR
#308. It does not claim native Linux qualification where that path was not
executed.

## Matrix

| Capability | Classification | Evidence / boundary |
| --- | --- | --- |
| f64 scalar arithmetic | REUSE_DIRECTLY | `IROpcode.ADD`, `MULTIPLY`, `DIVIDE`, `COMPARE`, verifier and hosted emulator already preserve f64 values. |
| i64 scalar arithmetic | REUSE_DIRECTLY | Existing checked i64 IR/emulator arithmetic and native semantic execution tests. |
| typed f64 vectors | REUSE_DIRECTLY | `f64_vector_new`, `f64_vector_len`, `f64_vector_get` are registered in semantic and IR dynamic-builtin tables. |
| typed i64 vectors | REUSE_DIRECTLY | Existing i64 vector builtin family and focused generic-vector tests. |
| vector references/slices | REUSE_DIRECTLY | Reference-aware lowering, `SLICE_LENGTH`/`SLICE_LOAD`, and vector reference signatures exist. |
| REFERENCE IR | REUSE_DIRECTLY | `IRType.REFERENCE`, reference address/load/store and verifier/emulator contracts exist. |
| Slice IR | REUSE_DIRECTLY | Slice operations are present in IR, verifier, lowering and emulator. |
| CALL | REUSE_DIRECTLY | `IROpcode.CALL` validates dynamic signatures and dispatches hosted builtins. |
| TCALL | REUSE_DIRECTLY | Assembly call surface and call-boundary tests exist; no new call opcode is needed for hosted RMSD. |
| dynamic builtin table | ADAPT_EXISTING_CONTRACT | Add only a named `sqrt` signature if the existing CALL contract proves suitable; do not add an opcode first. |
| x86 f64 ABI/vector runtime | REUSE_DIRECTLY | Existing f64 ABI and vector runtime carried the native sqrt canary; aggregate TAGG* x86 emission remains outside this slice. |
| aggregate references / TAGG* | REUSE_DIRECTLY | PR308 provides bounded immutable aggregate references and assembly verifier surface; use only if direct vector references are insufficient. |
| sqrt | GENUINELY_MISSING | No semantic builtin, IR opcode, hosted dynamic builtin, runtime helper, or x86 emitter path exists at the audited base. |
| SSD | ADAPT_EXISTING_CONTRACT | PR308 already proves indexed f64 SSD on the hosted S3 IR path; first scientific slice should use direct typed vector references. |
| RMSD | GENUINELY_MISSING | No RMSD source/runtime contract exists; it can be layered over proven SSD plus a separately qualified sqrt contract. |
| historical aggregate-reference prototypes | HISTORICAL_OR_STALE_ONLY | TAGG* is a PR308 capability frontier, not evidence that native aggregate x86 execution is qualified. |

## Reuse decision

The first implementation slice must attempt direct `f64_vector` references,
`f64_vector_len/get`, while-loop control and existing f64 arithmetic. It must
not introduce `NativeIndexedValue`, new TAGG lowering, or a new IR opcode
unless the direct path fails for a documented contract reason.

The existing CALL contract is the only permitted initial route for `sqrt`.
Hosted execution may use a reference implementation for correctness, but
native qualification requires an explicit x86-64 SSE2 path. A libm dependency
is not implied by this audit.

## Known limitations

PR308's full-suite evidence was repaired after three stale opcode-enum tests,
but the corrected full suite was not rerun. The new campaign therefore runs
one inherited corrected-state full suite before production implementation.
Linux x86-64 qualification remains an environment-dependent gate and is not
claimed by this document.
