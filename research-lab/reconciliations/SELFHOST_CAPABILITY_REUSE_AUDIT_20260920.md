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
## Complementary repository-wide audit
# Self-host Capability Reuse Audit — 2026-09-20

## Purpose

This audit was triggered after PR #307/#308 exposed a preventable planning error: a self-host campaign began reasoning as if aggregate ownership/borrowing had to be invented, although the repository already contained validated ownership, borrowed-view, numeric-vector, reference/slice IR, and native x86-64 contracts.

The purpose is to prevent future campaign prompts from re-implementing established S3 capabilities.

## Audited anchors

CANONICAL_MAIN=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
SELFHOST_CURRENT_PR=308
SELFHOST_CURRENT_HEAD=db0f6b1533938c925daa603209d76d94bbe72485
RESEARCH_BRANCH=research/zettelkasten-lab-20260812

The audit inspected current code, normative specifications, milestone documents, later execution/closure reports, self-host architecture documents, native backend/runtime code, and tests.

## Authority order for future capability decisions

When documents disagree, use this order:

1. exact-head executable implementation plus tests/evidence;
2. current normative spec or accepted ADR matching that implementation;
3. later execution or closure report for the capability;
4. architecture/planning milestone document;
5. overview, AI guidance, or capability manifest;
6. old roadmap or historical research description.

A lower item must not override newer executable evidence. Historical documents remain provenance and must not be silently rewritten.

## Mandatory classification before new capability work

Every proposed semantic, IR, runtime, ABI, Assembly, or backend addition must be classified before implementation as one of:

REUSE_DIRECTLY
PORT_TO_SELFHOST
ADAPT_EXISTING_CONTRACT
GENUINELY_MISSING
HISTORICAL_OR_STALE_ONLY

A new opcode, ABI family, ownership rule, runtime representation, or library dependency is allowed only after the audit identifies why existing contracts cannot represent the requirement.

## Current reuse matrix

| Capability | Classification | Existing authority/evidence | Self-host consequence |
| --- | --- | --- | --- |
| checked i64 / IEEE f64 / conversions | REUSE_DIRECTLY | M1.32 numeric IR/native SSE2 path | do not recreate numeric semantics |
| scalar f64 SysV calls | REUSE_DIRECTLY | M1.34 FFI + native tests | use existing float ABI classes |
| borrowed slices | REUSE_DIRECTLY / PORT_TO_SELFHOST | M1.34, M1.35, M1.62 | reuse lexical borrow and base+length view semantics |
| owned dynamic data | REUSE_DIRECTLY / PORT_TO_SELFHOST | M1.39 | do not invent GC or a second ownership system |
| i64/f64 vectors | REUSE_DIRECTLY | M1.40 + ordered-collections spec | use existing descriptor/runtime/bounds contracts |
| vector<T> closed specialization | REUSE_DIRECTLY | M1.55 execution report | generic source surface lowers to validated vectors |
| composite ownership | PORT_TO_SELFHOST | M1.51/M1.52 execution reports | ownership/borrow flow exists; self-host maps to it |
| reference/slice IR | REUSE_DIRECTLY | current IR, generic IR/verifier, ADDRESS_OF/REFERENCE_*/SLICE_* | avoid parallel reference opcode families without proof |
| composite vectors Linux x86-64 | REUSE_DIRECTLY | S3 1.2 composite-vector representability report | native aggregate/vector layout is not a blank slate |
| f64 vector native runtime | REUSE_DIRECTLY | x86 runtime + M1.40 tests | scientific indexed data need not depend on new TAGG opcodes |
| scientific borrowed-slice f64 call | REUSE_DIRECTLY | test_ffi_capability scientific batch score | numeric slice ABI already has real Linux evidence |
| sqrt | GENUINELY_MISSING | repository-wide audit found no S3 semantic builtin, IR/runtime helper, or backend contract | legitimate next math capability |
| libm linking for standalone native path | NOT_DIRECTLY_AVAILABLE | FFI/project metadata exist, but native toolchain links nostdlib and foreign-library declarations are not a complete runtime linker path | do not assume libm is free reuse |
| PR #308 TAGG family | PR_LOCAL_ADAPTATION / REVIEW_REQUIRED | introduced for NativeIndexedValue aggregate references | not required as prerequisite for direct f64-vector SSD/RMSD |

## Important correction after PR #307/#308

The repository did not lack ownership or aggregate borrowing in general.

The actual gap was narrower:

existing language/runtime capability = YES
existing self-host mapping for the chosen NativeIndexedValue wrapper = INCOMPLETE / NEW
general language ownership redesign = NOT REQUIRED

PR #308 proved a bounded aggregate-reference path and SSD=14.0 on hosted IR, but the scientific workload itself does not inherently require the NativeIndexedValue wrapper or TAGG Assembly surface.

For the scientific path, the minimum existing capability is closer to:

f64_vector / vector<f64>
-> shared lexical borrow
-> f64_vector_len / f64_vector_get
-> loop + f64 arithmetic
-> SSD
-> sqrt
-> RMSD

Therefore Linux qualification of a direct vector-based SSD/RMSD path must be attempted before treating TAGG aggregate emission as a scientific-workload prerequisite.

TAGG may still be useful if required by the generic self-host value model. That is a separate claim and must be justified independently.

## sqrt design pre-audit

A repository-wide search found no existing S3 sqrt contract. This is a genuine missing capability.

However, the project already has a mature builtin/runtime-helper route:

source builtin
-> semantic builtin signature
-> ordinary CALL
-> deterministic builtin capability/signature table
-> IR emulator implementation
-> TCALL
-> native runtime helper

Vectors, buffers, maps, sets, and resources already use this route.

Before adding a new IROpcode or AssemblyOpcode for sqrt, the next campaign must first test whether sqrt can use this existing builtin-call contract.

A likely minimal physical x86-64 implementation can reuse the existing f64/XMM ABI and SSE2 scalar square-root instruction, but this is a design hypothesis, not an implementation authorization.

Using libm is not currently a zero-cost reuse path: project metadata can declare foreign libraries and scalar f64 FFI exists, but the standalone native toolchain is explicitly nostdlib and no complete foreign-library linker integration was found.

## Documentation drift discovered

The audit found material source-of-truth drift:

- docs/ai-agent-guide.md still describes several later-supported capabilities as unsupported.
- docs/ai-capabilities.json has stale or internally inconsistent feature fields relative to later milestones.
- spec/language.md and spec/memory.md preserve older bootstrap-era limits that are superseded for later capability families by newer normative specs.
- docs/milestone-1.51.md says implementation was not started, while later M1.51/M1.52 execution reports record focused verified implementation.
- self-host policy documents describe the earlier deferred state; current user-authorized experimental campaigns therefore require an explicit overlay rather than silent interpretation.

Do not delete or rewrite this history casually. A future documentation reconciliation should create one current capability-authority index pointing to the latest authoritative evidence for each family.

## Mandatory preflight for every future megacampaign

Before implementation:

1. identify the required workload/capability;
2. search current source and tests;
3. search normative specs and ADRs;
4. search milestone execution/closure reports, not only milestone plan docs;
5. search current self-host/generic substrate;
6. search native runtime/backend support;
7. classify every required capability as REUSE_DIRECTLY, PORT_TO_SELFHOST, ADAPT_EXISTING_CONTRACT, or GENUINELY_MISSING;
8. list proposed new opcodes/types/runtime helpers/ABI changes;
9. for each new construct, state why existing machinery is insufficient;
10. only then authorize implementation.

The campaign must stop before code if this matrix is incomplete.

## Immediate technical consequence

The next scientific-workload campaign should not reopen ownership, vectors, borrowed slices, f64 arithmetic, or aggregate layout generally.

It should:

1. close PR #308's full-suite evidence gap on the corrected code head;
2. test the direct existing f64-vector path for Linux x86-64 SSD before making TAGG emission a prerequisite;
3. design sqrt reuse-first, preferring the existing builtin/CALL/runtime-helper architecture unless evidence proves it insufficient;
4. qualify sqrt and SSD natively on Linux;
5. execute minimal RMSD;
6. only then move the workload to S3-Benchmarks for independent measurement.

## Research consequence

The durable rule is:

NEW REPRESENTATION REQUIRES A REUSE AUDIT FIRST.

A campaign may still introduce a new representation when existing semantic, IR, runtime, ABI, or backend contracts cannot express the required behavior. That insufficiency must be explicit evidence, not an assumption.
